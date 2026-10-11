from pathlib import Path
import os,time,json
from playwright.sync_api import sync_playwright
REF=Path(os.environ['VOICECRAFT_TEST_REFERENCE'])
refs=[REF];assert REF.is_file()
with sync_playwright() as p:
 b=p.chromium.launch(**({'executable_path':os.environ['PLAYWRIGHT_CHROMIUM']} if os.getenv('PLAYWRIGHT_CHROMIUM') else {}),headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 def until(js,seconds=30):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if page.evaluate(js):return
   page.wait_for_timeout(150)
  raise AssertionError(js+' :: '+page.locator('#notice').inner_text())
 def api(path,body=None,method='POST'):return page.evaluate('([path,body,method])=>api(path,body===null?{method}:json(method,body))',[path,body,method])
 page.goto(os.environ.get('VOICECRAFT_TEST_ORIGIN','http://127.0.0.1:8781'));until('()=>token!==""');assert api('/profiles',method='GET')==[], 'Use a new isolated empty QA data directory; never run this test against personal profiles.'
 assert page.title()=='VoiceCraft Studio';assert page.locator('.cover-art').is_visible()
 page.locator('#add-family').click();page.locator('#name').fill('VoiceCraft synthetic QA');page.get_by_role('button',name='Save Profile',exact=True).click();until('()=>profiles.length===1');page.get_by_role('button',name='Select Voice',exact=True).click();profile=page.evaluate('()=>selected')
 page.locator('#record-my-voice').click();assert len(page.locator('#record-script').input_value().split())>70;page.locator('#record-script-choice').select_option('long');assert len(page.locator('#record-script').input_value().split())>150
 page.locator('#enable-mic').click();until('()=>!document.getElementById("start-record").disabled');until('()=>document.getElementById("volume").value>0',10);page.locator('#start-record').click();page.wait_for_timeout(6100);page.locator('#stop-record').click();until('()=>pending!==null');assert page.evaluate('()=>document.getElementById("volume").value')==0
 page.locator('#record-adjustments').click();page.locator('#record-pitch').fill('-1');page.locator('#record-volume').fill('0.8');page.locator('#record-noise').fill('12');assert page.locator('#save-record').is_disabled();page.locator('#preview-record-adjustments').click();until('()=>!document.getElementById("save-record").disabled');assert page.evaluate('()=>pending!==originalRecording');page.locator('#reset-record-adjustments').click();until('()=>pending===originalRecording');page.locator('#cancel-record').click();until('()=>stream===null')
 page.locator('#import-voice').click();page.locator('#audio-file').set_input_files({'name':'Synthetic upstream.wav','mimeType':'audio/wav','buffer':refs[0].read_bytes()});until('()=>pending!==null');page.locator('#record-adjustments').click() if not page.locator('#record-volume').is_visible() else None
 page.locator('#record-volume').fill('0.9');page.locator('#preview-record-adjustments').click();until('()=>!document.getElementById("save-record").disabled');page.locator('#save-record').click();until('()=>profiles[0].recordings.length===1')
 page.locator('#voice-volume').fill('0.8');page.locator('#voice-volume').dispatch_event('change');until('()=>profiles[0].settings.volume===0.8')
 page.locator('#script').fill('Welcome to my channel. Today we are exploring a wonderful new discovery together.');until('()=>document.getElementById("voice-style").options.length===10')
 def wait_job(job):
  end=time.monotonic()+180
  while time.monotonic()<end:
   current=next(j for j in api('/jobs',method='GET') if j['id']==job['id'])
   if current['status'] not in ('queued','running'):
    assert current['status']=='completed',current;return current
   page.wait_for_timeout(500)
  raise AssertionError('Inference timeout')
 for style in ['normal','storytelling','bedtime','energetic','calm','horror','presenter','food','demo','review']:
  page.locator('#voice-style').select_option(style);until('()=>profiles[0].settings.style==='+json.dumps(style))
  settings=page.evaluate('()=>workingSettings()');job=api('/profiles/'+profile+'/preview',{'text':page.locator('#script').input_value(),'settings':settings,'seconds':10});done=wait_job(job);assert done['result']['seconds']<=10 and done['result']['engine']=='turbo';print('REAL Turbo style',style,done['result']['seconds'],done['elapsed_seconds'],flush=True)
 until('()=>document.querySelectorAll("#history audio").length===10');page.locator('#history audio').first.evaluate('(e)=>e.play()');page.wait_for_timeout(600);assert page.locator('#history audio').first.evaluate('(e)=>e.currentTime')>0
 page.get_by_role('button',name='Adjust Audio',exact=True).first.click();page.locator('#edit-pitch').fill('-1');page.locator('#edit-volume').fill('0.7');page.locator('#preview-edit').click();until('()=>!document.getElementById("save-edit").disabled');page.locator('#save-edit').click();until('()=>profiles[0].generated.length===11')
 with page.expect_download() as d:page.get_by_role('link',name='Export MP3',exact=True).first.click()
 assert Path(d.value.path()).stat().st_size>1000
 # Full narration uses exactly the user's saved preview settings.
 settings=page.evaluate('()=>workingSettings()');full=wait_job(api('/profiles/'+profile+'/generate',{'text':'Thank you for watching. Remember to join us again for the next story.','settings':settings}));assert full['result']['settings']==settings
 until('()=>document.querySelectorAll(".history-pick").length===12');page.locator('.history-pick').first.check();page.once('dialog',lambda d:d.accept());page.locator('#delete-selected').click();until('()=>profiles[0].generated.length===11')
 page.once('dialog',lambda d:d.accept());page.locator('#clear-history').click();until('()=>profiles[0].generated.length===0');assert len(api('/profiles',method='GET')[0]['recordings'])==1
 page.reload();until('()=>token!==""&&profiles.length===1');assert api('/jobs',method='GET')==[]
 page.locator('#nav-workspace').click();page.screenshot(path='/tmp/voicecraft-workspace.png',full_page=True);page.locator('#nav-library').click();page.screenshot(path='/tmp/voicecraft-cover.png',full_page=True)
 page.set_viewport_size({'width':390,'height':850});assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1')
 assert not errors,errors
 print('Browser microphone, scripts, unsaved editing, originals, profiles, ALL real Turbo presets, generated editing, playback, MP3, full generation, deletion, restart persistence and mobile checks PASSED',flush=True);b.close()
