import hashlib,io,json,zipfile,importlib.util
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from studio import prosody
from tests.test_jobs import AdapterFixture,open_client,person,wait


def test_script_preparation_preserves_questions_clauses_and_pronunciation():
    text='Dr. Lee has 3.5 kg. Is AI 25% faster?\n\nVoicecraft needs 32 GB, not 20.'
    prepared=prosody.plan(text,{'Voicecraft':'voice craft'})
    assert prepared['prepared_text']=='doctor Lee has three point five kilograms. Is A I twenty five percent faster?\n\nvoice craft needs thirty two gigabytes, not twenty.'
    assert prosody.normalize('It costs $1.50, not $2. Temperature: -3.5.')=='It costs one dollar and fifty cents, not two dollars. Temperature: minus three point five.'
    assert len(prepared['segments'])==3
    assert prepared['segments'][1]['text'].endswith('?')
    assert prepared['segments'][1]['section_end']
    assert prosody.normalize('Meet on 2026-10-15 at 10:30. Version 1.2.3.')=='Meet on 2026-10-15 at 10:30. Version 1.2.3.'
    text=' '.join(['Keep every word,']*90)+ ' now.'
    result=prosody.plan(text)
    assert ' '.join(p['text'] for p in result['segments'])==result['prepared_text']
    assert all(len(p['text'])<=420 for p in result['segments'])
    with pytest.raises(ValueError):prosody.plan('x'*421)


def test_natural_join_shortens_only_edge_padding_and_uses_small_gaps():
    sr=24000;voice=.1*np.sin(np.arange(sr)*.07).astype(np.float32);clip=np.r_[np.zeros(sr),voice,np.zeros(sr)]
    parts=prosody.plan('First sentence. Second sentence?\n\nThird section.')['segments']
    output,timings=prosody.join([clip,clip,clip],sr,parts)
    assert np.isfinite(output).all() and 3<len(output)/sr<4.5
    assert len(timings)==3
    assert all(q['end_sample']>q['start_sample'] for q in timings)


def test_sentence_regeneration_reuses_non_target_audio_and_retains_original(tmp_path):
    class Capture(AdapterFixture):
        def __init__(self):self.calls=[]
        def synthesize(self,text,reference,settings):self.calls.append((text,str(reference)));return super().synthesize(text,reference,settings)
    engine=Capture();client=open_client(tmp_path,engine);p=person(client);base='/api/profiles/'+p['id'];text='First sentence. Second sentence?\n\nThird section.'
    try:
        result=wait(client,client.post(base+'/generate',json={'text':text}).json());assert result['status']=='completed',result
        first=result['result'];assert first['can_regenerate'];assert len(engine.calls)==3
        original=client.get(base+'/generated/'+first['id']).content
        reference=p['primary_reference'];original_reference=client.get(base+'/audio/'+reference).content
        regenerated=wait(client,client.post(base+'/generated/'+first['id']+'/regenerate-sentence',json={'sentence':1}).json())
        assert regenerated['status']=='completed',regenerated
        assert len(engine.calls)==4 and engine.calls[-1][0]=='Second sentence?'
        root=tmp_path/'family-profiles'/p['id']/'generated-audio'
        for index in [0,2]:assert (root/(first['id']+'.segments')/(str(index)+'.wav')).read_bytes()==(root/(regenerated['id']+'.segments')/(str(index)+'.wav')).read_bytes()
        assert client.get(base+'/generated/'+first['id']).content==original
        assert client.get(base+'/audio/'+reference).content==original_reference
        other=person(client)
        assert client.post('/api/profiles/'+other['id']+'/generated/'+first['id']+'/regenerate-sentence',json={'sentence':0}).status_code==404
        assert client.post(base+'/generated/'+first['id']+'/regenerate-sentence',json={'sentence':999}).status_code==400
        assert client.delete(base+'/generated/'+regenerated['id']).status_code==200
        assert not (root/(regenerated['id']+'.segments')).exists()
        assert (root/(first['id']+'.segments')).exists()
    finally:client.app.state.jobs.close()


def test_candidates_and_quality_comparison_are_real_jobs_with_saved_seeds(tmp_path):
    client=open_client(tmp_path,AdapterFixture());p=person(client);base='/api/profiles/'+p['id']
    try:
        jobs=client.post(base+'/candidates',json={'text':'One complete sentence.','count':3}).json();assert len(jobs)==3
        completed=[wait(client,j) for j in jobs];assert all(j['status']=='completed' for j in completed)
        assert len({j['settings']['sampling_seed'] for j in jobs})==3
        assert client.post(base+'/generated/'+jobs[0]['id']+'/select-take').json()['selected']==jobs[0]['id']
        assert client.get('/api/profiles').json()[0]['preferred_generated']==jobs[0]['id']
        assert [j['result']['name'] for j in completed]==['Candidate 1 of 3','Candidate 2 of 3','Candidate 3 of 3']
        compared=client.post(base+'/compare-quality',json={'text':'Use the same script.'}).json()
        assert [j['settings']['quality_mode'] for j in compared]==['standard','natural_studio']
        assert compared[0]['settings']['sampling_seed']==compared[1]['settings']['sampling_seed']
        assert all(wait(client,j)['status']=='completed' for j in compared)
        assert client.post(base+'/candidates',json={'text':'x','count':4}).status_code==422
        assert client.post(base+'/prepare-script',json={'text':'CPU and 20.','settings':{**p['settings'],'pronunciations':{'CPU':'processor'}}}).json()['prepared_text']=='processor and twenty.'
        assert client.post(base+'/generate',json={'text':'x','settings':{**p['settings'],'pronunciations':{'x':'z'*161}}}).status_code==422
        client.post(base+'/revoke')
        assert client.post(base+'/candidates',json={'text':'Not authorized.'}).status_code==403
    finally:client.app.state.jobs.close()


def test_reference_cleanup_is_a_preview_and_preserves_original(tmp_path):
    client=open_client(tmp_path,AdapterFixture());p=person(client);base='/api/profiles/'+p['id'];asset=p['primary_reference']
    try:
        original=client.get(base+'/audio/'+asset).content
        response=client.get(base+'/references/'+asset+'/suggestions');assert response.status_code==200,response.text
        section=response.json()['suggestions'][0]
        response=client.post(base+'/references/'+asset+'/clean-preview',json={'start':section['start'],'end':section['end'],'denoise':True});assert response.status_code==200,response.text
        data,sr=sf.read(io.BytesIO(response.content));assert np.isfinite(data).all() and len(data)/sr>5
        assert client.get(base+'/audio/'+asset).content==original
        assert len(client.get('/api/profiles').json()[0]['recordings'])==1
        assert client.post(base+'/references/'+asset+'/clean-preview',json={'start':0,'end':2}).status_code==400
    finally:client.app.state.jobs.close()


def test_upgrade_backup_preserves_private_data_and_excludes_shared_models(tmp_path):
    script=Path(__file__).parents[1]/'scripts/backup_upgrade.py';spec=importlib.util.spec_from_file_location('backup_upgrade',script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    install=tmp_path/'installed';local=tmp_path/'local';data=tmp_path/'data';(install/'app').mkdir(parents=True);local.mkdir();(data/'family-profiles/person/generated-audio').mkdir(parents=True);(data/'shared-models').mkdir()
    (install/'app/source.py').write_text('old source');(data/'family-profiles/person/generated-audio/audio.wav').write_bytes(b'private audio');(data/'shared-models/large.bin').write_bytes(b'weights');(local/'desktop.json').write_text(json.dumps({'data_directory':str(data)}))
    result=module.create_backup(install,local)
    with zipfile.ZipFile(result) as archive:
        assert archive.testzip() is None
        assert archive.read('previous-source/source.py')==b'old source'
        assert archive.read('family-data/family-profiles/person/generated-audio/audio.wav')==b'private audio'
        assert not any('large.bin' in name for name in archive.namelist())
    assert (data/'family-profiles/person/generated-audio/audio.wav').read_bytes()==b'private audio'


def test_low_memory_rejects_model_loading_without_crashing(tmp_path,monkeypatch):
    from studio.engine import VoiceEngine
    import studio.system
    monkeypatch.setattr(studio.system,'memory_bytes',lambda:(32*1024**3,1024**3))
    engine=VoiceEngine(tmp_path)
    with pytest.raises(RuntimeError,match='free system RAM'):engine.load('expressive','cpu')
    assert engine.model is None

@pytest.mark.parametrize('extension,codec',[('mp3','libmp3lame'),('m4a','aac'),('mp4','aac')])
def test_recording_import_decodes_compressed_audio_and_mp4_video(tmp_path,extension,codec):
    import subprocess
    from studio.audio import ffmpeg
    sr=24000;wave=tmp_path/'input.wav';sf.write(wave,.1*np.sin(np.arange(sr*6)*.1),sr)
    encoded=tmp_path/('recording.'+extension)
    command=[ffmpeg(),'-v','error','-nostdin','-y']
    if extension=='mp4':command+=['-f','lavfi','-i','color=c=black:s=32x32:r=1','-i',str(wave),'-map','0:v','-map','1:a','-c:v','mpeg4','-shortest']
    else:command+=['-i',str(wave)]
    command+=['-c:a',codec,str(encoded)];subprocess.run(command,check=True,capture_output=True,timeout=30)
    client=open_client(tmp_path/'studio',AdapterFixture())
    try:
        p=client.post('/api/profiles',json={'name':'Synthetic format test','consent':True,'authorization':'Synthetic test only.'}).json();base='/api/profiles/'+p['id'];raw=encoded.read_bytes()
        result=client.post(base+'/references',files={'file':(encoded.name,raw)});assert result.status_code==200,result.text
        asset=result.json()['primary_reference'];decoded,rate=sf.read(io.BytesIO(client.get(base+'/audio/'+asset).content));assert 5.9<len(decoded)/rate<6.2
        assert client.get(base+'/originals/'+asset).content==raw
    finally:client.app.state.jobs.close()


def test_long_inference_keeps_job_status_and_profiles_responsive(tmp_path):
    import threading,time
    entered=threading.Event();release=threading.Event()
    class Blocking(AdapterFixture):
        def synthesize(self,*args):entered.set();release.wait(5);return super().synthesize(*args)
    client=open_client(tmp_path,Blocking());p=person(client)
    try:
        response=client.post('/api/profiles/'+p['id']+'/generate',json={'text':'A complete sentence.'});job=response.json();assert entered.wait(2)
        time.sleep(.12)
        status=next(j for j in client.get('/api/jobs').json() if j['id']==job['id'])
        assert status['status']=='running' and status['elapsed_seconds']>=.1
        assert client.get('/api/profiles').status_code==200
        release.set();assert wait(client,job)['status']=='completed'
    finally:release.set();client.app.state.jobs.close()
