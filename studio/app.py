import os
# Prevent inference from making network calls. Downloads use the separate CLI.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')

import importlib.metadata
import json
import secrets
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from typing import Literal

from .storage import Store, data_directory
from .engine import Engine, segments
from . import audio


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['adult', 'child'] = 'adult'
    consent: bool = False
    guardian: str = Field(default='', max_length=100)


class RenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SettingsIn(BaseModel):
    engine: Literal['chatterbox', 'turbo'] = 'chatterbox'
    device: Literal['auto', 'cpu', 'cuda'] = 'auto'


class GenerationIn(BaseModel):
    profile_id: str = 'my-voice'
    text: str = Field(min_length=1, max_length=20000)
    temperature: float = Field(default=.8, ge=.1, le=1.2)
    exaggeration: float = Field(default=.5, ge=0, le=1)
    cfg_weight: float = Field(default=.5, ge=0, le=1)
    pause_ms: int = Field(default=180, ge=0, le=1500)


class EditIn(BaseModel):
    start: float = Field(default=0, ge=0)
    end: float | None = Field(default=None, gt=0)
    remove_silence: bool = False
    denoise: bool = False
    speed: float = Field(default=1, ge=.5, le=2)
    pitch: float = Field(default=0, ge=-6, le=6)


class ReviewIn(BaseModel):
    similarity: int = Field(ge=1, le=5)
    naturalness: int = Field(ge=1, le=5)
    pronunciation: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    consistency: int = Field(ge=1, le=5)
    notes: str = Field(default='', max_length=2000)


def memory_status():
    if os.name == 'nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                        ('total_physical', ctypes.c_ulonglong), ('available_physical', ctypes.c_ulonglong),
                        ('total_page', ctypes.c_ulonglong), ('available_page', ctypes.c_ulonglong),
                        ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                        ('available_extended', ctypes.c_ulonglong)]
        status = Memory()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {'total_gb': round(status.total_physical / 1024**3, 1), 'available_gb': round(status.available_physical / 1024**3, 1)}
    elif hasattr(os, 'sysconf'):
        return {'total_gb': round(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / 1024**3, 1),
                'available_gb': round(os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / 1024**3, 1)}
    return {'message': 'Physical memory status unavailable on this platform.'}


def create_app(root=None):
    app = FastAPI(title='Voice Control Room Advanced', docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])
    store = Store(root or data_directory())
    engine = Engine(store.root / 'models')
    jobs = {}
    jobs_lock = threading.Lock()
    mutation_lock = threading.RLock()
    token = secrets.token_urlsafe(32)
    app.state.store, app.state.engine, app.state.jobs = store, engine, jobs
    app.state.shutdown = None

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        origin = request.headers.get('origin')
        allowed_origin = str(request.base_url).rstrip('/')
        if origin and origin != allowed_origin:
            return JSONResponse({'detail': 'Only same-origin local access is permitted.'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Cross-site access denied.'}, status_code=403)
        if request.url.path.startswith('/api/') and request.url.path != '/api/health':
            if request.cookies.get('vcr_session') != token:
                return JSONResponse({'detail': 'Open the local studio in your browser first.'}, status_code=401)
            if request.method not in ('GET', 'HEAD') and request.headers.get('x-vcr-token') != token:
                return JSONResponse({'detail': 'Local session token missing.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.exception_handler(RuntimeError)
    async def runtime(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=503)

    static = Path(__file__).parent / 'static'
    app.mount('/static', StaticFiles(directory=static), name='static')

    @app.get('/')
    def index():
        response = FileResponse(static / 'index.html')
        response.set_cookie('vcr_session', token, httponly=True, samesite='strict')
        return response

    @app.get('/api/health')
    def health():
        return {'application': 'voice-control-room-advanced', 'version': '1.0.0', 'status': 'running'}

    @app.get('/api/session')
    def session():
        return {'token': token}

    @app.get('/api/profiles')
    def profiles():
        return store.profiles()

    @app.post('/api/profiles')
    def new_profile(body: ProfileIn):
        if not body.consent:
            raise ValueError('Explicit speaker permission is required.')
        if body.kind == 'child' and not body.guardian.strip():
            raise ValueError('Parent or guardian authorization is required for a child.')
        if not body.name.strip():
            raise ValueError('Enter a speaker name.')
        return store.create_profile(body.name.strip(), body.kind,
                                    'Parent/guardian: ' + body.guardian.strip() if body.kind == 'child' else 'Speaker authorized enrollment')

    @app.patch('/api/profiles/{ident}')
    def rename(ident: str, body: RenameIn):
        if not body.name.strip():
            raise ValueError('Enter a profile name.')
        store.rename(ident, body.name.strip())
        return store.profile(ident)

    def idle():
        with jobs_lock:
            if any(j['status'] in ('queued', 'running') for j in jobs.values()) or engine.lock.locked():
                raise HTTPException(409, 'Wait for engine work to finish before changing or deleting recordings.')

    @app.delete('/api/profiles/{ident}')
    def delete_profile(ident: str):
        with mutation_lock:
            idle()
            store.delete_profile(ident)
            with engine.lock:
                engine.unload()
        return {'deleted': True, 'notice': 'Active local recordings deleted. Separately remove any exported files and backups.'}

    @app.get('/api/assets')
    def assets(profile_id: str | None = None):
        return store.assets(profile_id)

    @app.post('/api/profiles/{ident}/references')
    def upload(ident: str, file: UploadFile = File(...), consent: bool = Form(False)):
        store.profile(ident)
        if not consent:
            raise ValueError('Confirm permission to store this speaker’s recording.')
        asset_id = uuid.uuid4().hex
        dest = store.path(asset_id)
        try:
            with tempfile.TemporaryDirectory(prefix='vcr-upload-') as directory:
                source = Path(directory) / 'upload'
                total = 0
                with source.open('wb') as out:
                    while chunk := file.file.read(1024 * 1024):
                        total += len(chunk)
                        if total > 100 * 1024 * 1024:
                            raise ValueError('Upload exceeds 100 MB.')
                        out.write(chunk)
                metadata = audio.decode(source, dest)
            return store.add_asset(asset_id, ident, Path(file.filename or 'Recording').name[:120], 'reference', metadata)
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        finally:
            file.file.close()

    @app.post('/api/profiles/{ident}/primary/{asset_id}')
    def primary(ident: str, asset_id: str):
        store.set_primary(ident, asset_id)
        return store.profile(ident)

    @app.delete('/api/assets/{ident}')
    def delete_asset(ident: str):
        with mutation_lock:
            idle()
            store.delete_asset(ident)
            with engine.lock:
                engine.unload()
        return {'deleted': True}

    @app.get('/api/assets/{ident}/audio')
    def play(ident: str):
        asset = store.asset(ident)
        prefix = 'AI-generated-' if asset['kind'] == 'generated' else 'Recording-'
        return FileResponse(store.path(ident), media_type='audio/wav', filename=prefix + ident[:8] + '.wav')

    @app.get('/api/assets/{ident}/waveform')
    def peaks(ident: str):
        store.asset(ident)
        return audio.waveform(store.path(ident))

    @app.get('/api/assets/{ident}/export/{fmt}')
    def export(ident: str, fmt: Literal['wav', 'mp3']):
        asset = store.asset(ident)
        if fmt == 'wav':
            return play(ident)
        with tempfile.NamedTemporaryFile(suffix='.mp3', prefix='vcr-export-', delete=False) as handle:
            temp = Path(handle.name)
        try:
            audio.export_mp3(store.path(ident), temp, synthetic=asset['kind'] == 'generated')
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        prefix = 'AI-generated-' if asset['kind'] == 'generated' else 'Recording-'
        return FileResponse(temp, media_type='audio/mpeg', filename=prefix + ident[:8] + '.mp3', background=BackgroundTask(temp.unlink, missing_ok=True))

    @app.post('/api/assets/{ident}/edit')
    def edit(ident: str, body: EditIn):
        original = store.asset(ident)
        new_id = uuid.uuid4().hex
        dest = store.path(new_id)
        try:
            metadata = audio.edit(store.path(ident), dest, **body.model_dump())
            metadata = {**original['metadata'], **metadata, 'source_asset': ident, 'processing': body.model_dump()}
            if original['kind'] == 'generated':
                metadata['synthetic'] = True
            # Preserve synthetic identity and original reference. No destructive edits.
            return store.add_asset(new_id, original['profile_id'], original['name'] + ' · edited', original['kind'], metadata)
        except Exception:
            dest.unlink(missing_ok=True)
            raise

    @app.get('/api/settings')
    def settings():
        return store.settings()

    @app.put('/api/settings')
    def set_settings(body: SettingsIn):
        with mutation_lock:
            idle()
            store.save_settings(body.model_dump())
            with engine.lock:
                engine.unload()
        return store.settings()

    @app.get('/api/engine')
    def engine_status():
        return engine.status()

    def update_job(ident, **kwargs):
        with jobs_lock:
            jobs[ident].update(kwargs)

    def worker(ident, body, reference, chosen):
        output_id = uuid.uuid4().hex
        dest = store.path(output_id)
        try:
            with engine.lock:
                update_job(ident, status='running')
                wave, sr = engine.generate(body.text, reference, chosen, body,
                    lambda done, total: update_job(ident, completed=done, total=total),
                    lambda: jobs[ident]['cancel'])
                sf.write(dest, wave, sr, subtype='PCM_16')
                metadata = audio.analyze(wave, sr)
                metadata.update({'synthetic': True, 'text': body.text, 'reference_id': reference.stem,
                                 'engine': chosen['engine'], 'device': engine.device, 'controls': body.model_dump(),
                                 'package_version': engine.status()['package_version'], 'checkpoint_revision': engine.revision})
                asset = store.add_asset(output_id, body.profile_id, 'AI-generated · ' + body.text[:60], 'generated', metadata)
                update_job(ident, status='complete', asset=asset)
        except Exception as exc:
            dest.unlink(missing_ok=True)
            engine.message = str(exc)
            update_job(ident, status='cancelled' if jobs[ident]['cancel'] else 'failed', error=str(exc))

    @app.post('/api/generate')
    def generate(body: GenerationIn):
        if not body.text.strip():
            raise ValueError('Enter text to generate.')
        parts = segments(body.text)
        with mutation_lock:
            idle()
            profile = store.profile(body.profile_id)
            if not profile['primary_asset']:
                raise ValueError('Add and choose a reference recording first.')
            reference = store.path(profile['primary_asset'])
            asset = store.asset(profile['primary_asset'])
            if asset['metadata']['seconds'] < 6:
                raise ValueError('Choose a reference with at least 6 seconds of clear speech.')
            chosen = store.settings()
            if engine.missing(chosen['engine']):
                raise RuntimeError('Selected model is not installed. Run Download Models.cmd, then load the engine.')
            ident = uuid.uuid4().hex
            with jobs_lock:
                # Bound memory retained for progress/history; assets remain on disk.
                finished = [k for k, j in jobs.items() if j['status'] not in ('queued', 'running')]
                for key in finished[:-20]:
                    jobs.pop(key, None)
                jobs[ident] = {'id': ident, 'status': 'queued', 'completed': 0, 'total': len(parts), 'cancel': False}
            threading.Thread(target=worker, args=(ident, body, reference, chosen), daemon=True).start()
        return {'id': ident}

    @app.get('/api/jobs/{ident}')
    def job(ident: str):
        with jobs_lock:
            if ident not in jobs:
                raise HTTPException(404, 'Job not found; see saved recordings after restart.')
            return dict(jobs[ident])

    @app.post('/api/jobs/{ident}/cancel')
    def cancel(ident: str):
        with jobs_lock:
            if ident not in jobs:
                raise HTTPException(404, 'Job not found.')
            jobs[ident]['cancel'] = True
        return {'notice': 'Cancellation will take effect after the current segment.'}

    @app.post('/api/engine/load')
    def warmup():
        with mutation_lock:
            idle()
            chosen = store.settings()
            # Reserve before starting thread so simultaneous requests cannot queue loads.
            if not engine.lock.acquire(blocking=False):
                raise HTTPException(409, 'Engine busy.')
            engine.message = 'Loading model…'
            def load():
                try:
                    engine.load(chosen['engine'], chosen['device'])
                except Exception as exc:
                    engine.message = str(exc)
                finally:
                    engine.lock.release()
            threading.Thread(target=load, daemon=True).start()
        return {'loading': True}

    @app.post('/api/assets/{ident}/review')
    def review(ident: str, body: ReviewIn):
        store.review(ident, body.model_dump())
        return {'saved': True}

    @app.get('/api/reviews')
    def reviews():
        return store.reviews()

    @app.get('/api/diagnostics')
    def diagnostics():
        packages = {}
        for name in ['fastapi', 'uvicorn', 'soundfile', 'numpy', 'torch', 'torchaudio', 'chatterbox-tts', 'resemble-perth', 'setuptools']:
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = None
        gpu = {'available': False, 'message': 'PyTorch not installed.'}
        if packages['torch']:
            try:
                import torch
                gpu = {'available': torch.cuda.is_available(), 'torch_cuda': torch.version.cuda}
                if gpu['available']:
                    gpu.update(name=torch.cuda.get_device_name(0), vram_gb=round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2))
            except Exception as exc:
                gpu['message'] = str(exc)
        try:
            ff = audio.ffmpeg()
        except Exception as exc:
            ff = str(exc)
        return {'data_directory': str(store.root), 'free_disk_gb': round(shutil.disk_usage(store.root).free / 1024**3, 1),
                'packages': packages, 'gpu': gpu, 'ffmpeg': ff, 'engine': engine.status(),
                'privacy': 'Inference is offline. No cloud audio uploads. Bound to loopback by launcher.',
                'repair': 'Close the studio and run Install or Repair.cmd. This preserves the data directory. Download Models.cmd repairs model files.',
                'memory': memory_status(),
                'unindexed_recordings': len([p for p in store.audio.glob('*.wav') if p.stem not in {a['id'] for a in store.assets()}]),
                'missing_recordings': [a['id'] for a in store.assets() if not store.path(a['id']).is_file()],
                'microphone': 'Browser permission and device test are available in Voice Recorder; cannot be inspected by the server.'}

    @app.post('/api/shutdown')
    def shutdown():
        with mutation_lock:
            idle()
            if app.state.shutdown:
                app.state.shutdown()
        return {'stopping': True}

    return app
