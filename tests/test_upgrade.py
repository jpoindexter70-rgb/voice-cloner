"""Recovery and audio quality regressions; fixture synthesis is explicitly not neural."""
import io
import json
import time
import zipfile
from contextlib import contextmanager

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from studio.app import create_app
from studio.audio import edit
from studio.storage import Store
from studio.workflows import Workspace


@contextmanager
def connect(root):
    with TestClient(create_app(root)) as c:
        c.get('/')
        c.headers['X-VCR-Token']=c.get('/api/session').json()['token']
        yield c


def upload(c):
    b=io.BytesIO();sf.write(b,.1*np.sin(np.arange(240000)*.05),24000,format='WAV')
    r=c.post('/api/profiles/my-voice/references',files={'file':('reference.wav',b.getvalue())},data={'consent':'true'})
    r.raise_for_status();return r.json()


def test_recycle_restores_primary_audio_and_survives_restart_backup(tmp_path):
    root=tmp_path/'data'
    with connect(root) as c:
        a=upload(c);before=c.get('/api/assets/'+a['id']+'/audio').content
        c.delete('/api/assets/'+a['id']).raise_for_status()
        assert c.get('/api/assets').json()==[]
        backup=c.get('/api/backup');backup.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(backup.content)) as z:
            assert z.read('audio/'+a['id']+'.wav')==before
    with connect(root) as c:
        assert len(c.get('/api/recovery').json())==1
        c.post('/api/recovery/'+a['id']+'/restore').raise_for_status()
        assert c.get('/api/assets/'+a['id']+'/audio').content==before
        assert c.get('/api/profiles').json()[0]['primary_asset']==a['id']
        assert c.get('/api/recovery').json()==[]
        assert c.post('/api/recovery/'+a['id']+'/restore').status_code==400
        c.post('/api/restore',files={'file':('backup.zip',backup.content)}).raise_for_status()
        assert c.get('/api/assets').json()==[]
        c.post('/api/recovery/'+a['id']+'/restore').raise_for_status()
        assert c.get('/api/assets/'+a['id']+'/audio').content==before


def test_profile_recovery_preserves_picture_preferences_and_authorization(tmp_path):
    root=tmp_path/'data'
    with connect(root) as c:
        p=c.post('/api/profiles',json={'name':'Authorized family','consent':True}).json()
        preferences=c.get('/api/profiles/'+p['id']+'/preferences').json()
        preferences['controls']['speed']=.85
        c.put('/api/profiles/'+p['id']+'/preferences',json=preferences).raise_for_status()
        c.patch('/api/profiles/'+p['id'],json={'name':p['name'],'accent_notes':'Reference A'}).raise_for_status()
        c.delete('/api/profiles/'+p['id']).raise_for_status()
        recovery=c.get('/api/recovery').json()[0]
        c.post('/api/recovery/'+recovery['id']+'/restore').raise_for_status()
        restored=next(x for x in c.get('/api/profiles').json() if x['id']==p['id'])
        assert restored['authorization']==p['authorization']
        assert restored['details']['accent_notes']=='Reference A'
        assert c.get('/api/profiles/'+p['id']+'/preferences').json()['controls']['speed']==.85


def test_recovery_works_with_legacy_extra_columns(tmp_path):
    store=Store(tmp_path);Workspace(store)
    with store.connect() as c:
        for table in ('profiles','assets','reviews'):
            c.execute('ALTER TABLE '+table+' ADD COLUMN legacy_notes TEXT')
    a='a'*32;store.path(a).write_bytes(b'preserved')
    store.add_asset(a,'my-voice','Reference','reference',{'seconds':10})
    store.delete_asset(a);store.restore_deleted(a)
    assert store.profile('my-voice')['primary_asset']==a
    store.delete_profile('my-voice');store.restore_deleted(store.recycle_items()[0]['id'])
    assert store.asset(a)['name']=='Reference'


def test_loudness_leveling_preserves_duration_limits_peaks_and_handles_silence(tmp_path):
    sr=24000;t=np.arange(sr*5)/sr
    source=tmp_path/'source.wav';target=tmp_path/'level.wav'
    x=np.concatenate([.025*np.sin(2*np.pi*220*t),.4*np.sin(2*np.pi*220*t)])
    sf.write(source,x,sr);edit(source,target,0,None,False,False,1,0,level=True)
    y,rate=sf.read(target)
    assert rate==sr and abs(len(y)-len(x))<24 and np.isfinite(y).all()
    ratio_before=np.sqrt(np.mean(x[sr*6:sr*9]**2))/np.sqrt(np.mean(x[sr:sr*4]**2))
    ratio_after=np.sqrt(np.mean(y[sr*6:sr*9]**2))/np.sqrt(np.mean(y[sr:sr*4]**2))
    assert ratio_after<ratio_before and np.max(np.abs(y))<=.85
    sf.write(source,np.zeros(sr),sr);edit(source,target,0,None,False,False,1,0,level=True)
    silence,_=sf.read(target);assert np.max(np.abs(silence))==0


def test_generation_modes_use_actual_engines_and_reject_missing_models(tmp_path,monkeypatch):
    with connect(tmp_path) as c:
        upload(c);engine=c.app.state.engine;used=[]
        monkeypatch.setattr(engine,'missing',lambda name:[])
        def generate(text,ref,settings,controls,progress,cancelled):
            used.append(settings['engine']);return .1*np.sin(np.arange(24000)*.05),24000
        monkeypatch.setattr(engine,'generate',generate)
        for mode,expected in [('fast','turbo'),('final','chatterbox')]:
            r=c.post('/api/queue',json={'text':'Hello. Another sentence.','render_mode':mode,'preview':True});r.raise_for_status()
            for _ in range(200):
                j=next(x for x in c.get('/api/queue').json() if x['id']==r.json()['id'])
                if j['status']=='complete':break
                time.sleep(.02)
            assert j['status']=='complete' and j['total']==1 and j['settings']['engine']==expected
        assert used==['turbo','chatterbox']
        monkeypatch.setattr(engine,'missing',lambda name:['missing'] if name=='turbo' else [])
        assert c.post('/api/queue',json={'text':'Hello','render_mode':'fast'}).status_code==400
        assert c.post('/api/queue',json={'text':'Hello','render_mode':'fake'}).status_code==422


def test_capabilities_match_installed_engine_api_and_preview_buttons(tmp_path):
    import inspect
    from chatterbox.tts import ChatterboxTTS
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    with connect(tmp_path) as c:
        caps=c.get('/api/capabilities').json()
        assert caps['expression']['available'] and not caps['similarity_control']['available']
        assert 'exaggeration' in inspect.signature(ChatterboxTTS.generate).parameters
        assert 'audio_prompt_path' in inspect.signature(ChatterboxTurboTTS.generate).parameters
        html=c.get('/').text;js=c.get('/static/workflows.js').text
        assert 'id="preview-button"' in html and 'id="tts-preview"' in js
        c.put('/api/settings',json={'engine':'turbo','device':'cpu'}).raise_for_status()
        caps=c.get('/api/capabilities').json()
        assert not caps['expression']['available'] and caps['laughter']['available']
        assert not caps['whisper']['available']


def test_speaker_encoder_rejects_silence_and_measures_real_embeddings(tmp_path):
    # Numerical/security adapter regression. Separate real model report covers actual encoder.
    from studio.engine import Engine
    class Encoder:
        def embeds_from_wavs(self,waves,sample_rate):
            assert sample_rate==16000 and all(len(x)==32000 for x in waves)
            return np.array([[1.,0.],[.6,.8]])
    class Model:
        ve=Encoder()
    e=Engine(tmp_path);e.model=Model();e.loaded='turbo'
    a=tmp_path/'a.wav';b=tmp_path/'b.wav'
    sf.write(a,.1*np.sin(np.arange(48000)*.05),24000);sf.write(b,.1*np.sin(np.arange(48000)*.09),24000)
    assert e.compare_speakers(a,b)['cosine']==.6
    sf.write(b,np.zeros(48000),24000)
    import pytest
    with pytest.raises(ValueError,match='audible'):
        e.compare_speakers(a,b)


def test_reference_cache_changes_on_file_and_speaker(tmp_path,monkeypatch):
    import torch
    from studio.engine import Engine
    from studio.app import GenerationIn
    e=Engine(tmp_path);calls=[]
    class Model:
        sr=24000
        def generate(self,text,**kwargs):
            calls.append(kwargs['audio_prompt_path'])
            return torch.ones((1,24000))*.1
    e.model=Model();e.loaded='turbo';e.device='cpu'
    monkeypatch.setattr(e,'load',lambda *args:None)
    a=tmp_path/'a.wav';b=tmp_path/'b.wav';a.write_bytes(b'a');b.write_bytes(b'b')
    controls=GenerationIn(text='Hello.')
    def generate(path):
        return e.generate('Hello.',path,{'engine':'turbo','device':'cpu'},controls,lambda *args:None,lambda:False)
    generate(a);generate(a);a.write_bytes(b'changed');generate(a);generate(b)
    assert calls==[str(a),None,str(a),str(b)]
    assert e.last_generation['reference_cache_hits']==1


def test_failed_reference_switch_does_not_reuse_wrong_speaker(tmp_path,monkeypatch):
    import torch
    import pytest
    from studio.engine import Engine
    from studio.app import GenerationIn
    e=Engine(tmp_path)
    class Model:
        sr=24000
        reference=None
        fail=False
        def generate(self,text,**kwargs):
            if kwargs['audio_prompt_path']:
                self.reference=kwargs['audio_prompt_path']
            if self.fail:
                self.fail=False
                raise RuntimeError('Failed after conditioning changed')
            return torch.ones((1,24000))*.1
    e.model=Model();e.loaded='turbo';e.device='cpu'
    monkeypatch.setattr(e,'load',lambda *args:None)
    a=tmp_path/'a.wav';b=tmp_path/'b.wav';a.write_bytes(b'a');b.write_bytes(b'b')
    controls=GenerationIn(text='Hello.')
    def generate(path):
        return e.generate('Hello.',path,{'engine':'turbo','device':'cpu'},controls,lambda *args:None,lambda:False)
    generate(a);e.model.fail=True
    with pytest.raises(RuntimeError,match='conditioning changed'):
        generate(b)
    generate(a)
    assert e.model.reference==str(a)
