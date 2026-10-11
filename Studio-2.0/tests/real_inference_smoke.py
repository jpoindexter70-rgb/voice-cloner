"""Opt-in real checkpoint inference, using only a synthetic packaged reference."""
import io
import json
import os
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from fastapi.testclient import TestClient
from studio.app import create_app
from studio.engine import VoiceEngine

root=Path(os.environ.get('STUDIO2_TEST_DATA_DIR','.runtime/real-inference-qa')).resolve()
root.mkdir(parents=True,exist_ok=True)
model_root=Path(os.environ.get('STUDIO2_MODEL_DIR','.runtime/shared-models')).resolve()
engine=VoiceEngine(model_root)
torch.manual_seed(42)
print('Loading verified Expressive checkpoints for REAL inference',flush=True)
engine.load('expressive','cpu')
print('Generating a synthetic test reference from the official packaged conditionals',flush=True)
started=time.monotonic()
with torch.inference_mode():
    reference=engine.model.generate('This is a synthetic reference for testing a private voice studio. No family member recording is used in this test.')
values=reference.detach().cpu().numpy().reshape(-1);sr=engine.model.sr
assert len(values)>=3*sr and np.isfinite(values).all()
# A synthetic reference can be extended for Turbo's >5-second conditioning requirement.
if len(values)<=6*sr:values=np.tile(values,int(np.ceil(7*sr/len(values))))
out=io.BytesIO();sf.write(out,values,sr,format='WAV');payload=out.getvalue()
print('REAL reference generated:',round(len(values)/sr,2),'seconds in',round(time.monotonic()-started,2),'seconds',flush=True)
results=[]
with TestClient(create_app(root,engine=engine)) as c:
    c.get('/');c.headers['X-Studio-Token']=c.get('/api/session').json()['token']
    profile=c.post('/api/profiles',json={'name':'Synthetic AI validation fixture','consent':True,'authorization':'Official packaged synthetic test reference using MIT-licensed checkpoints; not an enrolled real speaker.'}).json()
    identity=profile['id']
    c.post('/api/profiles/'+identity+'/references',files={'file':('synthetic-reference.wav',payload,'audio/wav')}).raise_for_status()
    def check_job(job):
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            state=next(j for j in c.get('/api/jobs').json() if j['id']==job['id'])
            if state['status'] not in ('running','queued'):break
            time.sleep(1)
        assert state['status']=='completed',state
        for format in ('wav','mp3'):
            response=c.get(f'/api/profiles/{identity}/generated/{job["id"]}/export/{format}');response.raise_for_status()
            if format=='wav':
                samples,rate=sf.read(io.BytesIO(response.content));assert len(samples)>rate*.2 and np.isfinite(samples).all()
            assert len(response.content)>1000
        results.append({'kind':state['kind'],'engine':state['result']['engine'],'seconds':state['result']['seconds'],'elapsed_seconds':state['elapsed_seconds'],'wav_mp3_export':True})
        print('REAL job passed:',results[-1],flush=True)
    response=c.post('/api/profiles/'+identity+'/generate',json={'text':'Welcome to our private family voice studio.'});response.raise_for_status();check_job(response.json())
    response=c.post('/api/profiles/'+identity+'/convert',files={'file':('synthetic-source.wav',payload,'audio/wav')});response.raise_for_status();check_job(response.json())
    if engine.status()['models']['turbo']:
        response=c.post('/api/profiles/'+identity+'/generate',json={'text':'This is the faster voice engine.','settings':{'engine':'turbo','device':'cpu'}});response.raise_for_status();check_job(response.json())
    c.post('/api/engine/unload').raise_for_status()
    assert engine.model is None
    # Keep the clearly labeled synthetic fixture in isolated QA data, not the main family library.
(root/'real-inference-results.json').write_text(json.dumps({'results':results,'reference':'Synthetic packaged voice; no personal voice quality claim','model_unload':True},indent=2))
print('REAL inference validation completed',flush=True)
