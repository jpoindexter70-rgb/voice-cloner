"""Opt-in real browser/inference check; requires empty isolated QA data and a synthetic reference."""
from playwright.sync_api import sync_playwright
from pathlib import Path
import time,os
root=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 def until(js,seconds=30):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if page.evaluate(js):return
   page.wait_for_timeout(100)
  raise AssertionError(js+' :: '+page.locator('#notice').inner_text())
 def api(path,body=None,method='POST'):
  return page.evaluate('([path,body,method])=>api(path,body===null?{method}:json(method,body))',[path,body,method])
 page.goto(os.environ.get('STUDIO2_TEST_ORIGIN','http://127.0.0.1:8779'));until('()=>token!==""');assert api('/profiles',method='GET')==[], 'Use a separate empty test data directory';page.locator('#add-family').click();page.locator('#name').fill('Synthetic simple QA');assert not page.locator('#minor-row').is_visible();assert not page.locator('#consent-fields').is_visible();page.get_by_role('button',name='Save Profile',exact=True).click();until('()=>profiles.length>=1');page.get_by_role('button',name='Select Voice',exact=True).first.click();profile=page.evaluate('()=>selected')
 # Real Web Audio input path with synthetic browser microphone; never call this physical hardware validation.
 page.locator('#record-my-voice').click();page.locator('#enable-mic').click();until('()=>!document.getElementById("start-record").disabled');page.wait_for_timeout(300);assert page.evaluate('()=>context.state')=='running';until('()=>document.getElementById("volume").value>0',10);page.locator('#start-record').click();page.wait_for_timeout(3300);page.locator('#stop-record').click();until('()=>pending!==null');assert page.evaluate('()=>document.getElementById("volume").value')==0
 page.locator('#cancel-record').click();until('()=>stream===null&&context===null')
 # Import a synthetic upstream voice, not a personal recording; actual Turbo reference inference follows.
 ref=Path(os.environ['STUDIO2_TEST_REFERENCE'])
 page.locator('#record-my-voice').click();page.locator('#audio-file').set_input_files({'name':'synthetic.wav','mimeType':'audio/wav','buffer':ref.read_bytes()});until('()=>!document.getElementById("save-record").disabled');page.locator('#save-record').click();until('()=>profiles.find(p=>p.id===selected).recordings.length===1')
 page.locator('#voice-pitch').fill('1');page.locator('#voice-pitch').dispatch_event('input');page.locator('#voice-pitch').dispatch_event('change');until('()=>profiles.find(p=>p.id===selected).settings.pitch===1');page.locator('#reset-pitch').click();until('()=>profiles.find(p=>p.id===selected).settings.pitch===0')
 page.locator('#voice-speed').fill('1.1');page.locator('#voice-speed').dispatch_event('input');page.locator('#voice-speed').dispatch_event('change');until('()=>profiles.find(p=>p.id===selected).settings.speed===1.1')
 page.locator('#script').fill('Welcome to my YouTube channel. Today we are testing this simple narration studio.');page.locator('#short-preview').click()
 def job_done(preview):
  end=time.monotonic()+240
  while time.monotonic()<end:
   jobs=api('/jobs',method='GET');job=next((j for j in jobs if j['profile']==profile and bool(j.get('preview_seconds'))==preview),None)
   if job and job['status'] not in ('running','queued'):
    assert job['status']=='completed',job
    assert job['result']['engine']=='turbo';print('REAL simple Turbo',job['result'],flush=True);return job
   page.wait_for_timeout(500)
  raise AssertionError('Real inference timeout')
 short=job_done(True);assert short['result']['seconds']<=10;until('()=>document.querySelectorAll("#history audio").length===1');player=page.locator('#history audio').first;player.evaluate('(e)=>e.play()');page.wait_for_timeout(600);assert player.evaluate('(e)=>e.currentTime')>0
 with page.expect_download() as download:page.get_by_role('link',name='Export MP3',exact=True).first.click()
 assert Path(download.value.path()).stat().st_size>1000
 page.locator('#generate-speech').click();full=job_done(False);until('()=>document.querySelectorAll(".history-pick").length===2')
 page.locator('.history-pick').first.check();page.once('dialog',lambda d:d.accept());page.locator('#delete-selected').click();until('()=>document.querySelectorAll(".history-pick").length===1')
 page.once('dialog',lambda d:d.accept());page.locator('#clear-history').click();until('()=>profiles.find(p=>p.id===selected).generated.length===0');assert len(api('/profiles',method='GET')[0]['recordings'])==1
 page.reload();until('()=>token!==""&&profiles.length>0');assert api('/jobs',method='GET')==[]
 page.locator('#nav-workspace').click();page.screenshot(path='/tmp/studio-simple-workspace.png',full_page=True);page.locator('#nav-library').click();page.screenshot(path='/tmp/studio-simple-library.png',full_page=True)
 assert not errors,errors
 print('Browser input RMS/meter, capture/stop, import, persisted sliders/reset, real Turbo preview/full speech, playback/MP3, bulk/clear history and reload PASSED',flush=True)
 b.close()
