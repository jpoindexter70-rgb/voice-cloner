import io
import json
import time
import zipfile

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from studio.app import create_app
from studio.workflows import ProjectIn, Workspace, VoiceControls


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'studio')
    with TestClient(app) as c:
        c.get('/')
        c.headers['X-VCR-Token'] = c.get('/api/session').json()['token']
        yield c
    app.state.queue.stop_event.set()
    app.state.queue.wake.set()
    if app.state.queue.thread:
        app.state.queue.thread.join(5)


def upload(c, profile='my-voice', frequency=220):
    stream=io.BytesIO()
    sf.write(stream,.1*np.sin(2*np.pi*frequency*np.arange(240000)/24000),24000,format='WAV')
    r=c.post('/api/profiles/'+profile+'/references',files={'file':('fixture.wav',stream.getvalue())},data={'consent':'true'})
    r.raise_for_status();return r.json()


def wait_job(c, ident):
    for _ in range(300):
        job=next(j for j in c.get('/api/queue').json() if j['id']==ident)
        if job['status'] not in ('queued','running'):return job
        time.sleep(.02)
    raise AssertionError('Queue did not finish')


def test_profile_settings_pronunciation_and_presets_persist_independently(client):
    other=client.post('/api/profiles',json={'name':'Other','consent':True}).json()['id']
    p=client.get('/api/profiles/my-voice/preferences').json()
    p['controls']['speed']=.85;p['pronunciation']={'Matthew':'Math-yoo'};p['presets']={'Custom':p['controls']}
    assert client.put('/api/profiles/my-voice/preferences',json=p).status_code==200
    assert client.get('/api/profiles/'+other+'/preferences').json()['controls']['speed']==1
    workspace=Workspace(client.app.state.store)
    assert workspace.pronounce('my-voice','MATTHEW met Matthewson.')=='Math-yoo met Matthewson.'
    assert workspace.preferences('my-voice')['presets']['Custom']['speed']==.85
    p['language']='fr'
    assert client.put('/api/profiles/my-voice/preferences',json=p).status_code==400


def test_timeline_mix_ducking_captions_and_version_recovery(client):
    speech=upload(client);music=upload(client,frequency=330)
    p=client.post('/api/projects',json={'title':'Bedtime','clips':[
        {'asset_id':speech['id'],'start':1,'duration':2,'role':'speech','text':'Hello family.'},
        {'asset_id':music['id'],'start':0,'duration':5,'role':'music','volume':.5}]}).json()
    response=client.get('/api/projects/'+p['id']+'/export/wav');response.raise_for_status()
    x,sr=sf.read(io.BytesIO(response.content));assert sr==24000 and len(x)==120000
    # Background-only RMS after speech equals the original music gain.
    assert .033<np.sqrt(np.mean(x[4*sr:5*sr]**2))<.038
    srt=client.get('/api/projects/'+p['id']+'/captions/srt').text
    assert '00:00:01,000 --> 00:00:03,000' in srt and 'Hello family.' in srt
    assert client.get('/api/projects/'+p['id']+'/captions/vtt').text.startswith('WEBVTT\n')
    p['title']='Edited';client.put('/api/projects/'+p['id'],json=p).raise_for_status()
    versions=client.get('/api/projects/'+p['id']+'/versions').json();assert len(versions)==1
    restored=client.post('/api/projects/'+p['id']+'/restore/'+versions[0]['id']).json()
    assert restored['title']=='Bedtime'
    assert len(client.get('/api/projects/'+p['id']+'/versions').json())==2
    assert client.get('/api/projects/'+p['id']+'/export/mp3').status_code==200


def test_timeline_rejects_out_of_range_and_foreign_versions(client):
    a=upload(client)
    p=client.post('/api/projects',json={'title':'Invalid trim','clips':[{'asset_id':a['id'],'trim_start':20}]}).json()
    assert client.get('/api/projects/'+p['id']+'/export/wav').status_code==400
    assert client.post('/api/projects/'+p['id']+'/restore/not-a-version').status_code==400


def test_persistent_queue_serializes_and_resumes_completed_checkpoints(client,monkeypatch):
    upload(client)
    engine=client.app.state.engine;monkeypatch.setattr(engine,'missing',lambda name:[])
    calls=[];fail=[True]
    def generate(text,reference,settings,controls,progress,cancelled):
        calls.append(text)
        if len(calls)==2 and fail[0]:raise RuntimeError('Injected second-segment failure')
        return np.sin(np.arange(24000)*.04)*.1,24000
    monkeypatch.setattr(engine,'generate',generate)
    text=('This is one complete sentence to narrate. '*20).strip()
    first=client.post('/api/queue',json={'text':text}).json()
    failed=wait_job(client,first['id']);assert failed['status']=='failed' and failed['completed']==1
    fail[0]=False
    client.post('/api/queue/'+first['id']+'/resume').raise_for_status()
    done=wait_job(client,first['id']);assert done['status']=='complete'
    assert calls.count(first['parts'][0])>=1
    # Exactly one initial successful segment plus one failure plus remaining resumed segments.
    assert len(calls)==first['total']+1
    assert sf.info(client.app.state.store.path(done['asset']['id'])).duration>first['total']
    second=client.post('/api/queue',json={'text':'A second independent job.'}).json()
    assert wait_job(client,second['id'])['status']=='complete'
    from studio.workflows import PersistentQueue
    q=PersistentQueue(client.app.state.workspace,engine,{},__import__('threading').Lock(),__import__('threading').RLock(),client.app.state.queue.generation_model)
    assert len(q.list())==2 and all(j['status']=='complete' for j in q.list())


def test_story_character_references_and_sentence_replacement_preserve_history(client,monkeypatch):
    upload(client);other=client.post('/api/profiles',json={'name':'Alice','consent':True}).json()['id'];upload(client,other)
    e=client.app.state.engine;monkeypatch.setattr(e,'missing',lambda name:[])
    refs=[]
    def generate(text,reference,*args):
        refs.append(reference.stem);return np.ones(24000)*.1,24000
    monkeypatch.setattr(e,'generate',generate)
    p=client.post('/api/projects',json={'title':'Two voices','text':'Narrator sentence.\nAlice: Character sentence.','characters':{'Alice':other}}).json()
    jobs=client.post('/api/projects/'+p['id']+'/generate').json()
    for job in jobs:assert wait_job(client,job['id'])['status']=='complete'
    p=client.get('/api/projects/'+p['id']).json();assert len(p['clips'])==2 and len(set(refs))==2
    old=p['clips'][0]['asset_id'];clip=p['clips'][0]
    job=client.post('/api/queue',json={'text':'Replacement sentence.','project_id':p['id'],'replace_clip':clip['id']}).json()
    assert wait_job(client,job['id'])['status']=='complete'
    updated=client.get('/api/projects/'+p['id']).json()
    assert updated['clips'][0]['asset_id']!=old and updated['clips'][1]['asset_id']==p['clips'][1]['asset_id']
    assert client.app.state.store.path(old).is_file()


def test_backup_restore_roundtrip_and_tampering_preserve_current_data(client):
    a=upload(client)
    client.post('/api/projects',json={'title':'Preserved story'}).raise_for_status()
    archive=client.get('/api/backup');archive.raise_for_status()
    p=client.post('/api/profiles',json={'name':'Added later','consent':True}).json()
    response=client.post('/api/restore',files={'file':('backup.zip',archive.content)});response.raise_for_status()
    assert all(x['id']!=p['id'] for x in client.get('/api/profiles').json())
    assert client.app.state.store.path(a['id']).is_file()
    from pathlib import Path
    preserved=Path(response.json()['preserved_current_data']);assert (preserved/'audio'/(a['id']+'.wav')).is_file()
    damaged=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(archive.content)) as source,zipfile.ZipFile(damaged,'w') as target:
        for name in source.namelist():target.writestr(name,b'changed' if name=='audio/'+a['id']+'.wav' else source.read(name))
    assert client.post('/api/restore',files={'file':('bad.zip',damaged.getvalue())}).status_code==400
    assert client.get('/api/projects').json()[0]['title']=='Preserved story'


def test_noise_clipping_low_volume_and_normalization(tmp_path):
    from studio.audio import analyze,edit
    quiet=analyze(np.ones(24000)*.001,24000);assert any('quiet' in w for w in quiet['warnings'])
    clipped=analyze(np.ones(24000),24000);assert any('Clipping' in w for w in clipped['warnings'])
    noisy=analyze(np.ones(24000)*.05,24000);assert any('background noise' in w for w in noisy['warnings'])
    source=tmp_path/'source.wav';target=tmp_path/'normalized.wav'
    sf.write(source,np.sin(np.arange(48000)*.05)*.1,24000)
    edit(source,target,0,None,False,False,1,0,normalize=True,volume=.5)
    x,sr=sf.read(target);assert .47<np.max(np.abs(x))<.48


@pytest.mark.parametrize('speed,pitch',[(.5,6),(2,-6)])
def test_extreme_pitch_speed_combinations_use_supported_ffmpeg_tempo(tmp_path,speed,pitch):
    from studio.audio import edit
    source=tmp_path/'source.wav';target=tmp_path/'edited.wav'
    sf.write(source,np.sin(np.arange(240000)*.05)*.1,24000)
    result=edit(source,target,0,None,False,False,speed,pitch)
    assert abs(result['seconds']-10/speed)<.25


def test_phrase_emphasis_uses_real_audio_gain_and_sentence_pauses(client,monkeypatch):
    upload(client)
    e=client.app.state.engine;monkeypatch.setattr(e,'missing',lambda name:[])
    def generate(text,*args):return np.ones(24000)*.1,24000
    monkeypatch.setattr(e,'generate',generate)
    job=client.post('/api/queue',json={'text':'Hello [emphasis]family[/emphasis]. Another sentence.','controls':{'pause_ms':500}}).json()
    assert job['parts']==['Hello','family.','Another sentence.'] and job['emphasis']==[1]
    done=wait_job(client,job['id']);assert done['status']=='complete'
    x,sr=sf.read(client.app.state.store.path(done['asset']['id']))
    assert .124<np.max(x[sr:2*sr])<.126
    assert len(x)==round(3.5*sr) and np.max(np.abs(x[2*sr:round(2.5*sr)]))==0
    assert '[emphasis]' not in done['asset']['metadata']['text']
    assert client.post('/api/queue',json={'text':'[emphasis]Unclosed'}).status_code==400


def test_backup_retry_uses_distinct_names_when_windows_clock_repeats(tmp_path,monkeypatch):
    from scripts import backup_existing
    class SameTime:
        @staticmethod
        def now():return SameTime()
        def strftime(self,pattern):return '20261010-120000-000000'
    monkeypatch.setattr(backup_existing,'datetime',SameTime)
    source=tmp_path/'source';source.mkdir();(source/'recording.wav').write_bytes(b'preserve')
    first=backup_existing.backup(source,tmp_path/'backups')
    second=backup_existing.backup(source,tmp_path/'backups')
    assert first!=second and first.is_file() and second.is_file()


def test_application_shutdown_stops_queue_worker_and_reopen_preserves_audio(tmp_path, monkeypatch):
    root = tmp_path / 'restart'
    for index in range(3):
        app = create_app(root)
        monkeypatch.setattr(app.state.engine, 'missing', lambda name: [])
        monkeypatch.setattr(app.state.engine, 'generate', lambda *args: (np.ones(24000)*.1, 24000))
        with TestClient(app) as client:
            client.get('/')
            client.headers['X-VCR-Token'] = client.get('/api/session').json()['token']
            if index == 0:
                upload(client)
            job = client.post('/api/queue', json={'text': 'Restart reliability fixture.'}).json()
            assert wait_job(client, job['id'])['status'] == 'complete'
        assert app.state.queue.stop_event.is_set()
        assert not app.state.queue.thread.is_alive()
        assert len(app.state.store.assets()) == index + 2


def test_restore_earlier_release_backup_migrates_profile_details(client, tmp_path):
    import hashlib
    import sqlite3
    archive = client.get('/api/backup')
    archive.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(archive.content)) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    database = tmp_path / 'old.sqlite3'
    database.write_bytes(entries['database.sqlite3'])
    connection = sqlite3.connect(database)
    connection.execute('DROP TABLE profile_details')
    connection.commit(); connection.close()
    entries['database.sqlite3'] = database.read_bytes()
    manifest = json.loads(entries['manifest.json'])
    manifest['files']['database.sqlite3'] = hashlib.sha256(entries['database.sqlite3']).hexdigest()
    entries['manifest.json'] = json.dumps(manifest).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as target:
        for name, content in entries.items():
            target.writestr(name, content)
    restored = client.post('/api/restore', files={'file': ('earlier-backup.zip', out.getvalue())})
    assert restored.status_code == 200, restored.text
    assert client.get('/api/profiles').json()[0]['details'] == {}
    assert client.patch('/api/profiles/my-voice', json={'name': 'Recovered', 'accent_notes': 'Original sample'}).json()['details']['accent_notes'] == 'Original sample'
