import io
import threading
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from studio.app import create_app
from studio.engine import split_text
from tests.test_library import wave


class AdapterFixture:
    """Orchestration fixture only; never counted as AI inference validation."""
    name='expressive';device='cpu';message='Fixture';references=[]
    def status(self):return {'dependencies':True,'models':{'expressive':True,'turbo':True},'message':'Fixture'}
    def unload(self):self.message='Unloaded'
    def synthesize(self,text,reference,settings):
        self.references.append(str(reference))
        return .1*np.sin(np.arange(24000)*.1),24000
    def convert(self,source,reference,settings):return self.synthesize('',reference,settings)


def open_client(root,fixture):
    c=TestClient(create_app(root,engine=fixture));c.get('/');c.headers['X-Studio-Token']=c.get('/api/session').json()['token'];return c


def person(c):
    p=c.post('/api/profiles',json={'name':'Fixture adult','consent':True,'authorization':'Synthetic test fixture; no real speaker.'}).json()
    r=c.post('/api/profiles/'+p['id']+'/references',files={'file':('ref.wav',wave())})
    assert r.status_code==200
    return r.json()


def wait(c,job):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        current=next(j for j in c.get('/api/jobs').json() if j['id']==job['id'])
        if current['status'] not in ('queued','running'):return current
        time.sleep(.02)
    raise AssertionError('Job did not finish')


def test_jobs_real_export_history_and_isolation(tmp_path):
    fixture=AdapterFixture();fixture.references=[]
    c=open_client(tmp_path,fixture);a,b=person(c),person(c)
    try:
        scripts=['One test.',' '.join(['Long speech.']*50)]
        jobs=c.post('/api/profiles/'+a['id']+'/batch',json={'texts':scripts}).json()
        for job in jobs:
            result=wait(c,job);assert result['status']=='completed',result
            asset=result['id']
            response=c.get(f'/api/profiles/{a["id"]}/generated/{asset}/export/mp3')
            assert response.status_code==200 and len(response.content)>1000
            output=tmp_path/(asset+'.mp3');output.write_bytes(response.content)
            from studio.audio import decode
            data,sr=decode(output.read_bytes());assert len(data)>0 and sr>0
            assert c.get(f'/api/profiles/{b["id"]}/generated/{asset}').status_code==404
            assert c.post(f'/api/profiles/{a["id"]}/generated/{asset}/rating',json={'naturalness':4,'similarity':3,'notes':'Fixture rating'}).status_code==200
        assert all(Path(r).parent.parent.name==a['id'] for r in fixture.references)
        reopened=open_client(tmp_path,AdapterFixture())
        assert len(next(p for p in reopened.get('/api/profiles').json() if p['id']==a['id'])['generated'])==2
        reopened.app.state.jobs.close()
    finally:c.app.state.jobs.close()


def test_cancellation_and_revocation_never_save_output(tmp_path):
    started=threading.Event();release=threading.Event()
    class Blocking(AdapterFixture):
        def synthesize(self,*args):
            started.set();assert release.wait(5)
            return super().synthesize(*args)
    c=open_client(tmp_path,Blocking());a=person(c)
    try:
        job=c.post('/api/profiles/'+a['id']+'/generate',json={'text':'Cancellation fixture'}).json()
        assert started.wait(3)
        assert c.delete('/api/profiles/'+a['id']).status_code==409
        c.post('/api/profiles/'+a['id']+'/revoke').raise_for_status()
        release.set();result=wait(c,job);assert result['status']=='cancelled'
        assert list((tmp_path/'family-profiles'/a['id']/'generated-audio').iterdir())==[]
        assert list((tmp_path/'temporary').iterdir())==[]
    finally:release.set();c.app.state.jobs.close()


def test_conversion_non_destructive_edits_and_recovery(tmp_path):
    c=open_client(tmp_path,AdapterFixture());a=person(c);asset=a['primary_reference']
    try:
        original=c.get(f'/api/profiles/{a["id"]}/audio/{asset}').content
        edited=c.post(f'/api/profiles/{a["id"]}/references/{asset}/edit',json={'start':1,'end':7,'speed':1.2,'pitch':1,'denoise':True})
        assert edited.status_code==200,edited.text
        assert c.get(f'/api/profiles/{a["id"]}/audio/{asset}').content==original
        job=c.post(f'/api/profiles/{a["id"]}/convert',files={'file':('input.wav',wave())}).json()
        assert wait(c,job)['status']=='completed'
        c.post('/api/engine/unload').raise_for_status()
        c.post('/api/storage/clear-temporary').raise_for_status()
        assert (tmp_path/'family-profiles'/a['id']/'references'/asset).exists()
    finally:c.app.state.jobs.close()


def test_failed_inference_preserves_reference_and_can_retry(tmp_path):
    class Recoverable(AdapterFixture):
        def synthesize(self,*args):
            if self.message!='retry':raise RuntimeError('Fixture processing error')
            return super().synthesize(*args)
    fixture=Recoverable();c=open_client(tmp_path,fixture);a=person(c)
    try:
        job=c.post('/api/profiles/'+a['id']+'/generate',json={'text':'Failure fixture'}).json()
        assert wait(c,job)['status']=='failed'
        assert (tmp_path/'family-profiles'/a['id']/'references'/a['primary_reference']).exists()
        fixture.message='retry'
        retry=c.post('/api/profiles/'+a['id']+'/generate',json={'text':'Retry fixture'}).json()
        assert wait(c,retry)['status']=='completed'
    finally:c.app.state.jobs.close()


def test_hosted_mode_requires_password_and_same_origin(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO2_PUBLIC_ORIGIN','https://studio.example.test')
    monkeypatch.setenv('STUDIO2_PASSWORD','a-long-test-password-only')
    app=create_app(tmp_path,engine=AdapterFixture())
    try:
        c=TestClient(app,base_url='https://studio.example.test')
        assert c.get('/').status_code==401
        c.auth=('family','a-long-test-password-only')
        assert c.get('/').status_code==200
        assert c.get('/api/profiles').status_code==200
        assert c.get('/api/profiles',headers={'Origin':'https://elsewhere.test'}).status_code==403
    finally:app.state.jobs.close()


def test_segmentation_does_not_drop_words_or_overflow():
    text=' '.join(['A natural sentence.']*30)+' '+'x'*600
    pieces=split_text(text)
    assert all(len(p)<=220 for p in pieces)
    assert ''.join(''.join(p.split()) for p in pieces)==''.join(text.split())


def test_backup_restore_checksums_and_preserves_existing_profiles(tmp_path):
    c=open_client(tmp_path/'first',AdapterFixture());p=person(c)
    try:
        response=c.get('/api/backup');assert response.status_code==200
        other=open_client(tmp_path/'second',AdapterFixture())
        try:
            r=other.post('/api/backup/restore',files={'file':('backup.zip',response.content)})
            assert r.status_code==200 and r.json()['restored']==1,r.text
            records=other.get('/api/profiles').json()
            assert records[0]['id']==p['id']
            r=other.post('/api/backup/restore',files={'file':('backup.zip',response.content)})
            assert r.json()['existing_profiles_preserved']==1
            import zipfile,json
            source=zipfile.ZipFile(io.BytesIO(response.content));output=io.BytesIO()
            with zipfile.ZipFile(output,'w') as z:
                for name in source.namelist():z.writestr(name,b'tampered' if name.endswith('/'+p['primary_reference']) else source.read(name))
            r=other.post('/api/backup/restore',files={'file':('tampered.zip',output.getvalue())})
            assert r.status_code==400
            assert other.get('/api/profiles').json()[0]['id']==p['id']
        finally:other.app.state.jobs.close()
    finally:c.app.state.jobs.close()


def test_invalid_backup_rejected_and_new_adult_consent_documented(tmp_path):
    c=open_client(tmp_path,AdapterFixture());p=person(c)
    try:
        assert c.post('/api/backup/restore',files={'file':('bad.zip',b'invalid')}).status_code==400
        c.post('/api/profiles/'+p['id']+'/revoke').raise_for_status()
        assert c.app.state.engine.message=='Unloaded'
        r=c.post('/api/profiles/'+p['id']+'/reauthorize',json={'name':p['name'],'consent':True,'authorization':'New documented permission for synthetic tests.'})
        assert r.status_code==200 and r.json()['consent_status']=='authorized'
        assert len(r.json()['consent_history'])==1
        child=c.post('/api/profiles',json={'name':'Child','minor':True,'consent':True,'authorization':'Parent authorization pending verification.'}).json()
        assert c.post('/api/profiles/'+child['id']+'/reauthorize',json={'name':'Child','consent':True,'authorization':'Attempted self approval is insufficient.'}).status_code==403
    finally:c.app.state.jobs.close()


def test_optional_private_mirror_hooks_preserve_profile_identity(tmp_path,monkeypatch):
    import json,shutil
    import studio.app as module
    mirror=tmp_path/'mirror';mirror.mkdir()
    class MirrorFixture:
        repository='owner/private-fixture'
        def __init__(self,*args):pass
        def restore(self,families):
            for p in mirror.iterdir():shutil.copytree(p,families/p.name,dirs_exist_ok=True)
        def save(self,folder):shutil.copytree(folder,mirror/folder.name,dirs_exist_ok=True)
        def delete(self,identity):shutil.rmtree(mirror/identity)
        def delete_recording(self,identity,asset):
            for group in ['references','original-recordings']:(mirror/identity/group/asset).unlink(missing_ok=True)
    monkeypatch.setenv('STUDIO2_BACKUP_REPO','owner/private-fixture');monkeypatch.setenv('STUDIO2_BACKUP_TOKEN','test-fixture-only')
    monkeypatch.setattr(module,'PrivateProfileStore',MirrorFixture)
    c=open_client(tmp_path/'first',AdapterFixture());p=person(c)
    try:
        assert json.loads((mirror/p['id']/'settings/profile.json').read_text())['primary_reference']==p['primary_reference']
        second=open_client(tmp_path/'second',AdapterFixture())
        try:
            assert second.get('/api/profiles').json()[0]['primary_reference']==p['primary_reference']
            second.delete('/api/profiles/'+p['id']).raise_for_status()
            assert not (mirror/p['id']).exists()
        finally:second.app.state.jobs.close()
    finally:c.app.state.jobs.close()


def test_backup_rejects_path_traversal_and_oversized_manifest(tmp_path):
    import zipfile,json,hashlib
    c=open_client(tmp_path,AdapterFixture())
    try:
        output=io.BytesIO();payload=b'escape'
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('../escape',payload)
            z.writestr('manifest.json',json.dumps({'format':'studio2-private-backup-v2','files':{'../escape':{'size':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}}}))
        assert c.post('/api/backup/restore',files={'file':('bad.zip',output.getvalue())}).status_code==400
        assert not (tmp_path.parent/'escape').exists()
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('manifest.json',' '*2_000_001)
        assert c.post('/api/backup/restore',files={'file':('large.zip',output.getvalue())}).status_code==400
    finally:c.app.state.jobs.close()
