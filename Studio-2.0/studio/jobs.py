"""Persistent job state with one inference worker and profile-scoped commits."""
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import soundfile as sf
from .engine import split_text
from .audio import process


def now():return datetime.now(timezone.utc).isoformat()


class Jobs:
    def __init__(self,root,engine,read,folder,write,allowed,lock):
        self.root=Path(root);self.directory=self.root/'jobs';self.directory.mkdir(exist_ok=True)
        self.temporary=self.root/'temporary';self.temporary.mkdir(exist_ok=True)
        self.engine=engine;self.read=read;self.folder=folder;self.write=write;self.allowed=allowed;self.lock=lock
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='studio2-inference')
        self.jobs={};self.cancelled=set()
        for path in self.directory.glob('*.json'):
            job=json.loads(path.read_text())
            if job['status'] in ('queued','running'):
                job.update(status='interrupted',error='The studio restarted during processing. Original recordings are unchanged; submit again.');path.write_text(json.dumps(job))
            self.jobs[job['id']]=job

    def save(self,job):
        with self.lock:
            path=self.directory/(job['id']+'.json');tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(job,indent=2));tmp.replace(path)

    def active(self,profile=None):
        with self.lock:return any(j['status'] in ('queued','running') and (profile is None or j['profile']==profile) for j in self.jobs.values())

    def submit(self,profile,settings,text=None,source=None):
        with self.lock:
            person=self.read(profile);self.allowed(person)
            if not person['primary_reference']:raise ValueError('Add a clean authorized voice reference first.')
            record=next(r for r in person['recordings'] if r['id']==person['primary_reference'])
            if settings['engine']=='turbo' and text is not None and record['quality']['seconds']<=5:raise ValueError('Turbo needs a reference longer than 5 seconds.')
            if text is not None and person['language'].strip().lower() not in ('english','en'):raise ValueError('The installed engines generate English. Choose English or use recorded voice conversion.')
            if self.active() and sum(j['status'] in ('queued','running') for j in self.jobs.values())>=20:raise ValueError('Queue is full. Wait for current jobs or cancel them.')
            job={'id':str(uuid.uuid4()),'profile':profile,'profile_name':person['name'],'reference':person['primary_reference'],
                 'settings':settings,'kind':'conversion' if source is not None else 'speech','text':text,'status':'queued',
                 'progress':0,'created_at':now(),'error':None,'result':None,'elapsed_seconds':0}
            self.jobs[job['id']]=job;self.save(job)
            if source is not None:(self.temporary/(job['id']+'.source.wav')).write_bytes(source)
            self.executor.submit(self.run,job['id'])
            return dict(job)

    def permitted(self,job):
        with self.lock:
            if job['id'] in self.cancelled:raise InterruptedError('Cancelled; no partial output saved.')
            self.allowed(self.read(job['profile']))

    def run(self,identity):
        job=self.jobs[identity];started=time.monotonic();work=self.temporary/(identity+'.work.wav')
        source=self.temporary/(identity+'.source.wav')
        try:
            self.permitted(job);job.update(status='running',phase='Loading voice engine');self.save(job)
            reference=self.folder(job['profile'])/'references'/job['reference']
            if not reference.exists():raise ValueError('The saved reference is missing. Select another recording.')
            if job['kind']=='conversion':
                self.permitted(job);values,sr=self.engine.convert(source,reference,job['settings']);self.permitted(job)
                job['progress']=90;job['phase']='Finalizing converted audio';self.save(job)
            else:
                parts=split_text(job['text']);values=[];sr=24000
                for index,text in enumerate(parts):
                    self.permitted(job);job['phase']=f'Generating segment {index+1} of {len(parts)}';self.save(job)
                    clip,sr=self.engine.synthesize(text,reference,job['settings']);self.permitted(job)
                    if len(values):values.append(np.zeros(int(sr*job['settings']['pause']),dtype=np.float32))
                    values.append(clip);job['progress']=round(90*(index+1)/len(parts));job['elapsed_seconds']=round(time.monotonic()-started,1);self.save(job)
                values=np.concatenate(values)
            if len(values)==0 or not np.isfinite(values).all():raise ValueError('The engine returned invalid audio.')
            sf.write(work,values,sr,subtype='PCM_16')
            with self.lock:
                self.permitted(job);folder=self.folder(job['profile']);target=folder/'generated-audio'/(identity+'.wav')
                settings=job['settings']
                if settings['speed']!=1 or settings['pitch']!=0:process(work,target,speed=settings['speed'],pitch=settings['pitch'])
                else:work.replace(target)
                self.permitted(job);person=self.read(job['profile'])
                result={'id':identity,'kind':job['kind'],'created_at':now(),'text':job['text'],
                        'reference':job['reference'],'settings':settings,'seconds':round(sf.info(target).duration,2),
                        'engine':self.engine.name,'device':self.engine.device,'rating':None,'ai_generated':True}
                elapsed = time.monotonic() - started
                result['processing_seconds'] = round(elapsed, 2)
                result['realtime_factor'] = round(elapsed / max(sf.info(target).duration, .001), 3)
                result['latency_scope'] = 'Total recorded-job processing, including loading; not live microphone latency'
                person['generated'].append(result);self.write(folder,person)
                job.update(status='completed',progress=100,phase='Ready to play',result=result,elapsed_seconds=round(time.monotonic()-started,1));self.save(job)
        except Exception as exc:
            with self.lock:
                job.update(status='cancelled' if identity in self.cancelled or isinstance(exc,InterruptedError) else 'failed',error=str(exc),elapsed_seconds=round(time.monotonic()-started,1));self.save(job)
            self.engine.message='Job failed: '+str(exc)
        finally:
            for path in (work,source):path.unlink(missing_ok=True)
            # Remove conditioning after revocation or cancellation before another identity uses the engine.
            with self.lock:
                try:revoked=self.read(job['profile'])['consent_status']!='authorized'
                except Exception:revoked=True
            if revoked or identity in self.cancelled:self.engine.unload()

    def cancel(self,identity):
        with self.lock:
            if identity not in self.jobs:raise KeyError(identity)
            if self.jobs[identity]['status'] in ('queued','running'):
                self.cancelled.add(identity);self.jobs[identity]['phase']='Cancellation requested; current model step must finish';self.save(self.jobs[identity])
            return dict(self.jobs[identity])

    def close(self):
        with self.lock:
            for identity,job in self.jobs.items():
                if job['status'] in ('queued','running'):self.cancelled.add(identity)
        self.executor.shutdown(wait=True,cancel_futures=False)
        self.engine.unload()
