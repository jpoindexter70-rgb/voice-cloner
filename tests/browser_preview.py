"""Actual UI preview acceptance against an isolated server with official models.
References are AI-generated, not human family-identity evidence.
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def wait_js(page, expression, timeout=30000):
    deadline=time.monotonic()+timeout/1000
    while time.monotonic()<deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(200)
    raise AssertionError('UI readiness timed out: '+expression+' '+page.locator('#notice').inner_text())

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765/')
    wait_js(page,"() => Number(document.getElementById('profile-count').textContent)>=1")
    token=page.request.get('http://127.0.0.1:8765/api/session').json()['token']
    headers={'X-VCR-Token':token}
    reference=next(Path('.runtime/studio-data/diagnostics').glob('neural-test-*/turbo-AI-generated-reference.wav'))
    response=page.request.post('http://127.0.0.1:8765/api/profiles/my-voice/references',headers=headers,
        multipart={'consent':'true','file':{'name':'AI-reference.wav','mimeType':'audio/wav','buffer':reference.read_bytes()}})
    assert response.ok,response.text()
    response=page.request.put('http://127.0.0.1:8765/api/settings',headers=headers,data={'engine':'turbo','device':'cpu'})
    assert response.ok
    page.reload();wait_js(page,"() => Number(document.getElementById('reference-count').textContent)>=1")
    def wait_audio(previous=None):
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            jobs=page.request.get('http://127.0.0.1:8765/api/queue').json()
            jobs=[j for j in jobs if j['id'] not in (previous or set())]
            if not jobs:
                page.wait_for_timeout(250);continue
            job=jobs[-1]
            if job['status']=='complete':
                assert job['text']=='Hello family.' and job['total']==1
                audio=page.request.get('http://127.0.0.1:8765/api/assets/'+job['asset']['id']+'/audio')
                assert audio.ok and len(audio.body())>24000
                return job
            assert job['status'] not in ['failed','cancelled'],job
            page.wait_for_timeout(1000)
        raise AssertionError('Real UI preview timed out')
    page.get_by_role('button',name='Text-to-Speech Studio',exact=True).click()
    page.locator('#tts-text').fill('Hello family. This sentence must not be generated.')
    assert page.locator('#tts-preview').is_visible()
    previous={j['id'] for j in page.request.get('http://127.0.0.1:8765/api/queue').json()}
    page.locator('#tts-preview').click();tts=wait_audio(previous)
    page.get_by_role('button',name='Voice Cloning Studio',exact=True).click()
    page.locator('#script').fill('Hello family. This sentence must not be generated.')
    assert page.locator('#preview-button').is_visible()
    previous={j['id'] for j in page.request.get('http://127.0.0.1:8765/api/queue').json()}
    page.locator('#preview-button').click();cloning=wait_audio(previous)
    assert cloning['id']!=tts['id']
    page.locator('#generation-result').wait_for(state='visible',timeout=10000)
    wait_js(page,"() => document.getElementById('generated-player').readyState >= 2",timeout=20000)
    duration=page.locator('#generated-player').evaluate('(audio)=>audio.duration')
    assert duration>0
    page.get_by_role('button',name='Measure reference comparison',exact=True).click()
    wait_js(page,"() => document.getElementById('speaker-comparison-result').textContent.includes('cosine')",timeout=120000)
    page.screenshot(path='/workspace/deliverables/upgrade-preview-browser.png',full_page=True)
    assert not errors,errors
    report={'real_neural_tts_preview':True,'real_neural_cloning_preview':True,'first_sentence_only':True,
        'playable_in_app':True,'speaker_comparison_ui':True,'seconds':duration,'javascript_errors':errors,'reference_provenance':'AI-generated'}
    Path('/workspace/deliverables/upgrade-preview-browser-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2));browser.close()
