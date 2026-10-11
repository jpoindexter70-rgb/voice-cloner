import io
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from studio.app import create_app


def client(root):
    c = TestClient(create_app(root))
    c.get('/')
    c.headers['X-Studio-Token'] = c.get('/api/session').json()['token']
    return c


def profile(c, name='Alex', minor=False):
    r = c.post('/api/profiles', json={'name': name, 'consent': True, 'authorization': 'Written permission for local tests, 2026-10-10.', 'minor': minor})
    assert r.status_code == 200, r.text
    return r.json()


def wave():
    output = io.BytesIO()
    sf.write(output, .1*np.sin(np.arange(240000)*.1), 24000, format='WAV')
    return output.getvalue()


def test_separate_profiles_references_settings_and_restart(tmp_path):
    c = client(tmp_path)
    a, b = profile(c), profile(c, 'Sam')
    r = c.post(f'/api/profiles/{a["id"]}/references', files={'file': ('test.wav', wave(), 'audio/wav')})
    assert r.status_code == 200
    asset = r.json()['primary_reference']
    assert c.get(f'/api/profiles/{b["id"]}/audio/{asset}').status_code == 404
    assert c.post(f'/api/profiles/{b["id"]}/primary/{asset}').status_code == 404
    assert c.patch(f'/api/profiles/{a["id"]}', json={'name':'Alex Updated','language':'Spanish','accent':'Mexico','speed':1.2}).status_code == 200
    restarted = client(tmp_path).get('/api/profiles').json()
    assert next(p for p in restarted if p['id']==a['id'])['primary_reference']==asset
    assert next(p for p in restarted if p['id']==b['id'])['settings']['speed']==1
    audio=c.get(f'/api/profiles/{a["id"]}/audio/{asset}')
    data, sr=sf.read(io.BytesIO(audio.content))
    assert len(data)==240000 and sr==24000


def test_revocation_and_child_lock(tmp_path):
    c=client(tmp_path)
    a=profile(c)
    asset=c.post(f'/api/profiles/{a["id"]}/references',files={'file':('test.wav',wave())}).json()['primary_reference']
    assert c.post(f'/api/profiles/{a["id"]}/revoke').status_code==200
    assert c.get(f'/api/profiles/{a["id"]}/audio/{asset}').status_code==403
    child=profile(c,'Child',True)
    assert child['consent_status']=='guardian_verification_pending'
    assert c.post(f'/api/profiles/{child["id"]}/references',files={'file':('test.wav',wave())}).status_code==403
    assert c.post(f'/api/profiles/{child["id"]}/generate',json={'text':'Test'}).status_code==403


def test_delete_preserves_other_family_and_shared_models(tmp_path):
    c=client(tmp_path);a,b=profile(c),profile(c,'Sam')
    (tmp_path/'shared-models'/'keep').write_text('shared')
    assert c.delete(f'/api/profiles/{a["id"]}').status_code==200
    assert not (tmp_path/'family-profiles'/a['id']).exists()
    assert c.get('/api/profiles').json()[0]['id']==b['id']
    assert (tmp_path/'shared-models'/'keep').exists()


def test_permission_security_quality_and_truthful_engine_status(tmp_path):
    c=client(tmp_path)
    assert c.post('/api/profiles',json={'name':'No','consent':False,'authorization':'no authorization'}).status_code==400
    a=profile(c)
    assert c.post('/api/evaluate',files={'file':('tone.wav',wave())}).json()['seconds']==10
    assert c.post('/api/evaluate',files={'file':('bad.wav',b'invalid')}).status_code==400
    assert c.post(f'/api/profiles/{a["id"]}/generate',json={'text':'Test'}).status_code==503
    assert c.delete(f'/api/profiles/{a["id"]}',headers={'X-Studio-Token':''}).status_code==403
    assert c.get('/api/profiles',headers={'Origin':'https://example.com'}).status_code==403
    assert TestClient(c.app).get('/api/profiles').status_code==401
