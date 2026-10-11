import io
import numpy as np
import soundfile as sf
import pytest
from studio.audio import process
from studio.styles import effective
from tests.test_jobs import AdapterFixture,open_client,person,wait

@pytest.mark.parametrize('control,frequency,larger',[('warmth',100,True),('brightness',6000,True),('clarity',2500,True),('softness',6000,False)])
def test_tone_controls_change_the_expected_audio_band(tmp_path,control,frequency,larger):
    sr=24000;t=np.arange(sr*4)/sr;values=sum(.025*np.sin(2*np.pi*f*t) for f in [100,2500,6000]);source=tmp_path/'source.wav';target=tmp_path/'result.wav';sf.write(source,values,sr)
    process(source,target,**{control:6 if control in ('warmth','brightness') else 100})
    output,rate=sf.read(target);assert abs(len(output)/rate-4)<.01 and np.isfinite(output).all()
    def amplitude(signal):return abs(np.fft.rfft(signal)[int(frequency*4)])
    ratio=amplitude(output)/amplitude(values)
    assert ratio>1.5 if larger else ratio<.7,(control,ratio)


def test_controls_persist_preview_and_edit_without_changing_original(tmp_path):
    class Capture(AdapterFixture):
        def synthesize(self,text,reference,settings):self.last=settings;return super().synthesize(text,reference,settings)
    engine=Capture();c=open_client(tmp_path,engine);p=person(c);base='/api/profiles/'+p['id'];reference=p['primary_reference']
    try:
        original=c.get(base+'/audio/'+reference).content
        settings={**p['settings'],'warmth':4,'brightness':-2,'softness':40,'clarity':30,'denoise':True,'noise_strength':8,'pause':.7,'temperature':1,'expression':1.1,'similarity':.8,'style':'storytelling'}
        response=c.patch(base,json={**settings,'name':p['name'],'language':p['language'],'accent':p['accent']});assert response.status_code==200,response.text
        saved=response.json()['settings'];assert all(saved[key]==value for key,value in settings.items())
        job=wait(c,c.post(base+'/preview',json={'text':'Adjustment fixture','settings':settings,'seconds':10}).json());assert job['status']=='completed',job
        assert engine.last['temperature']==effective(settings)['temperature'] and engine.last['pause']==effective(settings)['pause']
        assert job['result']['settings']==settings and job['result']['effective_settings']['warmth']==4
        adjustments={'warmth':4,'brightness':-2,'softness':40,'clarity':30}
        for suffix in ['/references/'+reference+'/preview','/generated/'+job['id']+'/preview']:
            result=c.post(base+suffix,json=adjustments);assert result.status_code==200,result.text
            values,rate=sf.read(io.BytesIO(result.content));assert np.isfinite(values).all() and len(values)>0
        result=c.post(base+'/references/'+reference+'/edit',json=adjustments);assert result.status_code==200,result.text
        assert c.get(base+'/audio/'+reference).content==original
        invalid=c.patch(base,json={**settings,'warmth':7,'name':p['name'],'language':p['language'],'accent':p['accent']});assert invalid.status_code==422
        assert c.get('/api/profiles').json()[0]['settings']['warmth']==4
    finally:c.app.state.jobs.close()
