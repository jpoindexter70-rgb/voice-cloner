"""Persistent profile preferences, pronunciation, projects, history and resumable jobs."""
import copy
import io
import json
import re
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from . import audio
from .engine import segments
from .storage import now


class VoiceControls(BaseModel):
    pitch: float = Field(default=0, ge=-6, le=6)
    speed: float = Field(default=1, ge=.5, le=2)
    volume: float = Field(default=1, ge=0, le=2)
    pause_ms: int = Field(default=180, ge=0, le=1500)
    exaggeration: float = Field(default=.5, ge=0, le=1)
    cfg_weight: float = Field(default=.5, ge=0, le=1)
    temperature: float = Field(default=.8, ge=.1, le=1.2)
    normalize: bool = False


PRESETS = {
    'Storytelling': {'speed': .95, 'exaggeration': .6, 'pause_ms': 300},
    'Bedtime Reading': {'speed': .85, 'volume': .85, 'exaggeration': .3, 'pause_ms': 450},
    'Energetic Character': {'speed': 1.1, 'exaggeration': .8, 'pause_ms': 120},
    'Calm Narration': {'speed': .95, 'exaggeration': .3, 'pause_ms': 300},
}


class PreferencesIn(BaseModel):
    controls: VoiceControls = Field(default_factory=VoiceControls)
    language: str = Field(default='en', max_length=20)
    pronunciation: dict[str, str] = Field(default_factory=dict)
    presets: dict[str, VoiceControls] = Field(default_factory=dict)


class TimelineClip(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    asset_id: str | None = None
    start: float = Field(default=0, ge=0, le=14400)
    trim_start: float = Field(default=0, ge=0, le=14400)
    duration: float | None = Field(default=None, gt=0, le=14400)
    volume: float = Field(default=1, ge=0, le=2)
    role: str = Field(default='speech', pattern='^(speech|music|effect|pause)$')
    text: str = Field(default='', max_length=20000)


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    text: str = Field(default='', max_length=100000)
    narrator: str = 'my-voice'
    characters: dict[str, str] = Field(default_factory=dict)
    clips: list[TimelineClip] = Field(default_factory=list, max_length=500)
    duck_music: bool = True


class QueueIn(BaseModel):
    profile_id: str = 'my-voice'
    reference_id: str | None = None
    text: str = Field(min_length=1, max_length=20000)
    controls: VoiceControls | None = None
    project_id: str | None = None
    replace_clip: str | None = None
    preview: bool = False


class Workspace:
    def __init__(self, store):
        self.store = store
        with store.connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS voice_preferences (profile_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS project_versions (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS generation_queue (id TEXT PRIMARY KEY, data TEXT NOT NULL, created TEXT NOT NULL);
            ''')

    def preferences(self, profile_id):
        self.store.profile(profile_id)
        with self.store.connect() as c:
            row = c.execute('SELECT data FROM voice_preferences WHERE profile_id=?', (profile_id,)).fetchone()
        data = PreferencesIn.model_validate(json.loads(row['data'])).model_dump() if row else PreferencesIn().model_dump()
        data['builtin_presets'] = {name: VoiceControls(**controls).model_dump() for name, controls in PRESETS.items()}
        return data

    def save_preferences(self, profile_id, data):
        self.store.profile(profile_id)
        if data.language != 'en':
            raise ValueError('The integrated Original and Turbo engines support English. Other languages are not enabled.')
        if len(data.pronunciation) > 500 or any(not k.strip() or len(k) > 100 or not v.strip() or len(v) > 200
                                               for k, v in data.pronunciation.items()):
            raise ValueError('Use at most 500 nonempty pronunciation replacements (100/200 characters each).')
        if len(data.presets) > 100 or any(not name.strip() or len(name) > 80 for name in data.presets):
            raise ValueError('Use at most 100 named presets with names up to 80 characters.')
        with self.store.connect() as c:
            c.execute('INSERT INTO voice_preferences VALUES (?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data',
                      (profile_id, data.model_dump_json()))
        return self.preferences(profile_id)

    def pronounce(self, profile_id, text):
        replacements = self.preferences(profile_id)['pronunciation']
        if not replacements:
            return text
        pattern = r'(?<!\w)(?:' + '|'.join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)) + r')(?!\w)'
        lower = {k.lower(): v for k, v in replacements.items()}
        return re.sub(pattern, lambda m: lower[m.group().lower()], text, flags=re.IGNORECASE)

    def project(self, ident):
        with self.store.connect() as c:
            row = c.execute('SELECT * FROM projects WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise ValueError('Project not found.')
        return {'id': ident, **json.loads(row['data']), 'updated': row['updated']}

    def projects(self):
        with self.store.connect() as c:
            return [{'id': r['id'], **json.loads(r['data']), 'updated': r['updated']}
                    for r in c.execute('SELECT * FROM projects ORDER BY updated DESC')]

    def save_project(self, data, ident=None):
        self.store.profile(data.narrator)
        for person in data.characters.values():
            self.store.profile(person)
        for clip in data.clips:
            if clip.role != 'pause':
                if not clip.asset_id:
                    raise ValueError('Audio clips require a saved recording.')
                self.store.asset(clip.asset_id)
            elif not clip.duration:
                raise ValueError('Pause clips require a duration.')
        ident = ident or uuid.uuid4().hex
        with self.store.connect() as c:
            old = c.execute('SELECT data FROM projects WHERE id=?', (ident,)).fetchone()
            if old:
                c.execute('INSERT INTO project_versions VALUES (?,?,?,?)', (uuid.uuid4().hex, ident, old['data'], now()))
            c.execute('INSERT INTO projects VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated=excluded.updated',
                      (ident, data.model_dump_json(), now()))
        return self.project(ident)

    def history(self, ident):
        self.project(ident)
        with self.store.connect() as c:
            return [{'id': r['id'], 'created': r['created'], 'project': json.loads(r['data'])}
                    for r in c.execute('SELECT * FROM project_versions WHERE project_id=? ORDER BY created DESC', (ident,))]

    def restore_version(self, ident, version):
        with self.store.connect() as c:
            row = c.execute('SELECT data FROM project_versions WHERE project_id=? AND id=?', (ident, version)).fetchone()
        if not row:
            raise ValueError('Version does not belong to this project.')
        return self.save_project(ProjectIn.model_validate_json(row['data']), ident)

    def attach_generation(self, project_id, asset, text, replace=None):
        data = ProjectIn.model_validate(self.project(project_id))
        clip = TimelineClip(asset_id=asset['id'], text=text, duration=asset['metadata']['seconds'])
        if replace:
            index = next((i for i, c in enumerate(data.clips) if c.id == replace), None)
            if index is None:
                raise ValueError('The sentence clip was removed while generating. Audio remains in the recording library.')
            clip.start = data.clips[index].start
            clip.id = replace
            data.clips[index] = clip
        else:
            clip.start = max((c.start + (c.duration or self.store.asset(c.asset_id)['metadata']['seconds'])
                              for c in data.clips), default=0)
            data.clips.append(clip)
        self.save_project(data, project_id)

    def render(self, ident, target):
        project = self.project(ident)
        if not project['clips']:
            raise ValueError('Add audio or generate story sentences before exporting.')
        rate = 24000
        prepared, length = [], 0
        for item in project['clips']:
            clip = TimelineClip(**item)
            if clip.role == 'pause':
                samples = np.zeros(int(clip.duration * rate), dtype=np.float32)
            else:
                path = self.store.path(clip.asset_id)
                if not path.is_file():
                    raise ValueError('A timeline recording is missing. Restore it from backup.')
                samples, sr = sf.read(path, dtype='float32')
                if sr != rate:
                    from scipy.signal import resample_poly
                    from math import gcd
                    factor = gcd(sr, rate)
                    samples = resample_poly(samples, rate // factor, sr // factor)
                start = int(clip.trim_start * rate)
                end = start + int(clip.duration * rate) if clip.duration else len(samples)
                if start >= len(samples) or end > len(samples) + 24:
                    raise ValueError('Timeline trim exceeds the recording duration.')
                samples = samples[start:min(end, len(samples))] * clip.volume
            offset = int(clip.start * rate)
            length = max(length, offset + len(samples))
            prepared.append((clip, offset, samples))
        if length > 3600 * rate:
            raise ValueError('Export chapters separately; each rendered timeline is limited to one hour.')
        speech = np.zeros(length, dtype=np.float32)
        other = np.zeros(length, dtype=np.float32)
        music = np.zeros(length, dtype=np.float32)
        for clip, offset, samples in prepared:
            dest = speech if clip.role == 'speech' else music if clip.role == 'music' else other
            dest[offset:offset + len(samples)] += samples
        if project['duck_music']:
            # Smooth 50ms energy envelope; 150ms lookaround reduces rapid pumping.
            hop = 1200
            active = np.array([np.sqrt(np.mean(speech[i:i + hop] ** 2)) > .008 for i in range(0, length, hop)])
            expanded = np.convolve(active.astype(float), np.ones(7), mode='full')[3:3 + len(active)] > 0
            gains = np.where(expanded, .25, 1.0)
            envelope = np.interp(np.arange(length), np.arange(len(gains)) * hop, gains).astype(np.float32)
            music *= envelope
        result = speech + music + other
        peak = np.max(np.abs(result)) if len(result) else 0
        if peak > .98:
            result *= .98 / peak
        sf.write(target, result, rate, subtype='PCM_16')
        return audio.analyze(result, rate)

    def captions(self, ident, fmt):
        project = self.project(ident)
        def stamp(seconds):
            ms = round(seconds * 1000)
            hours, ms = divmod(ms, 3600000)
            minutes, ms = divmod(ms, 60000)
            sec, ms = divmod(ms, 1000)
            return f'{hours:02}:{minutes:02}:{sec:02}' + (',' if fmt == 'srt' else '.') + f'{ms:03}'
        result = [] if fmt == 'srt' else ['WEBVTT', '']
        for clip in sorted(project['clips'], key=lambda c: c['start']):
            if clip['role'] != 'speech' or not clip['text'].strip():
                continue
            duration = clip['duration'] or self.store.asset(clip['asset_id'])['metadata']['seconds']
            result += [str(sum(1 for line in result if '-->' in line) + 1),
                       stamp(clip['start']) + ' --> ' + stamp(clip['start'] + duration),
                       clip['text'].replace('-->', '→').replace('\r', '').replace('\n', ' '), '']
        return '\n'.join(result) + '\n'


class PersistentQueue:
    def __init__(self, workspace, engine, jobs, jobs_lock, mutation_lock, generation_model):
        self.workspace, self.store, self.engine = workspace, workspace.store, engine
        self.jobs, self.jobs_lock, self.mutation_lock = jobs, jobs_lock, mutation_lock
        self.generation_model = generation_model
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = threading.RLock()
        # Recover actual persisted work. Active jobs require explicit Resume after a crash.
        for item in self.list():
            if item['status'] in ('running', 'queued'):
                item.update(status='interrupted', error='Application closed before completion. Resume uses saved segment checkpoints.')
                self.save(item)

    def list(self):
        with self.store.connect() as c:
            return [json.loads(r['data']) for r in c.execute('SELECT * FROM generation_queue ORDER BY created')]

    def get(self, ident):
        return next((item for item in self.list() if item['id'] == ident), None)

    def save(self, item):
        with self.lock:
            with self.store.connect() as c:
                c.execute('INSERT INTO generation_queue VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                          (item['id'], json.dumps(item), item['created']))
            with self.jobs_lock:
                self.jobs[item['id']] = {**item, 'cancel': item.get('cancel', False)}

    def submit(self, body):
        profile = self.store.profile(body.profile_id)
        reference_id = body.reference_id or profile['primary_asset']
        if not reference_id:
            raise ValueError('Record or upload a reference first.')
        reference = self.store.asset(reference_id)
        if reference['profile_id'] != body.profile_id or reference['kind'] != 'reference':
            raise ValueError('Select a reference belonging to this speaker.')
        if not self.store.path(reference_id).is_file() or reference['metadata']['seconds'] < 6:
            raise ValueError('Choose an available reference with at least six seconds of clear speech.')
        settings = self.store.settings()
        if self.engine.missing(settings['engine']):
            raise ValueError('Download the selected model in Local AI Engine Manager first.')
        if body.project_id:
            self.workspace.project(body.project_id)
        controls = body.controls or VoiceControls(**self.workspace.preferences(body.profile_id)['controls'])
        original = body.text.strip()
        if not original:
            raise ValueError('Enter text to generate.')
        if body.preview:
            original = re.split(r'(?<=[.!?])\s+', original)[0][:240]
        text = self.workspace.pronounce(body.profile_id, original)
        parts = segments(text)
        item = {'id': uuid.uuid4().hex, 'created': now(), 'status': 'queued', 'completed': 0,
                'total': len(parts), 'parts': parts, 'text': original, 'profile_id': body.profile_id,
                'reference_id': reference_id, 'settings': settings, 'controls': controls.model_dump(),
                'project_id': body.project_id, 'replace_clip': body.replace_clip, 'cancel': False}
        self.save(item)
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.run, name='generation-queue', daemon=True)
            self.thread.start()
        self.wake.set()
        return item

    def cancel(self, ident):
        with self.lock:
            item = self.get(ident)
            if not item:
                raise ValueError('Queued job not found.')
            item['cancel'] = True
            if item['status'] != 'running':
                item['status'] = 'cancelled'
            self.save(item)
        return item

    def resume(self, ident):
        with self.lock:
            item = self.get(ident)
            if not item or item['status'] not in ('failed', 'interrupted', 'cancelled'):
                raise ValueError('Only failed, interrupted or cancelled jobs can be resumed.')
            self.store.profile(item['profile_id'])
            reference = self.store.asset(item['reference_id'])
            if reference['profile_id'] != item['profile_id'] or not self.store.path(reference['id']).is_file():
                raise ValueError('The original speaker reference is no longer available. Import a new reference and create a new job.')
            item.update(status='queued', cancel=False, error=None)
            self.save(item)
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.run, name='generation-queue', daemon=True)
            self.thread.start()
        self.wake.set()
        return item

    def run(self):
        while not self.stop_event.is_set():
            pending = next((j for j in self.list() if j['status'] == 'queued'), None)
            if not pending:
                self.wake.wait(1); self.wake.clear(); continue
            with self.engine.lock:
                if any(j['status'] == 'running' and j['id'] != pending['id'] for j in list(self.jobs.values())):
                    continue
                self.process(pending)

    def process(self, item):
        directory = self.store.root / 'checkpoints' / item['id']
        directory.mkdir(parents=True, exist_ok=True)
        ident = uuid.uuid4().hex
        target = self.store.path(ident)
        try:
            latest = self.get(item['id'])
            if latest['cancel']:
                return
            item.update(status='running', error=None)
            self.save(item)
            control = VoiceControls(**item['controls'])
            waves, rate = [], None
            for index, text in enumerate(item['parts']):
                if self.get(item['id'])['cancel'] or self.stop_event.is_set():
                    raise InterruptedError('Generation cancelled; completed segments are saved for Resume.')
                checkpoint = directory / f'{index:04}.wav'
                if checkpoint.is_file():
                    wave, sr = sf.read(checkpoint, dtype='float32')
                else:
                    request = self.generation_model(profile_id=item['profile_id'], text=text,
                        temperature=control.temperature, exaggeration=control.exaggeration,
                        cfg_weight=control.cfg_weight, pause_ms=control.pause_ms)
                    wave, sr = self.engine.generate(text, self.store.path(item['reference_id']), item['settings'], request,
                        lambda done, total: None, lambda: self.get(item['id'])['cancel'] or self.stop_event.is_set())
                    partial = checkpoint.with_suffix('.partial.wav')
                    sf.write(partial, wave, sr, subtype='PCM_16'); partial.replace(checkpoint)
                if rate is not None and rate != sr:
                    raise ValueError('Checkpoint sample rate changed; start a new job.')
                rate = sr
                waves.append(wave)
                if index < len(item['parts']) - 1:
                    waves.append(np.zeros(round(sr * control.pause_ms / 1000), dtype=np.float32))
                item['completed'] = index + 1
                item['cancel'] = self.get(item['id'])['cancel']
                self.save(item)
            if self.get(item['id'])['cancel']:
                raise InterruptedError('Generation cancelled; Resume retains completed segments.')
            sf.write(target, np.concatenate(waves), rate, subtype='PCM_16')
            if control.pitch or control.speed != 1:
                processed = target.with_suffix('.processing.wav')
                audio.edit(target, processed, 0, None, False, False, control.speed, control.pitch)
                processed.replace(target)
            x, sr = sf.read(target, dtype='float32')
            if control.normalize:
                peak = np.max(np.abs(x))
                if peak > 0:
                    x *= .95 / peak
            x = np.clip(x * control.volume, -1, 1)
            sf.write(target, x, sr, subtype='PCM_16')
            metadata = {**audio.analyze(x, sr), 'synthetic': True, 'text': item['text'],
                'reference_id': item['reference_id'], 'engine': item['settings']['engine'],
                'controls': item['controls'], 'checkpoint_revision': self.engine.revision}
            asset = self.store.add_asset(ident, item['profile_id'], 'AI-generated · ' + item['text'][:60], 'generated', metadata)
            item.update(status='complete', asset=asset, cancel=False)
            if item['project_id']:
                with self.mutation_lock:
                    self.workspace.attach_generation(item['project_id'], asset, item['text'], item['replace_clip'])
        except Exception as exc:
            if not self.store.path(ident).is_file() or not any(a['id'] == ident for a in self.store.assets()):
                target.unlink(missing_ok=True)
            item.update(status='cancelled' if self.get(item['id'])['cancel'] else 'failed', error=str(exc))
        self.save(item)


def register_workflows(app, store, engine, jobs, jobs_lock, mutation_lock, idle, generation_model):
    workspace = Workspace(store)
    queue = PersistentQueue(workspace, engine, jobs, jobs_lock, mutation_lock, generation_model)
    app.state.workspace, app.state.queue = workspace, queue

    @app.get('/api/profiles/{ident}/preferences')
    def preferences(ident: str):
        return workspace.preferences(ident)

    @app.put('/api/profiles/{ident}/preferences')
    def save_preferences(ident: str, body: PreferencesIn):
        return workspace.save_preferences(ident, body)

    @app.get('/api/projects')
    def projects():
        return workspace.projects()

    @app.post('/api/projects')
    def create_project(body: ProjectIn):
        with mutation_lock:
            return workspace.save_project(body)

    @app.get('/api/projects/{ident}')
    def project(ident: str):
        return workspace.project(ident)

    @app.put('/api/projects/{ident}')
    def save_project(ident: str, body: ProjectIn):
        with mutation_lock:
            workspace.project(ident)
            return workspace.save_project(body, ident)

    @app.get('/api/projects/{ident}/versions')
    def versions(ident: str):
        return workspace.history(ident)

    @app.post('/api/projects/{ident}/restore/{version}')
    def restore(ident: str, version: str):
        with mutation_lock:
            return workspace.restore_version(ident, version)

    @app.get('/api/projects/{ident}/captions/{fmt}')
    def captions(ident: str, fmt: str):
        if fmt not in ('srt', 'vtt'):
            raise ValueError('Choose SRT or VTT captions.')
        return Response(workspace.captions(ident, fmt), media_type='text/plain; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="captions.{fmt}"'})

    @app.get('/api/projects/{ident}/export/{fmt}')
    def export_project(ident: str, fmt: str):
        import tempfile
        from starlette.background import BackgroundTask
        if fmt not in ('wav', 'mp3'):
            raise ValueError('Choose WAV or MP3.')
        with mutation_lock:
            temporary = Path(tempfile.mkdtemp(prefix='family-story-'))
            try:
                wave = temporary / 'story.wav'
                workspace.render(ident, wave)
                target = wave if fmt == 'wav' else temporary / 'story.mp3'
                if fmt == 'mp3':
                    audio.export_mp3(wave, target, synthetic=True)
                return FileResponse(target, filename='AI-generated-story.' + fmt,
                    media_type='audio/wav' if fmt == 'wav' else 'audio/mpeg',
                    background=BackgroundTask(shutil.rmtree, temporary))
            except Exception:
                shutil.rmtree(temporary); raise

    @app.post('/api/queue')
    def submit(body: QueueIn):
        with mutation_lock:
            return queue.submit(body)

    @app.get('/api/queue')
    def queue_list():
        return queue.list()

    @app.post('/api/queue/{ident}/cancel')
    def cancel(ident: str):
        return queue.cancel(ident)

    @app.post('/api/queue/{ident}/resume')
    def resume(ident: str):
        with mutation_lock:
            return queue.resume(ident)

    @app.post('/api/projects/{ident}/generate')
    def generate_story(ident: str):
        with mutation_lock:
            project = workspace.project(ident)
            entries = []
            for paragraph in project['text'].splitlines():
                paragraph = paragraph.strip()
                if not paragraph or paragraph.startswith('#'):
                    continue
                speaker = project['narrator']
                if ':' in paragraph:
                    character, dialogue = paragraph.split(':', 1)
                    if character in project['characters']:
                        speaker, paragraph = project['characters'][character], dialogue.strip()
                for sentence in re.split(r'(?<=[.!?])\s+', paragraph):
                    if sentence:
                        entries.append(QueueIn(profile_id=speaker, text=sentence, project_id=ident))
            if not entries:
                raise ValueError('Write story text first. Use # Chapter headings and Character: dialogue.')
            if len(entries) > 500:
                raise ValueError('Generate fewer than 500 sentences at once.')
            # Validate all voices/references before queuing the first operation.
            for entry in entries:
                profile = store.profile(entry.profile_id)
                if not profile['primary_asset']:
                    raise ValueError('Add a reference for ' + profile['name'] + ' first.')
                ref = store.asset(profile['primary_asset'])
                if ref['metadata']['seconds'] < 6 or not store.path(ref['id']).is_file():
                    raise ValueError('A story speaker needs an available six-second reference.')
            return [queue.submit(entry) for entry in entries]

    @app.get('/api/backup')
    def backup_data():
        import hashlib
        import tempfile
        from starlette.background import BackgroundTask
        with mutation_lock:
            idle()
            temporary = Path(tempfile.mkdtemp(prefix='family-backup-'))
            try:
                import sqlite3
                snapshot = temporary / 'database.sqlite3'
                with store.connect() as source, sqlite3.connect(snapshot) as target:
                    source.backup(target)
                entries = {'database.sqlite3': snapshot}
                for asset in store.assets():
                    path = store.path(asset['id'])
                    if not path.is_file():
                        raise ValueError('A recording is missing. Restore it before making a complete backup.')
                    entries['audio/' + path.name] = path
                for path in (store.root / 'checkpoints').glob('*/*.wav'):
                    if not path.name.endswith('.partial.wav'):
                        entries[path.relative_to(store.root).as_posix()] = path
                manifest = {'format': 'family-voice-backup-v1', 'created': now(), 'files': {}}
                archive = temporary / 'family-voice-backup.zip'
                with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as zipped:
                    for name, path in entries.items():
                        digest = hashlib.sha256()
                        with path.open('rb') as source, zipped.open(name, 'w', force_zip64=True) as target:
                            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                                digest.update(chunk); target.write(chunk)
                        manifest['files'][name] = digest.hexdigest()
                    zipped.writestr('manifest.json', json.dumps(manifest))
                return FileResponse(archive, filename='Family-Voice-Backup.zip', media_type='application/zip',
                    background=BackgroundTask(shutil.rmtree, temporary))
            except Exception:
                shutil.rmtree(temporary); raise

    @app.post('/api/restore')
    def restore_backup(file: UploadFile = File(...)):
        import hashlib
        import sqlite3
        import tempfile
        from .storage import Store
        with mutation_lock:
            idle()
            with tempfile.TemporaryDirectory(prefix='family-restore-') as folder:
                temporary = Path(folder)
                archive = temporary / 'input.zip'
                count = 0
                try:
                    with archive.open('wb') as out:
                        while chunk := file.file.read(1024 * 1024):
                            count += len(chunk)
                            if count > 2 * 1024**3:
                                raise ValueError('Backup exceeds the 2 GB restore limit. Restore larger archives through diagnostics support.')
                            out.write(chunk)
                    staging = temporary / 'staging'; staging.mkdir()
                    with zipfile.ZipFile(archive) as zipped:
                        names = zipped.namelist()
                        if len(names) != len(set(names)) or len(names) > 20000:
                            raise ValueError('Duplicate or excessive backup entries.')
                        if sum(x.file_size for x in zipped.infolist()) > 4 * 1024**3:
                            raise ValueError('Uncompressed backup exceeds the 4 GB limit.')
                        if zipped.getinfo('manifest.json').file_size > 5 * 1024**2:
                            raise ValueError('Backup manifest is too large.')
                        manifest = json.loads(zipped.read('manifest.json'))
                        if manifest.get('format') != 'family-voice-backup-v1' or set(names) != set(manifest['files']) | {'manifest.json'}:
                            raise ValueError('Use a complete backup produced by this application.')
                        for name, expected in manifest['files'].items():
                            if name != 'database.sqlite3' and not re.fullmatch(r'(audio/[a-f0-9]{32}\.wav|checkpoints/[a-f0-9]{32}/[0-9]{4}\.wav)', name):
                                raise ValueError('Unsafe or unsupported archive path.')
                            target = staging / name; target.parent.mkdir(parents=True, exist_ok=True)
                            digest = hashlib.sha256()
                            with zipped.open(name) as source, target.open('wb') as dest:
                                while chunk := source.read(1024 * 1024):
                                    digest.update(chunk);dest.write(chunk)
                            if digest.hexdigest() != expected:
                                raise ValueError('Backup integrity check failed: ' + name)
                    database = staging / 'database.sqlite3'
                    if not database.is_file() or not Store.compatible(database):
                        raise ValueError('Backup database is missing or incompatible.')
                    with sqlite3.connect(database) as c:
                        if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                            raise ValueError('Backup database failed SQLite integrity checks.')
                        assets = c.execute('SELECT id FROM assets').fetchall()
                        for (ident,) in assets:
                            if not re.fullmatch('[a-f0-9]{32}', ident) or not (staging / 'audio' / (ident + '.wav')).is_file():
                                raise ValueError('Backup is missing a recording.')
                    # Preserve the complete current state before restoring anything.
                    preserved = store.root.parent / ('VoiceControlRoom-before-restore-' + uuid.uuid4().hex)
                    preserved.mkdir(mode=0o700)
                    with store.connect() as source, sqlite3.connect(preserved / store.db.name) as dest:
                        source.backup(dest)
                    shutil.copytree(store.audio, preserved / 'audio')
                    if (store.root / 'checkpoints').exists():
                        shutil.copytree(store.root / 'checkpoints', preserved / 'checkpoints')
                    with engine.lock:
                        engine.unload()
                        # Audio files use immutable IDs. Keep originals not present in the restored backup.
                        for path in (staging / 'audio').glob('*.wav'):
                            shutil.copy2(path, store.audio / path.name)
                        for path in (staging / 'checkpoints').glob('*/*.wav'):
                            target = store.root / path.relative_to(staging);target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(path, target)
                        with sqlite3.connect(database) as source, store.connect() as dest:
                            source.backup(dest)
                        Workspace(store)
                        with jobs_lock:
                            jobs.clear()
                        for item in queue.list():
                            if item['status'] in ('queued', 'running'):
                                item.update(status='interrupted', error='Restored from backup. Resume explicitly to continue.')
                                queue.save(item)
                    return {'restored': True, 'preserved_current_data': str(preserved),
                            'notice': 'Profiles, recordings, settings, projects and queue restored. Previous data was preserved separately.'}
                except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
                    raise ValueError('Invalid or incomplete backup archive.') from exc
                finally:
                    file.file.close()

    return workspace, queue
