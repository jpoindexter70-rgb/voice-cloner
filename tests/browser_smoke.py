"""Browser integration with synthetic microphone; NOT a Windows/device/voice test."""
import json
import time
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright

def wait_js(page, expression):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(100)
    raise AssertionError('Timed out: ' + expression + '\nNotice: ' + page.locator('#notice').inner_text())

speaker = 'Browser Test ' + uuid.uuid4().hex[:8]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
        args=['--autoplay-policy=no-user-gesture-required','--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
    context = browser.new_context(permissions=['microphone'], viewport={'width':1440,'height':1000},accept_downloads=True)
    page = context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:8765/')
    wait_js(page, "() => document.getElementById('profile-count').textContent !== '—'")
    page.screenshot(path='/tmp/voice-control-room-dashboard.png',full_page=True)
    for name in ['My Voice','Record Voice','Voice Cloning Studio','Family Voice Library','Recording Editor','Settings and Diagnostics','Local AI Engine Manager','Dashboard']:
        page.get_by_role('button',name=name,exact=True).first.click()
        page.wait_for_timeout(100)
    page.get_by_role('button',name='Family Voice Library',exact=True).click()
    page.locator('#profile-name').fill(speaker)
    page.locator('#profile-consent').check()
    page.get_by_role('button',name='Create profile',exact=True).click()
    page.get_by_role('heading',name=speaker,exact=True).wait_for()
    page.get_by_role('button',name='Record Voice',exact=True).click()
    page.locator('#record-profile').select_option(label=speaker)
    page.locator('#microphone-enable').click()
    wait_js(page, "() => document.querySelectorAll('#microphone option').length > 1")
    page.locator('#record-countdown').select_option('5')
    page.locator('#record-start').click()
    page.get_by_role('button',name='Cancel countdown',exact=True).click()
    assert page.locator('#record-state').inner_text() == 'READY TO RECORD'
    assert page.locator('#record-start').is_enabled()
    page.locator('#record-start').click()
    assert page.locator('#record-state').inner_text().startswith('STARTING IN')
    wait_js(page, "() => document.getElementById('record-state').textContent === 'RECORDING'")
    wait_js(page, "() => parseFloat(document.getElementById('input-level').style.width) > 0")
    page.wait_for_timeout(3500)
    page.locator('#record-pause').click()
    assert page.locator('#record-state').inner_text()=='PAUSED'
    page.wait_for_timeout(300)
    page.locator('#record-pause').click()
    page.wait_for_timeout(3500)
    page.locator('#record-stop').click()
    wait_js(page, "() => !document.getElementById('record-save').disabled")
    page.locator('#record-consent').check()
    page.locator('#record-save').click()
    wait_js(page, "() => document.getElementById('reference-count').textContent !== '0'")
    page.get_by_role('button',name='Family Voice Library',exact=True).click()
    card = page.locator('article.card').filter(has=page.get_by_role('heading',name=speaker,exact=True))
    audio = card.locator('audio').first
    audio.evaluate('(a)=>a.play()')
    wait_js(page, "() => [...document.querySelectorAll('audio')].some(a => !a.paused && a.currentTime > 0)")
    page.wait_for_timeout(400)
    assert audio.evaluate('(a)=>a.currentTime')>0
    audio.evaluate('(a)=>a.pause()')
    card.get_by_role('button',name='Edit',exact=True).click()
    wait_js(page, "() => Number(document.getElementById('trim-end').value)>6")
    page.locator('#trim-start').fill('0.2')
    page.locator('#trim-end').fill('6')
    page.locator('#apply-edit').click()
    wait_js(page, "() => [...document.querySelectorAll('#edit-asset option')].some(o=>o.textContent.includes('edited'))")
    with page.expect_download() as download:
        page.locator('#edit-wav').click()
    downloaded=download.value
    assert downloaded.suggested_filename.endswith('.wav')
    assert Path(downloaded.path()).stat().st_size>1000
    with page.expect_download() as download:
        page.locator('#edit-mp3').click()
    assert Path(download.value.path()).stat().st_size>1000
    page.get_by_role('button',name='Voice Cloning Studio',exact=True).click()
    page.locator('#generate-profile').select_option(label=speaker)
    page.locator('#script').fill('Testing a useful missing-model diagnostic.')
    page.get_by_role('button',name='My Voice',exact=True).click()
    page.locator('#test-my-voice').click()
    assert page.locator('#generate-profile').input_value()=='my-voice'
    page.locator('#generate-profile').select_option(label=speaker)
    page.locator('#generate-button').click()
    wait_js(page, "() => document.getElementById('notice').textContent.includes('not installed')")
    page.get_by_role('button',name='Settings and Diagnostics',exact=True).click()
    page.locator('#setting-engine').select_option('turbo')
    page.get_by_role('button',name='Save settings',exact=True).click()
    wait_js(page, "() => document.getElementById('cfg').disabled")
    page.locator('#setting-engine').select_option('chatterbox')
    page.get_by_role('button',name='Save settings',exact=True).click()
    wait_js(page, "() => !document.getElementById('cfg').disabled")
    page.get_by_role('button',name='Family Voice Library',exact=True).click()
    card=page.locator('article.card').filter(has=page.get_by_role('heading',name=speaker,exact=True))
    card.get_by_role('button',name='Delete profile',exact=True).click()
    page.locator('#confirm-yes').click()
    page.get_by_role('heading',name=speaker,exact=True).wait_for(state='detached')
    assert not errors,errors
    print(json.dumps({'browser':'system Chromium on Linux','navigation':8,'fake_microphone_record_pause_resume_save':True,'five_second_countdown':True,'live_level_response':True,'playback':True,'editing':True,'wav_mp3_downloads':True,'profile_create_delete':True,'missing_model_error':True,'unsupported_turbo_controls_disabled':True,'javascript_errors':errors},indent=2))
    browser.close()
