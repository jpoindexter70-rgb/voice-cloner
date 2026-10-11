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
from .audio import process, voice_processing, needs_processing
from .styles import effective


def now():return datetime.now(timezone.utc).isoformat()


class Jobs:
    def __init__(self,root,engine,read,folder,write,allowed,lock):
        self.root=Path(root);self.directory=self.root/'jobs';self.directory.mkdir(exist_ok=True)
        self.temporary=self.root/'temporary';self.temporary.mkdir(exist_ok=True)
        self.engine=engine;self.read=read;self.folder=folder;self.write=write;self.allowed=allowed;self.lock=lock
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='studio2-inference')
        self.jobs={};self.cancelled=set();self.recovery_warnings=[]
        self.last_activity=time.monotonic();self.live=None;self.benchmarks={}
        for path in self.directory.glob('*.json'):
            try:
                job=json.loads(path.read_text())
                if not isinstance(job,dict) or not {'id','profile','status','settings','kind'}<=job.keys():
                    raise ValueError('Invalid job record')
                if str(uuid.UUID(job['id']))+'.json'!=path.name or str(uuid.UUID(job['profile']))!=job['profile']:
                    raise ValueError('Invalid job identity')
                if job['status'] not in ('queued','running','interrupted','completed','failed','cancelled') or job['kind'] not in ('speech','conversion','adaptation','benchmark'):
                    raise ValueError('Invalid job status')
            except (OSError,ValueError,TypeError,AttributeError):
                self.recovery_warnings.append({'file':path.name,'message':'Damaged job record was preserved and skipped. Profiles and recordings were not changed.'})
                continue
            if job['status'] in ('queued','running'):
                job.update(status='interrupted',error='The studio restarted during processing. Original recordings are unchanged; retry the script or import conversion input again.')
                self.save(job)
            self.jobs[job['id']]=job

    def save(self,job):
        with self.lock:
            path=self.directory/(job['id']+'.json');tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(job,indent=2));tmp.replace(path)

    def active(self,profile=None):
        with self.lock:return bool(self.live and (profile is None or self.live['profile']==profile)) or any(j['status'] in ('queued','running') and (profile is None or j['profile']==profile) for j in self.jobs.values())

    def unload_if_idle(self,seconds):
        with self.lock:
            if seconds and not self.active() and getattr(self.engine,'model',None) is not None and time.monotonic()-self.last_activity>=seconds:
                self.engine.unload()
                return True
        return False

    def submit(self,profile,settings,text=None,source=None,kind=None,steps=100,block=.5,adaptation=None,preview_seconds=None):
        with self.lock:
            self.last_activity=time.monotonic()
            if self.live:raise ValueError('Stop live conversion before queuing another model operation.')
            person=self.read(profile);self.allowed(person)
            if not person['primary_reference']:raise ValueError('Add a clean authorized voice reference first.')
            record=next(r for r in person['recordings'] if r['id']==person['primary_reference'])
            if settings['engine']=='turbo' and text is not None and record['quality']['seconds']<=5:raise ValueError('Turbo needs a reference longer than 5 seconds.')
            if text is not None and person['language'].strip().lower() not in ('english','en'):raise ValueError('The installed engines generate English. Choose English or use recorded voice conversion.')
            if self.active() and sum(j['status'] in ('queued','running') for j in self.jobs.values())>=20:raise ValueError('Queue is full. Wait for current jobs or cancel them.')
            job={'id':str(uuid.uuid4()),'profile':profile,'profile_name':person['name'],'reference':person['primary_reference'],
                 'settings':settings,'kind':kind or ('conversion' if source is not None else 'speech'),'text':text,'status':'queued',
                 'progress':0,'created_at':now(),'error':None,'result':None,'elapsed_seconds':0,'training_steps':steps,'block_seconds':block,
                 'recordings':[r['id'] for r in person['recordings']],
                 'adaptation':adaptation if adaptation is not None else person.get('active_adaptation'),'preview_seconds':preview_seconds}
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
            if job['kind'] in ('adaptation','benchmark'):
                self.run_seed_operation(job,reference);job['elapsed_seconds']=round(time.monotonic()-started,1);self.save(job);return
            if job['kind']=='conversion':
                self.permitted(job);values,sr=self.engine.convert(source,reference,self.conversion_settings(job));self.permitted(job)
                job['progress']=90;job['phase']='Finalizing converted audio';self.save(job)
            else:
                parts=split_text(job['text']);values=[];sr=24000
                for index,text in enumerate(parts):
                    self.permitted(job);job['phase']=f'Generating segment {index+1} of {len(parts)}';self.save(job)
                    clip,sr=self.engine.synthesize(text,reference,effective(job['settings']));self.permitted(job)
                    if len(values):values.append(np.zeros(int(sr*effective(job['settings'])['pause']),dtype=np.float32))
                    values.append(clip);job['progress']=round(90*(index+1)/len(parts));job['elapsed_seconds']=round(time.monotonic()-started,1);self.save(job)
                values=np.concatenate(values)
            if len(values)==0 or not np.isfinite(values).all():raise ValueError('The engine returned invalid audio.')
            sf.write(work,values,sr,subtype='PCM_16')
            with self.lock:
                self.permitted(job);folder=self.folder(job['profile']);target=folder/'generated-audio'/(identity+'.wav')
                settings=effective(job['settings'])
                if needs_processing(settings):process(work,target,**voice_processing(settings))
                else:work.replace(target)
                if job.get('preview_seconds'):
                    clip,rate=sf.read(target,dtype='float32');sf.write(target,clip[:int(rate*job['preview_seconds'])],rate,subtype='PCM_16')
                self.permitted(job);person=self.read(job['profile'])
                result={'id':identity,'kind':job['kind'],'created_at':now(),'text':job['text'],
                        'reference':job['reference'],'settings':job['settings'],'effective_settings':settings,'seconds':round(sf.info(target).duration,2),
                        'engine':self.engine.name,'device':self.engine.device,'preview':bool(job.get('preview_seconds')),'rating':None,'ai_generated':True,'adaptation':job.get('adaptation') if job['kind']=='conversion' and settings.get('conversion_engine')=='seed' else None}

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
                self.last_activity=time.monotonic()
                try:revoked=self.read(job['profile'])['consent_status']!='authorized'
                except Exception:revoked=True
            if revoked or identity in self.cancelled:self.engine.unload()

    def conversion_settings(self,job):
        settings=dict(job['settings'])
        if job.get('adaptation'):
            identity=str(uuid.UUID(job['adaptation']))
            settings['_adapter']=str(self.folder(job['profile'])/'voice-models'/(identity+'.safetensors'))
        return settings

    def benchmark_key(self,profile,settings,block):
        return (profile['id'],profile['primary_reference'],profile.get('active_adaptation'),
                settings['device'],settings['seed_steps'],settings['seed_cfg'],block)

    def run_seed_operation(self,job,reference):
        self.permitted(job);self.engine.load('seed',job['settings']['device']);model=self.engine.model;self.permitted(job)
        if job['kind']=='adaptation':
            target=self.folder(job['profile'])/'voice-models'/(job['id']+'.safetensors')
            def progress(current,total,loss):
                self.permitted(job);job.update(progress=round(95*current/total),phase=f'Adaptation step {current}/{total}',training_loss=loss)
                self.save(job)
            try:
                paths=[self.folder(job['profile'])/'references'/identity for identity in job['recordings']]
                result=model.adapt(paths,target,job['training_steps'],progress)
                with self.lock:
                    self.permitted(job);person=self.read(job['profile'])
                    candidate=dict(id=job['id'],created_at=now(),steps=job['training_steps'],method=result['method'],sha256=result['sha256'])
                    person.setdefault('adaptations',[]).append(candidate);self.write(self.folder(job['profile']),person)
                    job.update(status='completed',phase='Candidate ready; audition and rate before activation',progress=100,result=candidate);self.save(job)
            except Exception:
                target.unlink(missing_ok=True);target.with_suffix('.json').unlink(missing_ok=True);raise
        else:
            values,sr=sf.read(reference,dtype='float32',always_2d=True);count=int(sr*(2.5+job['block_seconds']+.04))
            sample=np.pad(values.mean(axis=1)[:count],(0,max(0,count-len(values))))
            settings=self.conversion_settings(job);times=[]
            # Warm-up covers model/reference preparation and is excluded from steady-state timings.
            model.convert_values(sample,sr,reference,job['settings']['seed_steps'],job['settings']['seed_cfg'],settings.get('_adapter'))
            for index in range(3):
                self.permitted(job);started=time.monotonic()
                model.convert_values(sample,sr,reference,job['settings']['seed_steps'],job['settings']['seed_cfg'],settings.get('_adapter'))
                times.append(time.monotonic()-started);job.update(progress=(index+1)*30,phase=f'Measuring streaming context {index+1}/3');self.save(job)
            with self.lock:
                self.permitted(job);person=self.read(job['profile']);block=job['block_seconds']
                result={'ready':self.engine.device=='cuda' and max(times)<block*.8,'device':self.engine.device,
                        'block_seconds':block,'inference_ms':[round(t*1000,1) for t in times],
                        'worst_realtime_factor':round(max(times)/block,3),
                        'estimated_buffer_and_processing_ms':round((block+max(times)+.04)*1000,1),
                        'note':'Buffer plus neural inference only; excludes browser, microphone and output-device latency.'}
                self.benchmarks[self.benchmark_key(person,job['settings'],block)]=(time.monotonic(),result)
                job.update(status='completed',phase='Live benchmark passed' if result['ready'] else 'Live unavailable: measured hardware is too slow or CUDA is absent',progress=100,result=result);self.save(job)

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
