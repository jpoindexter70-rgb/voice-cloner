"""Permission/orchestration fixtures; real inference is a separate opt-in smoke test."""
import json
import numpy as np
import pytest
from starlette.websockets import WebSocketDisconnect
from studio.live import crossfade
from studio.models import sha256
from tests.test_jobs import AdapterFixture,open_client,person,wait

class SeedFixture(AdapterFixture):
    sr=22050
    def status(self):return {**super().status(),'conversion_engines':{'seed':True}}
    def load(self,name,device):self.name=name;self.device='cpu';self.model=self
    def adapt(self,recordings,target,steps,progress):
        assert recordings and all(path.exists() for path in recordings)
        progress(steps,steps,.5);target.write_bytes(b'explicit orchestration fixture')
        result={'sha256':sha256(target),'method':'fixture only'}
        target.with_suffix('.json').write_text(json.dumps(result));return result
    def convert_values(self,values,sr,*args):return np.zeros(70000,dtype=np.float32),22050


def test_profile_adaptation_rating_integrity_isolation_and_revocation(tmp_path):
    c=open_client(tmp_path,SeedFixture());a,b=person(c),person(c);base='/api/profiles/'+a['id']
    try:
        assert c.post(base+'/adaptations',json={'steps':0}).status_code==422
        job=wait(c,c.post(base+'/adaptations',json={'steps':2}).json());assert job['status']=='completed',job
        version=job['id'];endpoint=base+'/adaptations/'+version
        assert c.post('/api/profiles/'+b['id']+'/adaptations/'+version+'/activate').status_code==404
        assert c.post(endpoint+'/activate').status_code==409
        audition=wait(c,c.post(endpoint+'/audition').json());assert audition['status']=='completed'
        assert audition['result']['adaptation']==version
        assert c.post(base+'/generated/'+audition['id']+'/rating',json={'naturalness':3,'similarity':4}).status_code==200
        assert c.post(endpoint+'/activate').json()['active_adaptation']==version
        archived=c.get('/api/backup');assert archived.status_code==200
        restored=open_client(tmp_path/'restored',SeedFixture())
        try:
            response=restored.post('/api/backup/restore',files={'file':('private.zip',archived.content)})
            assert response.status_code==200,response.text
            copied=tmp_path/'restored'/'family-profiles'/a['id']/'voice-models'/(version+'.safetensors')
            assert copied.exists() and sha256(copied)==job['result']['sha256']
            assert next(p for p in restored.get('/api/profiles').json() if p['id']==a['id'])['active_adaptation']==version
        finally:restored.app.state.jobs.close()
        assert c.post(base+'/adaptations/deactivate').json()['active_adaptation'] is None
        assert c.post(base+'/live/benchmark',json={'block_seconds':.1}).status_code==400
        measured=wait(c,c.post(base+'/live/benchmark',json={'block_seconds':.5}).json())
        assert measured['status']=='completed' and measured['result']['ready'] is False
        assert len(measured['result']['inference_ms'])==3
        assert c.delete(endpoint).status_code==200
        assert (tmp_path/'family-profiles'/a['id']/'references'/a['primary_reference']).exists()
        assert c.post(base+'/revoke').status_code==200
        assert c.post(base+'/adaptations',json={'steps':2}).status_code==403
    finally:c.app.state.jobs.close()


def test_live_rejects_missing_origin_session_and_unmeasured_hardware(tmp_path):
    c=open_client(tmp_path,SeedFixture());a=person(c)
    endpoint='/api/profiles/'+a['id']+'/live'
    try:
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect(endpoint):pass
        with c.websocket_connect(endpoint,headers={'origin':'http://testserver'}) as ws:
            ws.send_json({'token':c.headers['X-Studio-Token'],'sample_rate':48000,'block_seconds':.5})
            assert 'benchmark' in ws.receive_json()['error']
    finally:c.app.state.jobs.close()


def test_stream_crossfade_is_bounded_and_finite():
    output,tail=crossfade(np.ones(40,dtype=np.float32),np.zeros(540,dtype=np.float32),40,500)
    assert len(output)==500 and len(tail)==40
    assert output[0]==1 and output[39]==0 and np.isfinite(output).all()
    with pytest.raises(ValueError):crossfade(None,np.zeros(10),40,500)


def test_live_protocol_reserves_engine_and_stops_after_revocation(tmp_path):
    import time
    class CudaProtocolFixture(SeedFixture):
        def load(self,name,device):self.name=name;self.device='cuda';self.model=self
    c=open_client(tmp_path,CudaProtocolFixture());a=person(c);jobs=c.app.state.jobs
    try:
        key=jobs.benchmark_key(a,a['settings'],.5)
        jobs.benchmarks[key]=(time.monotonic(),{'ready':True,'fixture_only':True})
        with c.websocket_connect('/api/profiles/'+a['id']+'/live',headers={'origin':'http://testserver'}) as ws:
            ws.send_json({'token':c.headers['X-Studio-Token'],'sample_rate':48000,'block_seconds':.5})
            assert ws.receive_json()['status']=='ready'
            assert jobs.active(a['id'])
            assert c.post('/api/engine/unload').status_code==409
            ws.send_bytes(np.zeros(24000,dtype='<f4').tobytes())
            assert ws.receive_json()['sample_rate']==22050
            assert len(ws.receive_bytes())==11025*4
            assert c.post('/api/profiles/'+a['id']+'/revoke').status_code==200
            ws.send_bytes(np.zeros(24000,dtype='<f4').tobytes())
            assert ws.receive_json()['status']=='stopped'
        assert jobs.live is None
    finally:jobs.close()
