"""Real FFmpeg processing and fixture engine orchestration; no hardware claims."""
import io,json,time
import numpy as np
import soundfile as sf
from tests.test_jobs import AdapterFixture,open_client,person,wait
from studio.styles import STYLES,effective
from studio import audio

def content(response):
    assert response.status_code==200,response.text[:200]
    return sf.read(io.BytesIO(response.content),dtype='float32')

def test_volume_noise_pitch_and_unsaved_originals(tmp_path):
    c=open_client(tmp_path,AdapterFixture());p=person(c);base='/api/profiles/'+p['id']
    try:
        raw=c.get(base+'/audio/'+p['primary_reference']).content
        settings={'pitch':-2,'speed':.9,'volume':.5,'denoise':True,'noise_strength':18}
        edited=c.post('/api/recording/preview',files={'file':('original.wav',raw,'audio/wav')},data={'settings':json.dumps(settings)})
        values,sr=content(edited);assert np.isfinite(values).all() and sr==24000
        assert len(values)/sr>sf.info(io.BytesIO(raw)).duration
        saved=c.post(base+'/references',files={'file':('adjusted.wav',edited.content,'audio/wav'),'original':('original.wav',raw,'audio/wav')})
        assert saved.status_code==200,saved.text
        record=saved.json()['recordings'][-1]
        assert c.get(base+'/originals/'+record['id']).content==raw
        assert c.get(base+'/audio/'+record['id']).content!=raw
        assert c.post('/api/recording/preview',files={'file':('bad',b'bad')},data={'settings':'{}'}).status_code==400
        assert c.post('/api/recording/preview',files={'file':('ok',raw)},data={'settings':'{"volume":3}'}).status_code==422
        # Verify volume scales and pitch shifts frequency while keeping tempo independent.
        wave=np.sin(2*np.pi*440*np.arange(24000*6)/24000).astype('float32')*.2
        source=tmp_path/'tone.wav';target=tmp_path/'processed.wav';sf.write(source,wave,24000)
        audio.process(source,target,volume=.5,pitch=-6,speed=1)
        result,rate=sf.read(target);assert abs(len(result)/rate-6)<.1
        peak=np.fft.rfftfreq(len(result),1/rate)[np.argmax(abs(np.fft.rfft(result)))];assert 305<peak<320
        assert .06<np.sqrt(np.mean(result**2))<.08
    finally:c.app.state.jobs.close()

def test_every_style_is_valid_and_applied_and_output_edit_preserves_original(tmp_path):
    class Capturing(AdapterFixture):
        def synthesize(self,text,reference,settings):
            self.last=settings
            return np.sin(np.arange(24000*4)*.08).astype('float32')*.1,24000
    engine=Capturing();c=open_client(tmp_path,engine);p=person(c);base='/api/profiles/'+p['id']
    try:
        assert set(c.get('/api/styles').json()['styles'])==set(STYLES)
        for style in STYLES:
            settings={**p['settings'],'style':style,'volume':.8}
            job=wait(c,c.post(base+'/generate',json={'text':'Style fixture','settings':settings}).json());assert job['status']=='completed',job
            assert engine.last['speed']==effective(settings)['speed']
            assert engine.last['pause']==effective(settings)['pause']
            assert job['result']['settings']['style']==style
        asset=job['id'];original=c.get(base+'/generated/'+asset).content
        before=len(c.get('/api/profiles').json()[0]['generated'])
        preview=c.post(base+'/generated/'+asset+'/preview',json={'pitch':-1,'volume':.5});content(preview)
        assert len(c.get('/api/profiles').json()[0]['generated'])==before
        copy=c.post(base+'/generated/'+asset+'/edit',json={'speed':1.1,'volume':.5});assert copy.status_code==200,copy.text
        assert c.get(base+'/generated/'+asset).content==original
        assert c.get(base+'/generated/'+copy.json()['id']+'/export/mp3').status_code==200
        assert c.post(base+'/generated/'+asset+'/edit',json={'end':100}).status_code==400
        other=person(c);assert c.post('/api/profiles/'+other['id']+'/generated/'+asset+'/edit',json={}).status_code==404
        assert c.delete(base).status_code==200
        assert c.get(base+'/generated/'+asset).status_code==404
        assert c.get('/api/jobs').json()==[]
    finally:c.app.state.jobs.close()

def test_noise_reduction_reduces_fixture_noise_preserving_tone(tmp_path):
    sr=24000;rng=np.random.default_rng(27)
    noisy=.15*np.sin(2*np.pi*440*np.arange(sr*6)/sr)+rng.normal(0,.01,sr*6)
    source=tmp_path/'noisy.wav';target=tmp_path/'clean.wav';sf.write(source,noisy,sr)
    audio.process(source,target,denoise=True,noise_strength=20)
    clean,_=sf.read(target)
    before=abs(np.fft.rfft(noisy[sr:]));after=abs(np.fft.rfft(clean[sr:]));frequencies=np.fft.rfftfreq(len(noisy[sr:]),1/sr)
    assert np.sum(after[frequencies>4000]**2)<np.sum(before[frequencies>4000]**2)*.2
    assert .9<max(after)/max(before)<1.1

def test_model_repair_handles_corruption_and_blocks_competing_operations(tmp_path,monkeypatch):
    import threading
    import studio.models as models
    started=threading.Event();release=threading.Event();called=[]
    fixture=AdapterFixture();fixture.root=tmp_path/'shared-models'
    def broken(*args):raise RuntimeError('Checkpoint integrity failed')
    def repair(root,name):
        called.append(name);started.set();assert release.wait(5)
    monkeypatch.setattr(models,'verify',broken);monkeypatch.setattr(models,'download',repair)
    c=open_client(tmp_path,fixture);p=person(c)
    try:
        assert c.post('/api/engine/setup/turbo').status_code==200;assert started.wait(2)
        assert c.get('/api/engine/setup').json()['status']=='running'
        assert c.post('/api/engine/setup/expressive').status_code==409
        assert c.post('/api/profiles/'+p['id']+'/generate',json={'text':'Do not infer while models change'}).status_code==409
        release.set();end=time.monotonic()+3
        while c.get('/api/engine/setup').json()['status']=='running' and time.monotonic()<end:time.sleep(.01)
        assert c.get('/api/engine/setup').json()['status']=='completed';assert called==['turbo']
        assert c.post('/api/engine/setup/unknown').status_code==404
    finally:release.set();c.app.state.jobs.close()

def test_corrupt_checkpoint_forces_trusted_redownload(tmp_path,monkeypatch):
    import hashlib
    import studio.models as models
    import huggingface_hub
    payload=b'verified fixture checkpoint'
    expected=hashlib.sha256(payload).hexdigest()
    spec={'repository':'fixture/checkpoints','revision':'fixture-revision','files':['voice.bin']}
    target=tmp_path/'turbo';target.mkdir();(target/'voice.bin').write_bytes(b'corrupt')
    metadata={'sha':'fixture-revision','siblings':[{'rfilename':'voice.bin','size':len(payload),'lfs':{'sha256':expected}}]}
    monkeypatch.setattr(models.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(json.dumps(metadata).encode()))
    def trusted_download(repository,filename,**kwargs):
        assert kwargs['force_download'] is True
        path=Path(kwargs['local_dir'])/'downloaded.bin';path.write_bytes(payload);return str(path)
    from pathlib import Path
    monkeypatch.setattr(huggingface_hub,'hf_hub_download',trusted_download)
    models.download(tmp_path,'turbo',spec)
    assert models.verify(tmp_path,'turbo',spec)==target
    assert (target/'voice.bin').read_bytes()==payload
