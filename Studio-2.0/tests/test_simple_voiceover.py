"""Simplified workflow regression checks with explicitly labelled orchestration fixtures."""
import numpy as np
from tests.test_jobs import AdapterFixture,open_client,person,wait

class LongFixture(AdapterFixture):
    def synthesize(self,text,reference,settings):
        return np.sin(np.arange(24000*14)*.08).astype('float32')*.1,24000


def test_names_bulk_history_restart_and_original_preservation(tmp_path):
    c=open_client(tmp_path,AdapterFixture());a,b=person(c),person(c);base='/api/profiles/'+a['id']
    try:
        asset=a['primary_reference']
        assert c.patch(base+'/references/'+asset,json={'name':'My narration reference'}).status_code==200
        assert c.patch('/api/profiles/'+b['id']+'/references/'+asset,json={'name':'Wrong profile'}).status_code==404
        jobs=[wait(c,c.post(base+'/generate',json={'text':'Fixture narration'}).json()) for _ in range(3)]
        ids=[j['id'] for j in jobs];assert all(j['status']=='completed' for j in jobs)
        assert c.patch(base+'/generated/'+ids[0],json={'name':'Intro'}).json()['name']=='Intro'
        assert c.post(base+'/history/delete',json={'ids':[ids[0],'not-my-audio']}).status_code==404
        assert len(next(p for p in c.get('/api/profiles').json() if p['id']==a['id'])['generated'])==3
        assert c.get(base+'/generated/'+ids[0]+'/export/mp3').status_code==200
        result=c.post(base+'/history/delete',json={'ids':ids[:2]}).json()
        assert result=={'deleted_audio':2,'deleted_jobs':2}
        assert c.get(base+'/generated/'+ids[0]).status_code==404
        assert all(j['id'] not in ids[:2] for j in c.get('/api/jobs').json())
        assert c.get(base+'/audio/'+asset).status_code==200
        c.app.state.jobs.close();reopened=open_client(tmp_path,AdapterFixture())
        try:
            p=next(p for p in reopened.get('/api/profiles').json() if p['id']==a['id'])
            assert [item['id'] for item in p['generated']]==ids[2:]
            assert p['recordings'][0]['name']=='My narration reference'
            assert len(reopened.get('/api/profiles').json())==2
            assert reopened.delete('/api/history').json()['deleted_audio']==1
            assert reopened.get(base+'/originals/'+asset).status_code==200
            assert not reopened.get('/api/jobs').json()
            assert not any((tmp_path/'family-profiles'/a['id']/'generated-audio').iterdir())
        finally:reopened.app.state.jobs.close()
    finally:c.app.state.jobs.close()


def test_short_preview_cap_and_settings_applied(tmp_path):
    c=open_client(tmp_path,LongFixture());a=person(c);base='/api/profiles/'+a['id']
    try:
        settings={**a['settings'],'pitch':1,'speed':1.1}
        result=wait(c,c.post(base+'/preview',json={'text':' '.join(['Narration']*100),'settings':settings,'seconds':5}).json())
        assert result['status']=='completed',result
        assert result['result']['seconds']<=5 and result['result']['preview']
        assert len(result['text'].split())<=24
        assert result['result']['settings']['pitch']==1
        assert c.post(base+'/preview',json={'text':'   '}).status_code==400
        assert c.post(base+'/preview',json={'text':'Hi','seconds':20}).status_code==422
        assert c.post(base+'/revoke').status_code==200
        assert c.post(base+'/preview',json={'text':'No access'}).status_code==403
        assert c.post(base+'/history/delete',json={}).status_code==200
    finally:c.app.state.jobs.close()


def test_history_clear_waits_for_active_job_and_removes_cancelled_records(tmp_path):
    import threading
    started=threading.Event();release=threading.Event()
    class Blocking(AdapterFixture):
        def synthesize(self,*args):
            started.set();assert release.wait(5)
            return np.zeros(24000,dtype=np.float32),24000
    c=open_client(tmp_path,Blocking());a=person(c);base='/api/profiles/'+a['id']
    try:
        job=c.post(base+'/generate',json={'text':'Fixture only'}).json();assert started.wait(2)
        assert c.post(base+'/history/delete',json={}).status_code==409
        assert c.delete('/api/history').status_code==409
        c.post('/api/jobs/'+job['id']+'/cancel');release.set()
        assert wait(c,job)['status']=='cancelled'
        assert c.post(base+'/history/delete',json={}).json()=={'deleted_audio':0,'deleted_jobs':1}
        assert c.get('/api/jobs').json()==[]
        assert c.get(base+'/audio/'+a['primary_reference']).status_code==200
    finally:release.set();c.app.state.jobs.close()
