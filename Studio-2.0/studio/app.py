"""Studio 2.0: independent, local family voice library."""
import io
import base64
import tempfile
import subprocess
import zipfile
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
import json
import os
import secrets
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from .backup import backup, restore
from .persistence import PrivateProfileStore
from pydantic import BaseModel, Field
from .engine import VoiceEngine
from .jobs import Jobs
from . import audio as audio_tools
from . import system as system_tools


def default_root():
    configured = os.getenv('STUDIO2_DATA_DIR')
    if configured:
        return Path(configured)
    if os.name == 'nt':
        root = Path('D:/AI-Voice-Cloning-Studio')
        if not Path('D:/').exists():
            raise RuntimeError('D: is unavailable. Set STUDIO2_DATA_DIR to your chosen storage location.')
        return root
    return Path(__file__).resolve().parent.parent / '.runtime'


class Profile(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    language: str = Field(default='English', max_length=80)
    accent: str = Field(default='', max_length=100)
    minor: bool = False
    authorization: str = Field(min_length=10, max_length=3000)
    consent: bool


class VoiceSettings(BaseModel):
    engine: str = Field(default='expressive', pattern='^(expressive|turbo)$')
    device: str = Field(default='auto', pattern='^(auto|cpu|cuda)$')
    speed: float = Field(default=1, ge=.5, le=2)
    pitch: float = Field(default=0, ge=-6, le=6)
    expression: float = Field(default=.5, ge=0, le=1.5)
    similarity: float = Field(default=.5, ge=0, le=1)
    temperature: float = Field(default=.8, ge=.1, le=1.5)
    pause: float = Field(default=.2, ge=0, le=2)


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    settings: VoiceSettings | None = None


class Batch(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=20)
    settings: VoiceSettings | None = None


class Comparison(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class AudioEdit(BaseModel):
    start: float = Field(default=0, ge=0)
    end: float | None = Field(default=None, gt=0)
    speed: float = Field(default=1, ge=.5, le=2)
    pitch: float = Field(default=0, ge=-6, le=6)
    denoise: bool = False


class Rating(BaseModel):
    naturalness: int = Field(ge=1, le=5)
    similarity: int = Field(ge=1, le=5)
    notes: str = Field(default='', max_length=2000)


class Settings(VoiceSettings):
    language: str = Field(max_length=80)
    accent: str = Field(max_length=100)
    speed: float = Field(default=1, ge=.5, le=2)
    name: str = Field(min_length=1, max_length=80)


class Preferences(BaseModel):
    microphone: str = Field(default='', max_length=512)
    output: str = Field(default='', max_length=512)
    input_gain: float = Field(default=1, ge=.1, le=4)
    noise_suppression: bool = False
    echo_cancellation: bool = False
    selected_profile: str = Field(default='', max_length=36)
    idle_unload_seconds: int = Field(default=300, ge=0, le=3600)


def create_app(root=None, engine=None):
    root = Path(root or default_root())
    families = root / 'family-profiles'
    families.mkdir(parents=True, exist_ok=True)
    (root / 'shared-models').mkdir(exist_ok=True)
    persistence = None
    if os.getenv('STUDIO2_BACKUP_REPO'):
        persistence = PrivateProfileStore(os.environ['STUDIO2_BACKUP_REPO'], os.getenv('STUDIO2_BACKUP_TOKEN'))
        persistence.restore(families)
    @asynccontextmanager
    async def lifespan(app):
        stopped=threading.Event()
        def release_idle_memory():
            while not stopped.wait(5):
                try:jobs.unload_if_idle(preferences()['idle_unload_seconds'])
                except (OSError,ValueError):pass
        housekeeping=threading.Thread(target=release_idle_memory,name='studio2-memory',daemon=True)
        housekeeping.start()
        try:yield
        finally:
            stopped.set();housekeeping.join();jobs.close()
    app = FastAPI(title='AI Voice Cloning Studio 2.0', lifespan=lifespan)
    voice_engine = engine or VoiceEngine(Path(os.getenv('STUDIO2_MODEL_DIR', str(root / 'shared-models'))))
    public_origin = os.getenv('STUDIO2_PUBLIC_ORIGIN', '').rstrip('/')
    password = os.getenv('STUDIO2_PASSWORD', '')
    if public_origin and (not public_origin.startswith('https://') or len(password) < 16):
        raise RuntimeError('Hosted mode requires an HTTPS STUDIO2_PUBLIC_ORIGIN and STUDIO2_PASSWORD of at least 16 characters.')
    lock = threading.RLock()
    token = secrets.token_urlsafe(32)
    static = Path(__file__).parent / 'static'

    def folder(identity):
        try:
            if str(uuid.UUID(identity)) != identity:
                raise ValueError()
        except ValueError:
            raise HTTPException(404, 'Profile not found')
        path = families / identity
        if not (path / 'settings/profile.json').is_file():
            raise HTTPException(404, 'Profile not found')
        return path

    def read(identity):
        return json.loads((folder(identity) / 'settings/profile.json').read_text())

    def write(path, data):
        target = path / 'settings/profile.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2))
        temporary.replace(target)
        if persistence:
            persistence.save(path)

    def allowed(profile):
        if profile['consent_status'] != 'authorized':
            raise HTTPException(403, 'Consent is revoked or guardian verification is pending. Voice access is locked.')

    jobs = Jobs(root, voice_engine, read, folder, write, allowed, lock)
    app.state.jobs = jobs
    app.state.engine = voice_engine
    app.state.root = root

    def require_idle(identity=None):
        if jobs.active(identity):
            raise HTTPException(409, 'Wait for this profile’s jobs to finish or cancel them first.')

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.headers.get('host', '').split(':')[0]
        allowed_hosts = ('127.0.0.1', 'localhost', 'testserver') if not public_origin else (urlsplit(public_origin).hostname,)
        if host not in allowed_hosts:
            return JSONResponse({'detail': 'Local access only'}, 403)
        if public_origin:
            valid = False
            try:
                header = request.headers.get('authorization', '')
                kind, value = header.split(' ', 1)
                username, provided = base64.b64decode(value, validate=True).decode().split(':', 1)
                valid = kind.lower() == 'basic' and secrets.compare_digest(provided.encode(), password.encode())
            except (ValueError, UnicodeError):
                pass
            if not valid:
                return JSONResponse({'detail': 'Sign in to your private studio'}, 401, headers={'WWW-Authenticate': 'Basic realm="Studio 2.0", charset="UTF-8"'})
        origin = request.headers.get('origin')
        expected_origin = public_origin or str(request.base_url).rstrip('/')
        if origin and origin != expected_origin:
            return JSONResponse({'detail': 'Cross-origin access refused'}, 403)
        if request.url.path.startswith('/api/'):
            if request.cookies.get('studio2_session') != token:
                return JSONResponse({'detail': 'Open the studio first'}, 401)
            if request.method not in ('GET', 'HEAD') and request.headers.get('x-studio-token') != token:
                return JSONResponse({'detail': 'Invalid session token'}, 403)
        response = await call_next(request)
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def index():
        response = FileResponse(static / 'index.html')
        response.set_cookie('studio2_session', token, httponly=True, samesite='strict', secure=bool(public_origin))
        return response

    @app.get('/api/session')
    def session():
        return {'token': token}

    @app.get('/api/profiles')
    def profiles():
        return [read(p.name) for p in families.iterdir() if p.is_dir() and (p / 'settings/profile.json').exists()]

    @app.post('/api/profiles')
    def add(body: Profile):
        if not body.consent or not body.name.strip() or not body.authorization.strip():
            raise HTTPException(400, 'Documented permission and a name are required')
        identity = str(uuid.uuid4())
        path = families / identity
        for part in ('original-recordings', 'references', 'voice-models', 'generated-audio', 'samples', 'settings'):
            (path / part).mkdir(parents=True)
        profile = dict(id=identity, name=body.name.strip(), language=body.language, accent=body.accent,
                       minor=body.minor, authorization=body.authorization, created_at=datetime.now(timezone.utc).isoformat(),
                       consent_status='guardian_verification_pending' if body.minor else 'authorized',
                       settings=VoiceSettings().model_dump(), recordings=[], generated=[], primary_reference=None, picture=False)
        profile['consent_history'] = [{'event':'created','authorization':body.authorization,
                                      'date':profile['created_at'],'status':profile['consent_status']}]
        write(path, profile)
        return profile

    @app.patch('/api/profiles/{identity}')
    def edit(identity: str, body: Settings):
        with lock:
            profile = read(identity)
            if not body.name.strip():
                raise HTTPException(400, 'Name cannot be blank')
            profile.update(name=body.name.strip(), language=body.language, accent=body.accent)
            profile['settings'] = VoiceSettings(**body.model_dump()).model_dump()
            write(folder(identity), profile)
            return profile

    @app.post('/api/profiles/{identity}/revoke')
    def revoke(identity: str):
        with lock:
            profile = read(identity)
            for identity_job, job in list(jobs.jobs.items()):
                if job['profile'] == identity:
                    jobs.cancel(identity_job)
            previous_status = profile['consent_status']
            profile['consent_status'] = 'revoked'
            profile['revoked_at'] = datetime.now(timezone.utc).isoformat()
            profile.setdefault('consent_history', []).append({'event':'revoked','previous_status':previous_status,
                                                             'authorization':profile['authorization'],'date':profile['revoked_at']})
            write(folder(identity), profile)
            if not jobs.active():voice_engine.unload()
        return profile

    @app.post('/api/profiles/{identity}/reauthorize')
    def reauthorize(identity: str, body: Profile):
        with lock:
            person=read(identity)
            if person['minor'] or body.minor:
                raise HTTPException(403, 'Child voices require verified guardian authorization and remain locked.')
            if not body.consent or not body.authorization.strip():
                raise HTTPException(400, 'New documented adult permission is required.')
            person.setdefault('consent_history', []).append({'event':'reauthorized','previous_status':person['consent_status'],
                                                            'previous_authorization':person['authorization'],
                                                            'authorization':body.authorization,'date':datetime.now(timezone.utc).isoformat()})
            person['authorization']=body.authorization
            person['consent_status']='authorized'
            write(folder(identity),person)
            return person

    @app.delete('/api/profiles/{identity}')
    def delete(identity: str):
        with lock:
            require_idle(identity)
            if persistence:
                persistence.delete(identity)
            shutil.rmtree(folder(identity))
            for job_id, job in list(jobs.jobs.items()):
                if job['profile'] == identity:
                    (jobs.directory / (job_id + '.json')).unlink(missing_ok=True)
                    jobs.jobs.pop(job_id)
                    jobs.cancelled.discard(job_id)
            if not jobs.active():voice_engine.unload()
        return {'deleted': True}

    @app.post('/api/profiles/{identity}/picture')
    async def picture(identity: str, file: UploadFile = File(...)):
        payload = await file.read(2_000_001)
        if len(payload) > 2_000_000:
            raise HTTPException(400, 'Use a PNG, JPEG or WebP picture under 2 MB')
        from PIL import Image, ImageOps
        try:
            with Image.open(io.BytesIO(payload)) as image:
                if image.format not in ('PNG','JPEG','WEBP') or image.width * image.height > 4_000_000:
                    raise ValueError()
                image.verify()
            with Image.open(io.BytesIO(payload)) as image:
                avatar = ImageOps.exif_transpose(image).convert('RGBA')
                avatar.thumbnail((512,512))
                normalized = io.BytesIO(); avatar.save(normalized, format='PNG')
                payload = normalized.getvalue()
        except Exception:
            raise HTTPException(400, 'Choose a valid PNG, JPEG or WebP picture up to 4 megapixels')
        with lock:
            profile = read(identity)
            (folder(identity) / 'settings/avatar.png').write_bytes(payload)
            profile['picture'] = True
            write(folder(identity), profile)
        return profile

    @app.get('/api/profiles/{identity}/picture')
    def get_picture(identity: str):
        path = folder(identity) / 'settings/avatar.png'
        if not path.exists():
            raise HTTPException(404)
        return FileResponse(path, media_type='image/png')

    @app.post('/api/evaluate')
    async def evaluate(file: UploadFile = File(...)):
        payload = await file.read(25_000_001)
        return analyze(payload)[1]

    def analyze(payload):
        if len(payload) > 25_000_000:
            raise HTTPException(400, 'Audio exceeds 25 MB')
        try:
            data, sr = audio_tools.decode(payload, root / 'temporary')
        except Exception:
            raise HTTPException(400, 'Import valid WAV, FLAC, MP3, M4A or browser-recorded audio')
        if len(data) == 0 or not np.isfinite(data).all():
            raise HTTPException(400, 'Audio is empty or invalid')
        seconds = len(data) / sr
        if not 3 <= seconds <= 120:
            raise HTTPException(400, 'Reference recordings must be 3–120 seconds')
        mono = data.mean(axis=1)
        rms = float(np.sqrt(np.mean(mono ** 2)))
        clipped = float(np.mean(np.abs(data) >= .99))
        warnings = []
        if rms < .01: warnings.append('Recording is quiet; move closer to the microphone.')
        if clipped > .001: warnings.append('Clipping detected; reduce microphone gain.')
        if seconds < 10: warnings.append('A clean 10–20 second reference is recommended.')
        return (data, sr), {'seconds': round(seconds, 2), 'sample_rate': sr, 'rms': round(rms, 4),
                             'clipped_fraction': round(clipped, 5), 'warnings': warnings,
                             'note': 'Signal checks only; this does not measure speech naturalness or speaker similarity.'}

    @app.post('/api/profiles/{identity}/references')
    async def reference(identity: str, file: UploadFile = File(...)):
        profile = read(identity)
        allowed(profile)
        payload = await file.read(25_000_001)
        (values, sample_rate), quality = analyze(payload)
        original_payload = payload
        payload = audio_tools.wav_bytes(values.mean(axis=1), sample_rate)
        asset = str(uuid.uuid4())
        with lock:
            profile = read(identity)
            allowed(profile)
            original_dir = folder(identity) / 'original-recordings'
            original_dir.mkdir(exist_ok=True)
            (original_dir / asset).write_bytes(original_payload)
            (folder(identity) / 'references' / asset).write_bytes(payload)
            record = {'id': asset, 'name': Path(file.filename or 'Recording').name[:120], 'quality': quality,
                      'created_at': datetime.now(timezone.utc).isoformat()}
            profile['recordings'].append(record)
            if not profile['primary_reference']: profile['primary_reference'] = asset
            write(folder(identity), profile)
        return profile

    @app.post('/api/profiles/{identity}/primary/{asset}')
    def primary(identity: str, asset: str):
        with lock:
            profile = read(identity); allowed(profile)
            if asset not in [r['id'] for r in profile['recordings']]:
                raise HTTPException(404, 'Recording does not belong to this profile')
            profile['primary_reference'] = asset
            write(folder(identity), profile)
        return profile

    @app.get('/api/profiles/{identity}/audio/{asset}')
    def audio(identity: str, asset: str):
        profile = read(identity); allowed(profile)
        if asset not in [r['id'] for r in profile['recordings']]: raise HTTPException(404)
        path = folder(identity) / 'references' / asset
        info = sf.info(path)
        return FileResponse(path, media_type='audio/wav' if info.format == 'WAV' else 'audio/flac')

    @app.get('/api/health')
    def health():
        return {'application': 'ai-voice-cloning-studio-2', 'status': 'running', 'recovery_warnings':jobs.recovery_warnings}

    @app.get('/api/system')
    def system_status():
        model_root = Path(os.getenv('STUDIO2_MODEL_DIR', str(root / 'shared-models')))
        result = system_tools.report(root, model_root)
        result['mode'] = 'hosted' if public_origin else 'local'
        return result

    @app.get('/api/preferences')
    def preferences():
        with lock:
            path = root / 'preferences.json'
            return Preferences(**json.loads(path.read_text())).model_dump() if path.exists() else Preferences().model_dump()

    @app.put('/api/preferences')
    def save_preferences(body: Preferences):
        with lock:
            if body.selected_profile:
                allowed(read(body.selected_profile))
            path = root / 'preferences.json'
            temporary = path.with_suffix('.tmp')
            temporary.write_text(body.model_dump_json())
            temporary.replace(path)
        return body.model_dump()

    @app.get('/api/engine')
    def engine_status():
        result=voice_engine.status()
        try:
            import torch
            result['cuda']=torch.cuda.is_available()
            if result['cuda']:
                result['gpu']=torch.cuda.get_device_name(0)
                result['vram_allocated_mb']=round(torch.cuda.memory_allocated()/1048576,1)
                result['vram_total_mb']=round(torch.cuda.get_device_properties(0).total_memory/1048576,1)
        except ImportError:result['cuda']=False
        return result

    @app.post('/api/engine/unload')
    def unload_engine():
        with lock:
            require_idle();voice_engine.unload()
            return voice_engine.status()

    def configured(identity, settings):
        person=read(identity);allowed(person)
        return (settings or VoiceSettings(**person['settings'])).model_dump()

    def ready(name):
        state=voice_engine.status()
        if not state['dependencies'] or not state['models'].get(name):
            raise HTTPException(503, 'The selected engine checkpoints or dependencies are missing. Run the separate Studio 2.0 installer to complete engine setup.')

    @app.post('/api/profiles/{identity}/compare')
    def compare(identity: str, body: Comparison):
        if not body.text.strip():raise HTTPException(400, 'Enter an audition script.')
        with lock:
            settings = configured(identity, None)
            for engine_name in ('expressive', 'turbo'):ready(engine_name)
            person = read(identity)
            reference = next((r for r in person['recordings'] if r['id'] == person['primary_reference']), None)
            if not reference or reference['quality']['seconds'] <= 5:
                raise HTTPException(400, 'Comparison needs a clean authorized reference longer than 5 seconds.')
            if person['language'].strip().lower() not in ('english', 'en'):
                raise HTTPException(400, 'Both installed synthesis engines currently support English.')
            if sum(j['status'] in ('queued', 'running') for j in jobs.jobs.values()) > 18:
                raise HTTPException(409, 'The queue needs two free slots for an engine comparison.')
            return [jobs.submit(identity, {**settings, 'engine': name}, text=body.text.strip())
                    for name in ('expressive', 'turbo')]

    @app.post('/api/profiles/{identity}/generate')
    def generate(identity: str, body: Speech):
        settings=configured(identity,body.settings)
        if not body.text.strip():raise HTTPException(400,'Enter some text.')
        ready(settings['engine'])
        try:return jobs.submit(identity,settings,text=body.text.strip())
        except ValueError as exc:raise HTTPException(400,str(exc))

    @app.post('/api/profiles/{identity}/batch')
    def batch(identity: str, body: Batch):
        settings=configured(identity,body.settings);ready(settings['engine'])
        if any(not text.strip() or len(text)>20000 for text in body.texts):raise HTTPException(400,'Each batch script must contain 1–20,000 characters.')
        with lock:
            if sum(j['status'] in ('queued','running') for j in jobs.jobs.values())+len(body.texts)>20:raise HTTPException(409,'This batch exceeds the queue limit of 20.')
            try:return [jobs.submit(identity,settings,text=text.strip()) for text in body.texts]
            except ValueError as exc:raise HTTPException(400,str(exc))

    @app.post('/api/profiles/{identity}/convert')
    async def convert(identity: str, file: UploadFile = File(...)):
        settings=configured(identity,None);ready('expressive')
        payload=await file.read(25_000_001);(values,sample_rate),quality=analyze(payload)
        if quality['seconds']>30:raise HTTPException(400,'Convert at most 30 seconds per recording on this version.')
        try:return jobs.submit(identity,settings,source=audio_tools.wav_bytes(values.mean(axis=1),sample_rate))
        except ValueError as exc:raise HTTPException(400,str(exc))

    @app.get('/api/jobs')
    def job_list():
        with lock:return list(reversed(list(jobs.jobs.values())))[:100]

    @app.post('/api/jobs/{identity}/cancel')
    def cancel(identity: str):
        try:return jobs.cancel(identity)
        except KeyError:raise HTTPException(404,'Job not found')

    @app.post('/api/jobs/{identity}/retry')
    def retry_job(identity: str):
        with lock:
            previous = jobs.jobs.get(identity)
            if previous is None:raise HTTPException(404, 'Job not found')
            if previous['status'] not in ('failed', 'interrupted', 'cancelled'):
                raise HTTPException(409, 'Only a stopped or failed job can be retried.')
            if previous['kind'] != 'speech':
                raise HTTPException(400, 'Record or import the conversion input again; temporary speech inputs are not retained.')
            configured(previous['profile'], None)
            ready(previous['settings']['engine'])
            try:
                # Settings/script are preserved; use the currently authorized reference, never a deleted asset.
                return jobs.submit(previous['profile'], previous['settings'], text=previous['text'])
            except ValueError as exc:raise HTTPException(400, str(exc))

    def generated(identity,asset):
        person=read(identity);allowed(person)
        if not any(item['id']==asset for item in person['generated']):raise HTTPException(404,'Generated audio is not in this profile')
        return folder(identity)/'generated-audio'/(asset+'.wav')

    @app.get('/api/profiles/{identity}/generated/{asset}')
    def playback_generated(identity: str,asset: str):
        return FileResponse(generated(identity,asset),media_type='audio/wav')

    @app.delete('/api/profiles/{identity}/generated/{asset}')
    def delete_generated(identity: str, asset: str):
        with lock:
            require_idle(identity)
            path = generated(identity, asset)
            person = read(identity)
            path.unlink(missing_ok=True)
            path.with_suffix('.mp3').unlink(missing_ok=True)
            person['generated'] = [item for item in person['generated'] if item['id'] != asset]
            write(folder(identity), person)
            if persistence:
                persistence.delete_generated(identity, asset)
        return {'deleted': asset}

    @app.get('/api/profiles/{identity}/originals/{asset}')
    def original_recording(identity: str, asset: str):
        person = read(identity); allowed(person)
        record = next((item for item in person['recordings'] if item['id'] == asset), None)
        if record is None:
            raise HTTPException(404, 'Recording does not belong to this profile')
        path = folder(identity) / 'original-recordings' / asset
        if not path.is_file():
            raise HTTPException(404, 'This edited reference has no imported original')
        return FileResponse(path, media_type='application/octet-stream', filename=record['name'])

    @app.get('/api/profiles/{identity}/generated/{asset}/export/{format}')
    def export(identity: str,asset: str,format: str):
        if format not in ('wav','mp3'):raise HTTPException(400,'Choose WAV or MP3')
        path=generated(identity,asset)
        if format=='wav':return FileResponse(path,media_type='audio/wav',filename='AI-generated-'+asset+'.wav')
        target=path.with_suffix('.mp3')
        with lock:
            if not target.exists():audio_tools.process(path,target)
        return FileResponse(target,media_type='audio/mpeg',filename='AI-generated-'+asset+'.mp3')

    @app.post('/api/profiles/{identity}/generated/{asset}/rating')
    def rate(identity: str,asset: str,body: Rating):
        with lock:
            generated(identity,asset);person=read(identity)
            item=next(item for item in person['generated'] if item['id']==asset)
            item['rating']=body.model_dump();write(folder(identity),person)
            return item

    @app.post('/api/profiles/{identity}/references/{asset}/edit')
    def edit_audio(identity: str,asset: str,body: AudioEdit):
        with lock:
            person=read(identity);allowed(person);require_idle(identity)
            if asset not in [r['id'] for r in person['recordings']]:raise HTTPException(404)
            source=folder(identity)/'references'/asset
            duration=sf.info(source).duration
            end=body.end if body.end is not None else duration
            if body.start>=end or end>duration+.0051:raise HTTPException(400,'Trim start/end are outside this recording.')
            end=min(end,duration)
            if (end-body.start)/body.speed<3:raise HTTPException(400,'Keep at least 3 seconds for a voice reference.')
            new_id=str(uuid.uuid4());target=folder(identity)/'references'/new_id
            temporary=folder(identity)/'references'/(new_id+'.wav')
            audio_tools.process(source,temporary,start=body.start,end=end,speed=body.speed,pitch=body.pitch,denoise=body.denoise)
            quality=analyze(temporary.read_bytes())[1];temporary.replace(target)
            person['recordings'].append({'id':new_id,'name':'Edited reference.wav','created_at':datetime.now(timezone.utc).isoformat(),'quality':quality,'original':asset})
            write(folder(identity),person)
            return person

    @app.post('/api/profiles/{identity}/references/{asset}/preview')
    def preview_edit(identity: str, asset: str, body: AudioEdit):
        with lock:
            person = read(identity); allowed(person); require_idle(identity)
            if asset not in [r['id'] for r in person['recordings']]:
                raise HTTPException(404, 'Recording does not belong to this profile')
            source = folder(identity) / 'references' / asset
            duration = sf.info(source).duration
            end = body.end if body.end is not None else duration
            if body.start >= end or end > duration+.0051 or (min(end,duration)-body.start)/body.speed < 3:
                raise HTTPException(400, 'Choose valid trim boundaries and keep at least 3 seconds.')
            end=min(end,duration)
            target = jobs.temporary / ('reference-preview-' + str(uuid.uuid4()) + '.wav')
            try:
                audio_tools.process(source, target, start=body.start, end=end, speed=body.speed,
                                    pitch=body.pitch, denoise=body.denoise)
                analyze(target.read_bytes())
            except Exception:
                target.unlink(missing_ok=True)
                raise
        return FileResponse(target, media_type='audio/wav', background=BackgroundTask(target.unlink, missing_ok=True))

    @app.delete('/api/profiles/{identity}/references/{asset}')
    def delete_reference(identity: str,asset: str):
        with lock:
            require_idle(identity);person=read(identity)
            if not any(r['id']==asset for r in person['recordings']):raise HTTPException(404)
            if persistence:
                persistence.delete_recording(identity, asset)
            (folder(identity)/'references'/asset).unlink(missing_ok=True)
            (folder(identity)/'original-recordings'/asset).unlink(missing_ok=True)
            person['recordings']=[r for r in person['recordings'] if r['id']!=asset]
            if person['primary_reference']==asset:person['primary_reference']=person['recordings'][0]['id'] if person['recordings'] else None
            write(folder(identity),person)
            return person

    @app.post('/api/storage/clear-temporary')
    def clear_temporary():
        with lock:
            require_idle();count=0
            for path in jobs.temporary.iterdir():
                if path.is_file() and path.name.endswith(('.source.wav','.work.wav')) and path.name.split('.')[0] in jobs.jobs:
                    path.unlink();count+=1
            return {'removed_files':count,'preserved':'Models, profiles, original recordings and generated audio'}

    @app.get('/api/backup')
    def export_backup():
        with lock:
            require_idle();target=jobs.temporary/('private-backup-'+str(uuid.uuid4())+'.zip')
            try:backup(families,target)
            except Exception:
                target.unlink(missing_ok=True);raise
        return FileResponse(target,media_type='application/zip',filename='Studio-2.0-private-backup.zip',background=BackgroundTask(target.unlink,missing_ok=True))

    @app.post('/api/backup/restore')
    async def restore_backup(file: UploadFile = File(...)):
        payload=await file.read(100_000_001)
        if len(payload)>100_000_000:raise HTTPException(400,'Compressed backup must be under 100 MB')
        with lock:
            require_idle()
            try:
                result=restore(io.BytesIO(payload),families)
                if persistence:
                    for profile in families.iterdir():
                        if profile.is_dir() and (profile/'settings/profile.json').exists():persistence.save(profile)
                return result
            except (ValueError,KeyError,OSError,zipfile.BadZipFile,json.JSONDecodeError) as exc:raise HTTPException(400,str(exc))

    @app.get('/api/storage')
    def storage():
        usage = shutil.disk_usage(root)
        categories = {}
        for path in root.rglob('*'):
            if path.is_file():
                part = path.relative_to(root).parts[0]
                categories[part] = categories.get(part, 0) + path.stat().st_size
        return {'path': str(root), 'used_bytes': sum(categories.values()), 'categories': categories,
                'free_bytes': usage.free, 'engine': voice_engine.status(), 'guardian_verification': 'Not implemented; child voices remain locked', 'durable_backup': persistence.repository if persistence else None}

    app.mount('/static', StaticFiles(directory=static), name='static')
    return app
