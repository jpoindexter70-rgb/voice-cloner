"""Studio 2.0: independent, local family voice library."""
import io
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
from pydantic import BaseModel, Field


def default_root():
    configured = os.getenv('STUDIO2_DATA_DIR')
    if configured:
        return Path(configured)
    if os.name == 'nt':
        root = Path('D:/AI-Voice-Cloning-Studio')
        if not Path('D:/').exists():
            raise RuntimeError('D: is unavailable. Set STUDIO2_DATA_DIR to your chosen storage location.')
        return root
    return Path('/workspace/ai-voice-cloning-studio-2/.runtime')


class Profile(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    language: str = Field(default='English', max_length=80)
    accent: str = Field(default='', max_length=100)
    minor: bool = False
    authorization: str = Field(min_length=10, max_length=3000)
    consent: bool


class Settings(BaseModel):
    language: str = Field(max_length=80)
    accent: str = Field(max_length=100)
    speed: float = Field(default=1, ge=.5, le=2)
    name: str = Field(min_length=1, max_length=80)


def create_app(root=None):
    root = Path(root or default_root())
    families = root / 'family-profiles'
    families.mkdir(parents=True, exist_ok=True)
    (root / 'shared-models').mkdir(exist_ok=True)
    app = FastAPI(title='AI Voice Cloning Studio 2.0')
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

    def allowed(profile):
        if profile['consent_status'] != 'authorized':
            raise HTTPException(403, 'Consent is revoked or guardian verification is pending. Voice access is locked.')

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.headers.get('host', '').split(':')[0]
        if host not in ('127.0.0.1', 'localhost', 'testserver'):
            return JSONResponse({'detail': 'Local access only'}, 403)
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
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
        response.set_cookie('studio2_session', token, httponly=True, samesite='strict')
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
        for part in ('references', 'voice-models', 'generated-audio', 'samples', 'settings'):
            (path / part).mkdir(parents=True)
        profile = dict(id=identity, name=body.name.strip(), language=body.language, accent=body.accent,
                       minor=body.minor, authorization=body.authorization, created_at=datetime.now(timezone.utc).isoformat(),
                       consent_status='guardian_verification_pending' if body.minor else 'authorized',
                       settings={'speed': 1}, recordings=[], generated=[], primary_reference=None, picture=False)
        write(path, profile)
        return profile

    @app.patch('/api/profiles/{identity}')
    def edit(identity: str, body: Settings):
        with lock:
            profile = read(identity)
            if not body.name.strip():
                raise HTTPException(400, 'Name cannot be blank')
            profile.update(name=body.name.strip(), language=body.language, accent=body.accent)
            profile['settings']['speed'] = body.speed
            write(folder(identity), profile)
            return profile

    @app.post('/api/profiles/{identity}/revoke')
    def revoke(identity: str):
        with lock:
            profile = read(identity)
            profile['consent_status'] = 'revoked'
            profile['revoked_at'] = datetime.now(timezone.utc).isoformat()
            write(folder(identity), profile)
        return profile

    @app.delete('/api/profiles/{identity}')
    def delete(identity: str):
        with lock:
            shutil.rmtree(folder(identity))
        return {'deleted': True}

    @app.post('/api/profiles/{identity}/picture')
    async def picture(identity: str, file: UploadFile = File(...)):
        payload = await file.read(2_000_001)
        if len(payload) > 2_000_000 or not payload.startswith(b'\x89PNG\r\n\x1a\n'):
            raise HTTPException(400, 'Use a PNG picture under 2 MB')
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
            data, sr = sf.read(io.BytesIO(payload), dtype='float32', always_2d=True)
        except Exception:
            raise HTTPException(400, 'Import a valid WAV or FLAC recording')
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
        (_, _), quality = analyze(payload)
        asset = str(uuid.uuid4())
        with lock:
            profile = read(identity)
            allowed(profile)
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

    @app.post('/api/profiles/{identity}/generate')
    def generate(identity: str):
        allowed(read(identity))
        raise HTTPException(503, 'No synthesis engine is installed in Studio 2.0. Generation is unavailable; no audio was created.')

    @app.get('/api/storage')
    def storage():
        usage = shutil.disk_usage(root)
        return {'path': str(root), 'used_bytes': sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
                'free_bytes': usage.free, 'engine': 'Not installed', 'guardian_verification': 'Not implemented; child voices remain locked'}

    app.mount('/static', StaticFiles(directory=static), name='static')
    return app
