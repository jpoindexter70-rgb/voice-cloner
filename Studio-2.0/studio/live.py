"""Local, benchmark-gated streaming. Never labels an unmeasured device as ready."""
import asyncio
import json
import secrets
import time
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect


def crossfade(previous,segment,overlap,count):
    values=np.asarray(segment,dtype=np.float32).copy()
    if len(values)<count+overlap:raise ValueError('Streaming output is shorter than its required block')
    values=values[-count-overlap:]
    if previous is not None:
        ramp=np.linspace(0,1,overlap,dtype=np.float32)
        values[:overlap]=previous*(1-ramp)+values[:overlap]*ramp
    return values[:count],values[count:count+overlap].copy()


def register_live(app,jobs,engine,read,allowed,token,public_origin):
    @app.websocket('/api/profiles/{identity}/live')
    async def live(websocket:WebSocket,identity:str):
        host=websocket.headers.get('host','')
        if public_origin or host.split(':')[0] not in ('127.0.0.1','localhost','testserver') or websocket.headers.get('origin')!='http://'+host or websocket.cookies.get('studio2_session')!=token:
            await websocket.close(code=1008);return
        await websocket.accept();reserved=False;pending=None
        try:
            init=await asyncio.wait_for(websocket.receive_json(),5)
            if not isinstance(init,dict) or not isinstance(init.get('token'),str) or not secrets.compare_digest(init['token'],token):
                raise ValueError('Invalid streaming session')
            rate=init.get('sample_rate');block=init.get('block_seconds',.5)
            if not isinstance(rate,int) or isinstance(rate,bool) or not 8000<=rate<=96000 or block not in (.25,.5,1):raise ValueError('Invalid stream sample rate or block duration')
            with jobs.lock:
                person=read(identity);allowed(person)
                if jobs.active():raise ValueError('Wait for existing jobs or stop another stream first')
                settings=dict(person['settings']);key=jobs.benchmark_key(person,settings,block)
                measured=jobs.benchmarks.get(key)
                if not measured or time.monotonic()-measured[0]>300 or not measured[1]['ready']:
                    raise ValueError('Run and pass the current profile/hardware streaming benchmark first')
                jobs.live={'profile':identity};reserved=True
            pending=asyncio.create_task(asyncio.to_thread(engine.load,'seed',settings['device']))
            await asyncio.shield(pending)
            if engine.device!='cuda':raise ValueError('CUDA readiness changed; benchmark this device again')
            adapter=None
            if person.get('active_adaptation'):
                import uuid
                adapter=str(jobs.folder(identity)/'voice-models'/(str(uuid.UUID(person['active_adaptation']))+'.safetensors'))
            reference=jobs.folder(identity)/'references'/person['primary_reference']
            count=int(rate*block);history=np.zeros(int(rate*(2.5+block+.04)),dtype=np.float32);previous=None;late=0
            await websocket.send_json({'status':'ready','sample_rate':engine.model.sr,'block_seconds':block,'benchmark':measured[1]})
            while True:
                payload=await asyncio.wait_for(websocket.receive_bytes(),20)
                if len(payload)!=count*4:raise ValueError('Send exactly one configured Float32 audio block')
                samples=np.frombuffer(payload,dtype='<f4')
                if not np.isfinite(samples).all() or np.max(np.abs(samples))>1.01:raise ValueError('Invalid microphone samples')
                with jobs.lock:allowed(read(identity))
                history[:-count]=history[count:];history[-count:]=samples
                started=time.monotonic()
                pending=asyncio.create_task(asyncio.to_thread(engine.model.convert_values,history.copy(),rate,reference,settings['seed_steps'],settings['seed_cfg'],adapter))
                converted,output_rate=await asyncio.shield(pending)
                with jobs.lock:allowed(read(identity))
                elapsed=time.monotonic()-started;late=late+1 if elapsed>block else 0
                if late>=3:raise ValueError('Hardware fell behind for three blocks; stream stopped instead of building an audio backlog')
                output,previous=crossfade(previous,converted,int(output_rate*.04),int(output_rate*block))
                await websocket.send_json({'inference_ms':round(elapsed*1000,1),'late_blocks':late,'sample_rate':output_rate})
                await websocket.send_bytes(output.astype('<f4').tobytes())
        except (WebSocketDisconnect,asyncio.TimeoutError):pass
        except Exception as exc:
            try:await websocket.send_json({'status':'stopped','error':str(exc)});await websocket.close(code=1000)
            except (RuntimeError,WebSocketDisconnect):pass
        finally:
            # A disconnected client must not release the model while an inference thread still owns it.
            if pending is not None and not pending.done():
                try:await asyncio.shield(pending)
                except BaseException:pass
            if reserved:
                with jobs.lock:
                    try:revoked=read(identity)['consent_status']!='authorized'
                    except Exception:revoked=True
                    if revoked:engine.unload()
                    jobs.live=None;jobs.last_activity=time.monotonic()
