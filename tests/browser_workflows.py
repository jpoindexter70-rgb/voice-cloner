"""Real Linux browser/UI workflows with an uploaded synthetic audio fixture."""
import io
import json
import uuid
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from playwright.sync_api import sync_playwright

def wait_js(page, expression):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(100)
    raise AssertionError('UI readiness timed out: ' + expression + '\n' + page.locator('#notice').inner_text())

name='Workflow Test '+uuid.uuid4().hex[:8]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,
        args=['--autoplay-policy=no-user-gesture-required','--no-sandbox'])
    page=browser.new_page(accept_downloads=True,viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('dialog',lambda dialog:dialog.accept())
    page.goto('http://127.0.0.1:8765/')
    wait_js(page, "() => Number(document.getElementById('profile-count').textContent)>=1")
    for title in ['Text-to-Speech Studio','Voice Adjustments','Pronunciation Editor','Story Creator',
                  'Audio Timeline Editor','Recording Library','Projects and History','Generation Queue']:
        page.get_by_role('button',name=title,exact=True).click()
    page.get_by_role('button',name='Family Voice Library',exact=True).click()
    page.locator('#profile-name').fill(name);page.locator('#profile-consent').check()
    page.get_by_role('button',name='Create profile',exact=True).click()
    page.get_by_role('heading',name=name,exact=True).wait_for()
    card=page.locator('article.card').filter(has=page.get_by_role('heading',name=name,exact=True))
    card.get_by_role('button',name='Edit profile',exact=True).click()
    card.locator('.detail-accent').fill('Family reference accent')
    import base64
    photo=io.BytesIO(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='))
    card.locator('.detail-picture').set_input_files({'name':'family.png','mimeType':'image/png','buffer':photo.getvalue()})
    card.get_by_role('button',name='Save profile',exact=True).click()
    wait_js(page, "() => document.getElementById('notice').textContent.includes('Profile details saved')")
    page.reload()
    page.get_by_role('button',name='Family Voice Library',exact=True).click()
    card.get_by_role('button',name='Edit profile',exact=True).click()
    assert card.locator('.detail-accent').input_value() == 'Family reference accent'
    assert card.get_by_role('img').get_attribute('src').startswith('data:image/png;base64,')
    page.get_by_role('button',name='Record Voice',exact=True).click()
    first_script=page.locator('#guided-script-text').inner_text()
    page.locator('#guided-script-next').click()
    assert page.locator('#guided-script-text').inner_text() != first_script
    page.locator('#guided-script').select_option('bedtime')
    assert 'moon' in page.locator('#guided-script-text').inner_text()
    page.get_by_role('button',name='Family Voice Library',exact=True).click()
    stream=io.BytesIO();sf.write(stream,.1*np.sin(np.arange(240000)*.05),24000,format='WAV')
    card.get_by_label('Add reference recording').set_input_files({'name':'workflow-tone.wav','mimeType':'audio/wav','buffer':stream.getvalue()})
    card.get_by_label('I have authorization to store this speaker’s audio.').check();card.get_by_role('button',name='Upload reference',exact=True).click()
    card.get_by_text('workflow-tone.wav',exact=True).first.wait_for()
    page.get_by_role('button',name='Voice Adjustments',exact=True).click()
    page.locator('#controls-profile').select_option(label=name)
    wait_js(page, "() => document.getElementById('voice-speed').value === '1'")
    page.locator('#voice-speed').fill('0.9');page.locator('#voice-volume').fill('0.8')
    page.get_by_role('button',name='Save voice settings',exact=True).click()
    wait_js(page, "() => document.getElementById('notice').textContent.includes('Voice settings saved')")
    page.get_by_role('button',name='Reset defaults',exact=True).click()
    wait_js(page, "() => document.getElementById('voice-speed').value === '1'")
    page.reload()
    page.get_by_role('button',name='Voice Adjustments',exact=True).click()
    page.locator('#controls-profile').select_option(label=name)
    wait_js(page, "() => document.getElementById('voice-volume').value === '1'")
    page.get_by_role('button',name='Pronunciation Editor',exact=True).click()
    page.locator('#pronunciation-profile').select_option(label=name)
    page.wait_for_timeout(250);page.locator('#pronunciation-rules').fill('Matthew = Math-yoo')
    page.get_by_role('button',name='Save pronunciation dictionary',exact=True).click()
    wait_js(page, "() => document.getElementById('notice').textContent.includes('Pronunciation dictionary saved')")
    page.get_by_role('button',name='Projects and History',exact=True).click()
    page.get_by_role('button',name='New story project',exact=True).click()
    page.locator('#story-title').fill(name);page.locator('#story-text').fill('# Chapter 1\nA saved family story.\nAlice: Hello Matthew.')
    page.locator('#story-narrator').select_option(label=name)
    page.locator('#character-voices select').select_option(label=name)
    page.get_by_role('button',name='Save story',exact=True).click()
    wait_js(page, "() => document.getElementById('notice').textContent.includes('Story and voice assignments saved')")
    page.get_by_role('button',name='Open timeline',exact=True).click()
    wait_js(page, "() => document.getElementById('timeline-project').value !== ''")
    page.locator('#timeline-asset').select_option(label='workflow-tone.wav')
    page.locator('#timeline-duration').fill('2');page.get_by_role('button',name='Add to timeline',exact=True).click()
    page.get_by_role('button',name='Save timeline',exact=True).click()
    wait_js(page, "() => document.querySelectorAll('.timeline-clip').length === 1")
    with page.expect_download() as download:page.locator('#story-wav').click()
    assert Path(download.value.path()).stat().st_size>1000
    with page.expect_download() as download:page.locator('#story-mp3').click()
    assert Path(download.value.path()).stat().st_size>1000
    page.screenshot(path='/tmp/family-voice-timeline.png',full_page=True)
    page.get_by_role('button',name='Settings and Diagnostics',exact=True).click()
    with page.expect_download() as download:page.get_by_role('link',name='Save verified backup ZIP').click()
    assert Path(download.value.path()).stat().st_size>1000
    # Remove only this test profile; archive/project fixtures remain isolated in the test directory.
    page.get_by_role('button',name='Family Voice Library',exact=True).click()
    card=page.locator('article.card').filter(has=page.get_by_role('heading',name=name,exact=True))
    card.get_by_role('button',name='Delete profile',exact=True).click();page.locator('#confirm-yes').click()
    page.get_by_role('heading',name=name,exact=True).wait_for(state='detached')
    assert not errors,errors
    print(json.dumps({'new_navigation':8,'profile_controls':True,'pronunciation':True,
        'story_voice_assignment':True,'timeline_edit':True,'timeline_wav_mp3_export':True,
        'backup_download':True,'profile_details_and_picture':True,'guided_scripts':True,
        'reset_settings_persistence':True,'javascript_errors':errors,'real_synthesis':'unrun'},indent=2))
    browser.close()
