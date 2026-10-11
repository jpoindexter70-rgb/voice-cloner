"""Explicit real-model workflow acceptance; never run during ordinary startup."""
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from .app import create_app
from . import audio


def story_acceptance(root, model_root, references):
    app = create_app(root)
    app.state.engine.root = Path(model_root)
    def checked(response):
        if response.status_code != 200:
            raise RuntimeError(response.text)
        return response.json()
    with TestClient(app) as client:
        client.get('/')
        client.headers['X-VCR-Token'] = client.get('/api/session').json()['token']
        checked(client.put('/api/settings', json={'engine': 'turbo', 'device': 'cpu'}))
        speakers = []
        for index, reference in enumerate(references):
            profile = checked(client.post('/api/profiles', json={'name': f'AI acceptance speaker {index}', 'consent': True}))
            checked(client.post(f'/api/profiles/{profile["id"]}/references', files={'file': ('AI-reference.wav', Path(reference).read_bytes(), 'audio/wav')}, data={'consent': 'true'}))
            speakers.append(profile['id'])
        def wait(items):
            ids = {item['id'] for item in items}
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                current = [item for item in checked(client.get('/api/queue')) if item['id'] in ids]
                if any(item['status'] in ('failed', 'cancelled') for item in current):
                    raise RuntimeError(str(current))
                if len(current) == len(ids) and all(item['status'] == 'complete' for item in current):
                    return current
                time.sleep(.25)
            raise TimeoutError('Real neural story acceptance exceeded ten minutes.')
        project = checked(client.post('/api/projects', json={'title': 'Real neural acceptance', 'text': '# Chapter 1\nThe moon is bright.\nChild: Good night, family.\nThe house is quiet.\nChild: Tell me a story.\n# Chapter 2\nThe stars shine softly.\nChild: I see the moon.\nA little fox falls asleep.\nChild: Sweet dreams.', 'narrator': speakers[0], 'characters': {'Child': speakers[1]}}))
        ident = project['id']
        completed = wait(checked(client.post(f'/api/projects/{ident}/generate')))
        if {item['profile_id'] for item in completed} != set(speakers):
            raise RuntimeError('Character reference routing failed.')
        project = checked(client.get(f'/api/projects/{ident}'))
        old_clips = project['clips']
        if len(old_clips) != 8:
            raise RuntimeError('Story did not preserve eight sentences across two chapters.')
        preview = checked(client.post('/api/queue', json={'profile_id': speakers[0], 'text': 'A quiet night. This sentence must be excluded.', 'preview': True}))
        if preview['text'] != 'A quiet night.':
            raise RuntimeError('Preview did not restrict generation to the first sentence.')
        wait([preview])
        replacement = checked(client.post('/api/queue', json={'profile_id': speakers[0], 'text': 'The stars are bright.', 'project_id': ident, 'replace_clip': old_clips[0]['id']}))
        wait([replacement])
        revised = checked(client.get(f'/api/projects/{ident}'))
        if revised['clips'][1:] != old_clips[1:] or revised['clips'][0]['asset_id'] == old_clips[0]['asset_id']:
            raise RuntimeError('Sentence regeneration modified an unrelated clip or failed to replace audio.')
        app.state.store.asset(old_clips[0]['asset_id'])
        if not checked(client.get(f'/api/projects/{ident}/versions')):
            raise RuntimeError('Sentence regeneration did not retain history.')
        for fmt in ('wav', 'mp3'):
            response = client.get(f'/api/projects/{ident}/export/{fmt}')
            if response.status_code != 200:
                raise RuntimeError(response.text)
            target = Path(root) / ('accepted-story.' + fmt)
            target.write_bytes(response.content)
            decoded = Path(root) / ('accepted-' + fmt + '-decoded.wav')
            audio.decode(target, decoded)
            wave, sr = sf.read(decoded)
            if len(wave) / sr < 1 or not np.isfinite(wave).all() or np.sqrt(np.mean(wave ** 2)) < .001:
                raise RuntimeError('Export is invalid or silent.')
        for fmt in ('srt', 'vtt'):
            response = client.get(f'/api/projects/{ident}/captions/{fmt}')
            if response.status_code != 200 or '-->' not in response.text:
                raise RuntimeError('Timed caption export failed.')
        comparison = checked(client.post('/api/assets/'+revised['clips'][0]['asset_id']+'/similarity'))
        if not -1 <= comparison['cosine'] <= 1:
            raise RuntimeError('Real speaker comparison failed.')
        reference = app.state.store.profile(speakers[0])['primary_asset']
        checked(client.delete('/api/assets/'+reference))
        checked(client.post('/api/recovery/'+reference+'/restore'))
        if app.state.store.profile(speakers[0])['primary_asset'] != reference:
            raise RuntimeError('Reference recovery failed.')
        app.state.engine.unload()
    reopened = create_app(root)
    if len(reopened.state.workspace.project(ident)['clips']) != 8:
        raise RuntimeError('Saved story did not survive reopening.')
    return {'real_neural_story': True, 'independent_reference_routing': True,
            'sentence_regeneration': True, 'short_preview': True, 'wav_mp3_decode': True,
            'captions': True, 'history_and_reopen': True, 'story_sentences': 8, 'story_chapters': 2,
            'speaker_encoder_comparison': comparison, 'reference_recovery': True,
            'reference_provenance': 'AI-generated references; human family similarity unrun'}
