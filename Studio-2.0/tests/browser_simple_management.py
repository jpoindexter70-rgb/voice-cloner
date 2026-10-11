"""Opt-in management browser test; run after browser_simple_voiceover.py in its isolated QA server."""
from playwright.sync_api import sync_playwright
import time,os
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 def until(js,seconds=20):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if page.evaluate(js):return
   page.wait_for_timeout(100)
  raise AssertionError(js+' :: '+page.locator('#notice').inner_text())
 page.goto(os.environ.get('STUDIO2_TEST_ORIGIN','http://127.0.0.1:8779'));until('()=>token!==""&&profiles.length>0');assert page.evaluate("()=>profiles.every(p=>['Second synthetic profile','Synthetic simple QA'].includes(p.name))"), 'Use only the isolated fixture from browser_simple_voiceover.py';page.evaluate("async()=>{for(const p of profiles){if(p.name==='Second synthetic profile')await api('/profiles/'+p.id,{method:'DELETE'});if(p.name==='Synthetic simple QA')for(const r of p.recordings)if(r.name==='Microphone.wav')await api('/profiles/'+p.id+'/references/'+r.id,{method:'DELETE'})}await refresh()}");page.locator('#add-family').click();page.locator('#name').fill('Second synthetic profile');page.locator('#own-voice').uncheck();assert page.locator('#consent-fields').is_visible();page.locator('#authorization').fill('Explicit synthetic test profile only; authorized fixture.');page.locator('#consent').check();page.get_by_role('button',name='Save Profile',exact=True).click();until('()=>profiles.length===2')
 page.locator('.card').filter(has=page.get_by_role('heading',name='Second synthetic profile',exact=True)).get_by_role('button',name='Select Voice',exact=True).click();profile=page.evaluate('()=>selected');page.locator('#record-my-voice').click();page.locator('#enable-mic').click();until('()=>document.getElementById("volume").value>0',15)
 page.evaluate('()=>stream.getAudioTracks()[0].enabled=false');until('()=>document.getElementById("volume").value===0',5);page.evaluate('()=>stream.getAudioTracks()[0].enabled=true');until('()=>document.getElementById("volume").value>0',5)
 page.locator('#start-record').click();page.wait_for_timeout(6200);page.locator('#stop-record').click();until('()=>pending!==null');page.locator('#save-record').click();until('()=>profiles.find(p=>p.id===selected).recordings.length===1');assert page.evaluate('()=>context===null&&stream===null')
 page.once('dialog',lambda d:d.accept('Recorded voice reference'));page.get_by_role('button',name='Rename Recording',exact=True).click();until('()=>profiles.find(p=>p.id===selected).recordings[0].name==="Recorded voice reference"')
 page.locator('#voice-select').select_option(label='Synthetic simple QA');until('()=>profiles.find(p=>p.id===selected).name==="Synthetic simple QA"');assert page.evaluate('()=>profiles.find(p=>p.id===selected).recordings[0].name')=='synthetic.wav'
 page.locator('#voice-select').select_option(profile);until('()=>document.querySelector("#recordings p").textContent.includes("Recorded voice reference")');page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Delete Recording',exact=True).click();until('()=>profiles.find(p=>p.id===selected).recordings.length===0')
 page.locator('#nav-library').click();page.locator('.card').filter(has=page.get_by_role('heading',name='Second synthetic profile',exact=True)).get_by_role('button',name='Edit Profile',exact=True).click();page.locator('#name').fill('Renamed synthetic profile');page.get_by_role('button',name='Save Profile',exact=True).click();until('()=>profiles.some(p=>p.name==="Renamed synthetic profile")')
 page.locator('.card').filter(has=page.get_by_role('heading',name='Renamed synthetic profile',exact=True)).locator('summary').click();page.once('dialog',lambda d:d.accept());page.locator('.card').filter(has=page.get_by_role('heading',name='Renamed synthetic profile',exact=True)).get_by_role('button',name='Delete Profile',exact=True).click();until('()=>profiles.length===1');page.reload();until('()=>profiles.length===1');assert page.evaluate('()=>profiles[0].recordings.length')==1
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 print('Browser consent, actual input silence/level response, six-second capture/save, rename/delete recording, profile switching/rename/delete, reload isolation and mobile layout PASSED',flush=True)
 b.close()
