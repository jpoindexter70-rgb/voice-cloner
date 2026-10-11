import io
import json
import subprocess
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from studio.app import create_app
from studio.engine import segments
from studio.cli import backup, verify


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'private')
    with TestClient(app) as client:
        client.get('/')
        token = client.get('/api/session').json()['token']
        client.headers['X-VCR-Token'] = token
        yield client


def recording(seconds=10, frequency=220):
    # Generated test tone is an audio transport fixture, not a voice-quality test.
    sr = 24000
    x = .12 * np.sin(2 * np.pi * frequency * np.arange(int(seconds * sr)) / sr)
    file = io.BytesIO()
    sf.write(file, x, sr, format='WAV')
    return file.getvalue()


def upload(client, profile='my-voice', seconds=10):
    result = client.post(f'/api/profiles/{profile}/references', files={'file': ('sample.wav', recording(seconds), 'audio/wav')}, data={'consent': 'true'})
    assert result.status_code == 200, result.text
    return result.json()


def test_startup_and_security(client):
    assert client.get('/api/health').json()['application'] == 'voice-control-room-advanced'
    assert client.get('/').headers['Content-Security-Policy'].startswith("default-src 'self'")
    assert client.post('/api/profiles', json={'name': 'Unknown'}, headers={'X-VCR-Token': ''}).status_code == 403
    assert client.get('/api/profiles', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/profiles', headers={'Host': 'evil.example'}).status_code == 400
    with TestClient(client.app) as stranger:
        assert stranger.get('/api/profiles').status_code == 401


def test_consent_and_guardian(client):
    assert client.post('/api/profiles', json={'name':'Josh'}).status_code == 400
    assert client.post('/api/profiles', json={'name':'Josh','kind':'child','consent':True}).status_code == 400
    profile = client.post('/api/profiles', json={'name':'Josh','kind':'child','consent':True,'guardian':'Parent'}).json()
    assert profile['kind'] == 'child'
    assert 'Parent' in profile['authorization']
    assert client.post('/api/profiles/my-voice/references', files={'file':('x.wav',recording())}).status_code == 400


def test_profile_isolation_and_restart(client):
    a = upload(client)
    p = client.post('/api/profiles',json={'name':'Matthew','consent':True}).json()
    b = upload(client,p['id'])
    assert client.post(f'/api/profiles/my-voice/primary/{b["id"]}').status_code == 400
    root = client.app.state.store.root
    with TestClient(create_app(root)) as restarted:
        restarted.get('/')
        profiles = restarted.get('/api/profiles').json()
        assert next(p for p in profiles if p['id']=='my-voice')['primary_asset'] == a['id']
        assert next(x for x in profiles if x['id']==p['id'])['primary_asset'] == b['id']
        assert len(restarted.get('/api/assets').json()) == 2
    client.delete(f'/api/profiles/{p["id"]}')
    assert len(client.get('/api/assets').json()) == 1
    assert client.get(f'/api/assets/{a["id"]}/audio').status_code == 200
    assert client.app.state.store.path(b['id']).exists()
    recovery=client.get('/api/recovery').json()
    assert len(recovery)==1 and recovery[0]['kind']=='profile'
    client.post('/api/recovery/'+recovery[0]['id']+'/restore').raise_for_status()
    assert len(client.get('/api/assets').json())==2


def test_real_audio_conversion_waveform_wav_mp3(client,tmp_path):
    asset=upload(client)
    wave=client.get(f'/api/assets/{asset["id"]}/waveform').json()
    assert wave['seconds'] == 10 and len(wave['peaks']) == 800
    response=client.get(f'/api/assets/{asset["id"]}/export/wav')
    x,sr=sf.read(io.BytesIO(response.content))
    assert len(x)==240000 and sr==24000
    mp3=client.get(f'/api/assets/{asset["id"]}/export/mp3')
    assert mp3.status_code==200 and len(mp3.content)>1000
    target=tmp_path/'export.mp3';target.write_bytes(mp3.content)
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(target)],capture_output=True,text=True,check=True)
    assert 9.9<float(json.loads(probe.stdout)['format']['duration'])<10.2
    again=client.post('/api/profiles/my-voice/references',files={'file':('export.mp3',mp3.content)},data={'consent':'true'})
    assert again.status_code==200


def test_editor_preserves_original_and_changes_duration(client):
    asset=upload(client)
    source=client.app.state.store.path(asset['id']).read_bytes()
    response=client.post(f'/api/assets/{asset["id"]}/edit',json={'start':1,'end':7,'speed':1.5,'pitch':2,'denoise':True})
    assert response.status_code==200,response.text
    edited=response.json()
    assert edited['id']!=asset['id'] and 3.8<edited['metadata']['seconds']<4.2
    assert client.app.state.store.path(asset['id']).read_bytes()==source
    assert client.get('/api/profiles').json()[0]['primary_asset']==asset['id']
    assert client.post(f'/api/assets/{asset["id"]}/edit',json={'start':20,'end':21}).status_code==400


def test_silence_removal(client):
    sr=24000
    tone=.2*np.sin(2*np.pi*220*np.arange(sr*3)/sr)
    x=np.concatenate([np.zeros(sr*2),tone,np.zeros(sr*2),tone,np.zeros(sr*2)])
    stream=io.BytesIO();sf.write(stream,x,sr,format='WAV')
    a=client.post('/api/profiles/my-voice/references',files={'file':('silent.wav',stream.getvalue())},data={'consent':'true'}).json()
    result=client.post(f'/api/assets/{a["id"]}/edit',json={'remove_silence':True})
    assert result.status_code==200
    assert 6<result.json()['metadata']['seconds']<7


def test_bad_uploads_and_missing_model_errors(client):
    assert client.post('/api/profiles/my-voice/references',files={'file':('invalid.wav',b'not audio')},data={'consent':'true'}).status_code==400
    assert client.get('/api/assets').json()==[]
    a=upload(client,seconds=1)
    assert client.post('/api/generate',json={'text':'Hello.'}).status_code==400
    upload(client)
    newer=client.get('/api/assets').json()[0]
    client.post(f'/api/profiles/my-voice/primary/{newer["id"]}')
    response=client.post('/api/generate',json={'text':'Hello.'})
    assert response.status_code==503 and 'not installed' in response.json()['detail']
    assert client.post('/api/generate',json={'text':' '}).status_code==400
    client.post('/api/engine/load')
    for _ in range(100):
        if not client.app.state.engine.lock.locked():break
        time.sleep(.01)
    assert 'missing' in client.get('/api/engine').json()['message']


def test_generation_job_persistence_and_reviews_with_test_adapter(client,monkeypatch):
    # Tests orchestration, never claims actual AI synthesis or similarity.
    a=upload(client)
    engine=client.app.state.engine
    monkeypatch.setattr(engine,'missing',lambda name:[])
    calls=[]
    def generate(text,reference,settings,controls,progress,cancelled):
        calls.append(reference.stem)
        progress(1,1)
        engine.loaded='chatterbox';engine.device='cpu'
        return np.sin(np.arange(24000)*.05)*.1,24000
    monkeypatch.setattr(engine,'generate',generate)
    response=client.post('/api/generate',json={'text':'Hello there.'})
    assert response.status_code==200
    ident=response.json()['id']
    for _ in range(100):
        job=client.get(f'/api/jobs/{ident}').json()
        if job['status'] not in ('queued','running'):break
        time.sleep(.01)
    assert job['status']=='complete',job
    output=job['asset']
    assert calls==[a['id']] and output['metadata']['synthetic'] is True
    assert output['metadata']['reference_id']==a['id']
    assert 'AI-generated-' in client.get(f'/api/assets/{output["id"]}/audio').headers['content-disposition']
    review={'similarity':3,'naturalness':3,'pronunciation':3,'clarity':4,'consistency':3,'notes':'Transport fixture only'}
    assert client.post(f'/api/assets/{output["id"]}/review',json=review).status_code==200
    assert len(client.get('/api/reviews').json())==1
    with TestClient(create_app(client.app.state.store.root)) as restarted:
        restarted.get('/')
        assert len(restarted.get('/api/assets').json())==2
        assert len(restarted.get('/api/reviews').json())==1
    client.delete('/api/profiles/my-voice')
    assert client.get('/api/assets').json()==[]
    assert client.get('/api/reviews').json()==[]
    assert client.get('/api/profiles').json()[0]['id']=='my-voice'


def test_long_text_segmentation():
    text=('This is a test sentence. A second sentence tests natural boundaries! '*100)
    chunks=segments(text)
    assert len(chunks)>10
    assert all(len(c)<=240 for c in chunks)
    assert ' '.join(chunks)==' '.join(text.split())
    with pytest.raises(ValueError):segments('x'*300)


def test_backup_and_verification(tmp_path,monkeypatch):
    source=tmp_path/'data';source.mkdir();(source/'reference.wav').write_bytes(recording())
    result=backup(source,tmp_path/'backups')
    with zipfile.ZipFile(result) as archive:
        assert archive.read('reference.wav')==(source/'reference.wav').read_bytes()
    with pytest.raises(RuntimeError):backup(source,source/'backups')
    monkeypatch.setenv('VCR_DATA_DIR',str(source))
    with pytest.raises(RuntimeError,match='Missing'):verify('chatterbox')


def test_active_job_blocks_deletion_and_settings(client):
    asset=upload(client)
    client.app.state.jobs['running']={'status':'running'}
    assert client.delete(f'/api/assets/{asset["id"]}').status_code==409
    assert client.delete('/api/profiles/my-voice').status_code==409
    assert client.put('/api/settings',json={'engine':'turbo'}).status_code==409
    assert client.app.state.store.path(asset['id']).exists()


def test_model_integrity_rejects_tampering(tmp_path):
    import hashlib
    from studio.engine import MODELS, verify_manifest
    directory=tmp_path/'model';directory.mkdir()
    entries={}
    for filename in MODELS['chatterbox']['files']:
        path=directory/filename;path.write_bytes(b'fixture')
        entries[filename]={'sha256':hashlib.sha256(b'fixture').hexdigest(),'size':7}
    (directory/'manifest.json').write_text(json.dumps({'repository':MODELS['chatterbox']['repo'],'files':entries}))
    verify_manifest(directory,'chatterbox')
    (directory/'ve.safetensors').write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='integrity'):verify_manifest(directory,'chatterbox')


def test_engine_segment_conditioning_and_cpu_fallback(tmp_path,monkeypatch):
    import torch
    from studio.engine import Engine
    from studio.app import GenerationIn
    engine=Engine(tmp_path)
    calls=[]
    class AdapterFixture:
        sr=24000
        failed=False
        def generate(self,text,**kwargs):
            calls.append((text,kwargs,engine.device))
            if engine.device=='cuda' and not self.failed:
                self.failed=True
                raise torch.cuda.OutOfMemoryError('Simulated capacity error')
            return torch.ones((1,2400))*.1
    fixture=AdapterFixture()
    def load(name,device):
        engine.loaded=name;engine.device='cuda' if device=='auto' else device;engine.model=fixture
    monkeypatch.setattr(engine,'load',load)
    monkeypatch.setattr(engine,'unload',lambda:None)
    (tmp_path/'one-speaker.wav').write_bytes(recording())
    (tmp_path/'another-speaker.wav').write_bytes(recording())
    text='This is a test sentence. '*50
    control=GenerationIn(text=text)
    progress=[]
    wave,sr=engine.generate(text,tmp_path/'one-speaker.wav',{'engine':'chatterbox','device':'auto'},control,lambda a,b:progress.append((a,b)),lambda:False)
    assert engine.device=='cpu' and len(wave)>2400 and sr==24000
    assert calls[0][1]['audio_prompt_path']==str(tmp_path/'one-speaker.wav')
    assert calls[1][1]['audio_prompt_path']==str(tmp_path/'one-speaker.wav')
    assert any(c[1]['audio_prompt_path'] is None for c in calls[2:])
    assert engine.reference_cache_hits>0
    assert all(c[1]['exaggeration']==.5 for c in calls)
    assert progress[-1][0]==len(segments(text))
    assert 'GPU ran out of memory' in engine.message
    calls.clear()
    engine.generate('Turbo fixture.',tmp_path/'another-speaker.wav',{'engine':'turbo','device':'cpu'},control,lambda a,b:None,lambda:False)
    assert 'exaggeration' not in calls[0][1] and 'cfg_weight' not in calls[0][1]
    with pytest.raises(RuntimeError,match='cancelled'):
        engine.generate('Cancelled.',tmp_path/'one-speaker.wav',{'engine':'turbo','device':'cpu'},control,lambda a,b:None,lambda:True)


def test_backup_lock_and_reparse_refusal(tmp_path):
    from studio.cli import data_lock
    with data_lock(tmp_path/'locked'):
        with pytest.raises(RuntimeError,match='Close the studio'):
            with data_lock(tmp_path/'locked'):
                pass
    source=tmp_path/'source';source.mkdir();(source/'external').symlink_to(tmp_path/'locked',target_is_directory=True)
    with pytest.raises(RuntimeError,match='link/junction'):
        backup(source,tmp_path/'backups')


def test_generation_settings_and_review_validation(client):
    assert client.put('/api/settings',json={'engine':'unsupported'}).status_code==422
    assert client.post('/api/profiles',json={'name':' ','consent':True}).status_code==400
    asset=upload(client)
    assert client.post(f'/api/assets/{asset["id"]}/review',json={'similarity':6,'naturalness':2,'pronunciation':3,'clarity':4,'consistency':3}).status_code==422
    assert client.post(f'/api/assets/{asset["id"]}/review',json={'similarity':3,'naturalness':2,'pronunciation':3,'clarity':4,'consistency':3}).status_code==400


def test_preinstall_backup_utility_preserves_files(tmp_path):
    import sys
    source=tmp_path/'legacy';source.mkdir();(source/'recordings').mkdir()
    reference=recording()
    (source/'recordings'/'my-voice.wav').write_bytes(reference)
    (source/'unknown-profile.json').write_text('{"legacy":true}')
    script=Path(__file__).parents[1]/'scripts'/'backup_existing.py'
    result=subprocess.run([sys.executable,str(script),str(source),str(tmp_path/'archives')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert 'VERIFIED BACKUP' in result.stdout
    with zipfile.ZipFile(next((tmp_path/'archives').glob('*.zip'))) as archive:
        assert archive.read('recordings/my-voice.wav')==reference
        assert archive.read('unknown-profile.json')==b'{"legacy":true}'
    assert (source/'recordings'/'my-voice.wav').read_bytes()==reference


def test_bundled_ffmpeg_fallback(tmp_path,monkeypatch):
    from studio import audio
    monkeypatch.setattr(audio.shutil,'which',lambda name:None)
    assert Path(audio.ffmpeg()).is_file()
    source=tmp_path/'reference.wav';source.write_bytes(recording(2))
    target=tmp_path/'export.mp3'
    audio.export_mp3(source,target,synthetic=True)
    assert target.stat().st_size>1000
    metadata=audio.decode(target,tmp_path/'decoded.wav')
    assert 1.9<metadata['seconds']<2.2


def wait_job(client, ident):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = client.get(f'/api/jobs/{ident}').json()
        if result['status'] not in ('queued', 'running'):
            return result
        time.sleep(.01)
    raise AssertionError('Job did not finish')


def test_failed_generation_preserves_reference_and_allows_retry(client, monkeypatch):
    reference = upload(client)
    engine = client.app.state.engine
    monkeypatch.setattr(engine, 'missing', lambda name: [])
    before = client.app.state.store.path(reference['id']).read_bytes()
    def fail(*args):
        raise RuntimeError('Deliberate inference failure fixture')
    monkeypatch.setattr(engine, 'generate', fail)
    ident = client.post('/api/generate', json={'text': 'Failure test.'}).json()['id']
    job = wait_job(client, ident)
    assert job['status'] == 'failed' and 'inference failure' in job['error']
    assert len(client.get('/api/assets').json()) == 1
    assert len(list(client.app.state.store.audio.glob('*.wav'))) == 1
    assert client.app.state.store.path(reference['id']).read_bytes() == before
    monkeypatch.setattr(engine, 'generate', lambda *args: (np.ones(24000) * .1, 24000))
    ident = client.post('/api/generate', json={'text': 'Retry test.'}).json()['id']
    assert wait_job(client, ident)['status'] == 'complete'


def test_cancellation_and_concurrent_generation_do_not_save_partial_output(client, monkeypatch):
    import threading
    reference = upload(client)
    engine = client.app.state.engine
    monkeypatch.setattr(engine, 'missing', lambda name: [])
    entered, release = threading.Event(), threading.Event()
    def generate(text, reference, settings, controls, progress, cancelled):
        entered.set()
        assert release.wait(5)
        if cancelled():
            raise RuntimeError('Generation cancelled. No recording was saved.')
        return np.ones(24000) * .1, 24000
    monkeypatch.setattr(engine, 'generate', generate)
    ident = client.post('/api/generate', json={'text': 'Cancellation test.'}).json()['id']
    try:
        assert entered.wait(5)
        assert client.post('/api/generate', json={'text': 'Concurrent test.'}).status_code == 409
        assert client.post('/api/shutdown').status_code == 409
        assert client.post('/api/engine/load').status_code == 409
        assert client.post(f'/api/jobs/{ident}/cancel').status_code == 200
    finally:
        release.set()
    assert wait_job(client, ident)['status'] == 'cancelled'
    assert client.get('/api/assets').json()[0]['id'] == reference['id']
    assert len(list(client.app.state.store.audio.glob('*.wav'))) == 1
    assert client.post('/api/jobs/unknown/cancel').status_code == 404
    assert client.get('/api/jobs/unknown').status_code == 404


def test_missing_or_cross_speaker_saved_reference_reports_recovery_error(client):
    reference = upload(client)
    client.app.state.store.path(reference['id']).unlink()
    assert client.get(f'/api/assets/{reference["id"]}/audio').status_code == 400
    response = client.post('/api/generate', json={'text': 'Missing reference.'})
    assert response.status_code == 400 and 'missing' in response.json()['detail']
    profile = client.post('/api/profiles', json={'name': 'Other speaker', 'consent': True}).json()
    other = upload(client, profile['id'])
    with client.app.state.store.connect() as c:
        c.execute('UPDATE profiles SET primary_asset=? WHERE id=?', (other['id'], 'my-voice'))
    response = client.post('/api/generate', json={'text': 'Wrong reference.'})
    assert response.status_code == 400 and 'does not belong' in response.json()['detail']


def test_profile_details_picture_validation_and_rename_preservation(client):
    import base64
    from PIL import Image
    image = io.BytesIO()
    Image.new('RGB', (400, 300), 'blue').save(image, format='PNG')
    picture = 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode()
    profile = client.post('/api/profiles', json={'name': 'Family picture', 'consent': True}).json()
    url = '/api/profiles/' + profile['id']
    result = client.patch(url, json={'name': 'Updated family', 'language': 'en', 'accent_notes': 'Scottish reference', 'picture': picture})
    assert result.status_code == 200, result.text
    details = result.json()['details']
    with Image.open(io.BytesIO(base64.b64decode(details['picture'].split(',')[1]))) as resized:
        assert resized.size == (256, 192)
    assert details['accent_notes'] == 'Scottish reference'
    assert client.patch(url, json={'name': 'Renamed again'}).json()['details'] == details
    assert next(p for p in client.get('/api/profiles').json() if p['id'] == profile['id'])['details'] == details
    assert client.patch(url, json={'name': 'Bad', 'picture': 'data:image/png;base64,bad!'}).status_code == 400
    assert client.patch(url, json={'name': 'Bad', 'language': 'fr'}).status_code == 422
    assert client.patch(url, json={'name': 'Removed', 'picture': ''}).json()['details']['picture'] == ''
    assert client.delete(url).status_code == 200
    with client.app.state.store.connect() as connection:
        assert connection.execute('SELECT * FROM profile_details WHERE profile_id=?', (profile['id'],)).fetchone() is None


def test_diagnostic_logs_are_bounded_and_only_known_local_files(client):
    root = client.app.state.store.root
    logs = root / 'logs'; logs.mkdir()
    (logs / 'desktop.log').write_text('old line\n' * 10000 + 'Current startup failure\n')
    (logs / 'private.txt').write_text('must not be served')
    result = client.get('/api/diagnostic-logs').json()
    assert len(result['logs']) == 1
    assert result['logs'][0]['name'] == 'desktop.log'
    assert result['logs'][0]['text'].endswith('Current startup failure')
    assert len(result['logs'][0]['text'].splitlines()) <= 200
    assert client.get('/api/diagnostic-logs?path=private.txt').json() == result
