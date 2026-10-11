import io
from pathlib import Path
import soundfile as sf
from studio.app import create_app
from fastapi.testclient import TestClient
from tests.test_library import profile, wave
from tests.test_jobs import AdapterFixture, open_client, person, wait


def test_preferences_restart_validation_and_revoked_selection(tmp_path):
    with TestClient(create_app(tmp_path, engine=AdapterFixture())) as c:
        c.get('/'); c.headers['X-Studio-Token']=c.get('/api/session').json()['token']
        p=profile(c)
        settings=dict(microphone='input-1',output='output-2',input_gain=1.8,
                      noise_suppression=True,echo_cancellation=False,selected_profile=p['id'],idle_unload_seconds=300)
        assert c.put('/api/preferences',json=settings).json()==settings
        assert c.put('/api/preferences',json={**settings,'input_gain':20}).status_code==422
        assert c.post('/api/profiles/'+p['id']+'/revoke').status_code==200
        assert c.put('/api/preferences',json=settings).status_code==403
        settings['selected_profile']=''
        assert c.put('/api/preferences',json=settings).status_code==200
    with TestClient(create_app(tmp_path, engine=AdapterFixture())) as c:
        c.get('/')
        assert c.get('/api/preferences').json()==settings
        facts=c.get('/api/system').json()
        assert facts['mode']=='local' and facts['data_path']==str(tmp_path.resolve())
        assert facts['logical_cpus']>0 and facts['disk_free_bytes']>0
        assert facts['vram'] is None or facts['vram']['total_bytes']>0


def test_preview_originals_and_storage_without_saving_changes(tmp_path):
    c=open_client(tmp_path,AdapterFixture()); a,b=person(c),person(c)
    asset=a['primary_reference']; endpoint=f'/api/profiles/{a["id"]}/references/{asset}'
    original=c.get(f'/api/profiles/{a["id"]}/originals/{asset}')
    assert original.status_code==200 and original.content==wave()
    assert c.get(f'/api/profiles/{b["id"]}/originals/{asset}').status_code==404
    result=c.post(endpoint+'/preview',json={'start':1,'end':9,'speed':1.2,'pitch':1,'denoise':True})
    assert result.status_code==200,result.text
    samples,sr=sf.read(io.BytesIO(result.content))
    assert 6<len(samples)/sr<7
    assert len(c.get('/api/profiles').json()[0]['recordings'])==1
    assert c.get(f'/api/profiles/{a["id"]}/originals/{asset}').content==wave()
    assert not list((tmp_path/'temporary').glob('reference-preview-*'))
    assert c.post(endpoint+'/preview',json={'start':8,'end':9}).status_code==400
    assert c.post(f'/api/profiles/{b["id"]}/references/{asset}/preview',json={'end':8}).status_code==404
    usage=c.get('/api/storage').json()
    assert usage['categories']['family-profiles']>0
    assert usage['used_bytes']==sum(usage['categories'].values())
    c.app.state.jobs.close()


def test_generated_deletion_is_scoped_and_timing_measured(tmp_path):
    c=open_client(tmp_path,AdapterFixture()); a,b=person(c),person(c)
    result=wait(c,c.post(f'/api/profiles/{a["id"]}/generate',json={'text':'Fixture test only.'}).json())
    asset=result['id']; item=result['result']
    assert item['processing_seconds']>=0 and item['realtime_factor']>=0
    assert 'not live' in item['latency_scope']
    assert c.get(f'/api/profiles/{a["id"]}/generated/{asset}/export/mp3').status_code==200
    assert c.delete(f'/api/profiles/{b["id"]}/generated/{asset}').status_code==404
    assert c.delete(f'/api/profiles/{a["id"]}/generated/{asset}').status_code==200
    assert c.get(f'/api/profiles/{a["id"]}/generated/{asset}').status_code==404
    directory=tmp_path/'family-profiles'/a['id']
    assert not (directory/'generated-audio'/(asset+'.wav')).exists()
    assert not (directory/'generated-audio'/(asset+'.mp3')).exists()
    assert (directory/'references'/a['primary_reference']).exists()
    assert (tmp_path/'family-profiles'/b['id']).exists()
    c.app.state.jobs.close()


def test_reference_pitch_respects_input_rate_and_speed_duration(tmp_path):
    import numpy as np
    from studio.audio import process
    source=tmp_path/'48khz.wav';target=tmp_path/'shifted.wav'
    sf.write(source,.15*np.sin(2*np.pi*440*np.arange(48000*6)/48000),48000)
    process(source,target,start=1,end=5,speed=1.25,pitch=3)
    samples,sr=sf.read(target)
    assert abs(len(samples)/sr-3.2)<.15
    window=samples[sr:sr*2]
    frequency=np.argmax(np.abs(np.fft.rfft(window))) * sr / len(window)
    assert 510<frequency<540


def test_engine_comparison_keeps_settings_and_reference_separate(tmp_path):
    c=open_client(tmp_path,AdapterFixture());a=person(c)
    before=c.get('/api/profiles').json()[0]['settings']
    response=c.post(f'/api/profiles/{a["id"]}/compare',json={'text':'An explicit fixture comparison.'})
    assert response.status_code==200,response.text
    jobs=response.json();assert len(jobs)==2
    assert {j['settings']['engine'] for j in jobs}=={'expressive','turbo'}
    assert all(j['reference']==a['primary_reference'] for j in jobs)
    for job in jobs:assert wait(c,job)['status']=='completed'
    assert c.get('/api/profiles').json()[0]['settings']==before
    assert c.post(f'/api/profiles/{a["id"]}/compare',json={'text':' '}).status_code==400
    c.post(f'/api/profiles/{a["id"]}/revoke')
    assert c.post(f'/api/profiles/{a["id"]}/compare',json={'text':'Forbidden.'}).status_code==403
    c.app.state.jobs.close()


def test_retry_requires_authorization_and_preserves_script_settings(tmp_path):
    class FailingFixture(AdapterFixture):
        def synthesize(self,*args):
            if self.message!='retry':raise RuntimeError('Fixture error')
            return super().synthesize(*args)
    fixture=FailingFixture();c=open_client(tmp_path,fixture);a=person(c)
    job=c.post(f'/api/profiles/{a["id"]}/generate',json={'text':'Retry this exact script.','settings':{'speed':1.2}}).json()
    assert wait(c,job)['status']=='failed'
    fixture.message='retry'
    response=c.post('/api/jobs/'+job['id']+'/retry')
    assert response.status_code==200,response.text
    retry=response.json();assert retry['text']==job['text'] and retry['settings']==job['settings']
    assert wait(c,retry)['status']=='completed'
    assert c.post('/api/jobs/'+retry['id']+'/retry').status_code==409
    c.post(f'/api/profiles/{a["id"]}/revoke')
    assert c.post('/api/jobs/'+job['id']+'/retry').status_code==403
    c.app.state.jobs.close()


def test_consent_history_and_normalized_jpeg_avatar(tmp_path):
    from PIL import Image
    c=open_client(tmp_path,AdapterFixture());a=person(c)
    assert a['consent_history'][0]['event']=='created'
    output=io.BytesIO();Image.new('RGB',(800,500),'navy').save(output,format='JPEG')
    response=c.post(f'/api/profiles/{a["id"]}/picture',files={'file':('avatar.jpg',output.getvalue(),'image/jpeg')})
    assert response.status_code==200,response.text
    result=c.get(f'/api/profiles/{a["id"]}/picture')
    with Image.open(io.BytesIO(result.content)) as image:
        assert image.format=='PNG' and max(image.size)==512
        assert not image.getexif()
    revoked=c.post(f'/api/profiles/{a["id"]}/revoke').json()
    assert revoked['consent_history'][-1]['event']=='revoked'
    body=dict(name=a['name'],authorization='New documented adult permission for this test.',consent=True)
    renewed=c.post(f'/api/profiles/{a["id"]}/reauthorize',json=body).json()
    assert renewed['consent_history'][-1]['previous_authorization']==a['authorization']
    assert renewed['consent_history'][-1]['event']=='reauthorized'
    c.app.state.jobs.close()


def test_damaged_job_history_does_not_block_startup_or_delete_data(tmp_path):
    directory=tmp_path/'jobs';directory.mkdir()
    damaged=directory/'damaged.json';damaged.write_text('{incomplete')
    c=open_client(tmp_path,AdapterFixture());a=person(c)
    health=c.get('/api/health').json()
    assert health['status']=='running' and health['recovery_warnings'][0]['file']=='damaged.json'
    assert damaged.read_text()=='{incomplete'
    assert c.get('/api/profiles').json()[0]['id']==a['id']
    job=c.post(f'/api/profiles/{a["id"]}/generate',json={'text':'Valid job with damaged prior history.'}).json()
    assert wait(c,job)['status']=='completed'
    c.app.state.jobs.close()


def test_idle_memory_release_never_deletes_files_or_interrupts_jobs(tmp_path):
    fixture=AdapterFixture();fixture.model=object()
    c=open_client(tmp_path,fixture);a=person(c);worker=c.app.state.jobs
    worker.last_activity=0
    assert not worker.unload_if_idle(0)
    assert worker.unload_if_idle(60)
    assert fixture.message=='Unloaded'
    assert (tmp_path/'family-profiles'/a['id']/'references'/a['primary_reference']).exists()
    fixture.message='Still loaded';worker.jobs['active-fixture']={'status':'running','profile':a['id']}
    assert not worker.unload_if_idle(60)
    assert fixture.message=='Still loaded'
    worker.jobs.clear();worker.close()
