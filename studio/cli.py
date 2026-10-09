"""Download, verify, back up, diagnose, and start without deleting voice data."""
import argparse
import hashlib
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from .storage import Store, data_directory
from .engine import Engine, MODELS, verify_manifest


@contextmanager
def data_lock(root=None):
    root = Path(root or data_directory())
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / 'server.lock').open('a+b')
    handle.seek(0)
    handle.write(b'0')
    handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError('Close the studio before backup, model repair, or starting another server.') from exc
    try:
        yield
    finally:
        handle.close()


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def download(name):
    # Only this explicit command accesses model servers. No audio is involved.
    os.environ.pop('HF_HUB_OFFLINE', None)
    os.environ.pop('TRANSFORMERS_OFFLINE', None)
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    from huggingface_hub import HfApi, hf_hub_download
    engine = Engine(data_directory() / 'models')
    directory = engine.model_path(name)
    directory.mkdir(parents=True, exist_ok=True)
    info = HfApi().model_info(MODELS[name]['repo'], files_metadata=True)
    wanted = set(MODELS[name]['files'])
    if name == 'turbo':
        wanted.update(x.rfilename for x in info.siblings if '/' not in x.rfilename and x.rfilename.endswith(('.json', '.txt', '.model')))
    manifest = {'repository': info.id, 'revision': info.sha, 'files': {}}
    for item in info.siblings:
        if item.rfilename not in wanted:
            continue
        path = Path(hf_hub_download(info.id, item.rfilename, revision=info.sha, local_dir=directory))
        actual = digest(path)
        if item.lfs and item.lfs.sha256 and actual != item.lfs.sha256:
            raise RuntimeError('Model checksum mismatch: ' + item.rfilename + '. File is not trusted; retry download.')
        manifest['files'][item.rfilename] = {'sha256': actual, 'size': path.stat().st_size}
        print('Verified:', item.rfilename, flush=True)
    missing = engine.missing(name)
    if missing:
        raise RuntimeError('Repository is missing required model files: ' + ', '.join(missing))
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Downloaded', name, 'revision', info.sha)


def verify(name):
    engine = Engine(data_directory() / 'models')
    directory = engine.model_path(name)
    missing = engine.missing(name)
    if missing:
        raise RuntimeError('Missing ' + name + ' model files: ' + ', '.join(missing) + '. Run Download Models.cmd.')
    verify_manifest(directory, name)
    print('Model integrity verified:', name)


def backup(source=None, destination=None):
    source = Path(source or data_directory()).resolve()
    if not source.is_dir():
        raise RuntimeError('No existing data directory: ' + str(source))
    destination = Path(destination or (source.parent / 'VoiceControlRoom-Backups')).resolve()
    if destination == source or source in destination.parents:
        raise RuntimeError('Backup destination must be outside the source directory.')
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / ('voice-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.zip')
    files = []
    # Refuse links/junctions instead of silently omitting unknown external data.
    for directory, dirs, names in os.walk(source, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        base = Path(directory)
        for name in dirs + names:
            path = base / name
            if path.is_symlink() or (getattr(path.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
                raise RuntimeError('Backup found a link/junction: ' + str(path) + '. Preserve its target separately before repair.')
        for name in names:
            if name != 'server.lock' or base != source:
                files.append(base / name)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(source)))
    with zipfile.ZipFile(target) as archive:
        failure = archive.testzip()
        if failure or len(archive.infolist()) != len(files):
            raise RuntimeError('Backup verification failed; do not overwrite source files.')
    if os.name != 'nt':
        target.chmod(0o600)
    print('Verified backup:', target)
    print('Backups contain private audio. Keep them secure; deletion in the studio does not remove these copies.')
    return target


def serve(port, browser, load_engine):
    url = f'http://127.0.0.1:{port}/'
    # Existing-instance reuse checks exact application identity, never just an open port.
    sock = socket.socket()
    try:
        sock.bind(('127.0.0.1', port))
    except OSError:
        try:
            with urllib.request.urlopen(url + 'api/health', timeout=3) as response:
                existing = json.load(response)
            if existing.get('application') != 'voice-control-room-advanced':
                raise RuntimeError('Port is occupied by another application.')
        except Exception as exc:
            raise RuntimeError(f'Port {port} is in use and is not a verified Voice Control Room server. Close the conflicting application.') from exc
        if browser:
            webbrowser.open(url)
        print('Existing studio is running. No duplicate instance started.')
        return
    finally:
        sock.close()
    # An OS file lock closes the check/bind race and releases automatically on exit/crash.
    root = data_directory()
    root.mkdir(parents=True, exist_ok=True)
    lock_file = (root / 'server.lock').open('a+b')
    lock_file.seek(0)
    lock_file.write(b'0')
    lock_file.flush()
    lock_file.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise RuntimeError('Another studio instance is starting. Wait a moment and launch again.') from exc
    try:
        import uvicorn
        from .app import create_app
        app = create_app()
        app.state.shutdown = lambda: setattr(server, 'should_exit', True)
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='info'))
        if load_engine:
            chosen = app.state.store.settings()
            verify(chosen['engine'])
            print('Loading local voice engine; please wait. This can take several minutes on CPU.', flush=True)
            with app.state.engine.lock:
                app.state.engine.load(chosen['engine'], chosen['device'])
            print(app.state.engine.message)
        def open_when_ready():
            for _ in range(100):
                if server.started:
                    if browser:
                        webbrowser.open(url)
                    return
                if server.should_exit:
                    return
                time.sleep(.1)
        threading.Thread(target=open_when_ready, daemon=True).start()
        print('Starting private studio. Ctrl+C or Shut down studio stops the server.')
        server.run()
    finally:
        lock_file.close()


def main():
    parser = argparse.ArgumentParser(description='Voice Control Room Advanced local utilities')
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('serve')
    start.add_argument('--port', type=int, default=8765)
    start.add_argument('--no-browser', action='store_true')
    start.add_argument('--load-engine', action='store_true')
    get = commands.add_parser('download-models')
    get.add_argument('--engine', choices=[*MODELS, 'all'], default='all')
    check = commands.add_parser('verify-models')
    check.add_argument('--engine', choices=[*MODELS, 'all'], default='all')
    back = commands.add_parser('backup')
    back.add_argument('--source')
    back.add_argument('--destination')
    commands.add_parser('doctor')
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            serve(args.port, not args.no_browser, args.load_engine)
        elif args.command in ('download-models', 'verify-models'):
            with data_lock():
                for name in MODELS if args.engine == 'all' else [args.engine]:
                    (download if args.command == 'download-models' else verify)(name)
        elif args.command == 'backup':
            with data_lock():
                backup(args.source, args.destination)
        else:
            from .app import create_app
            app = create_app()
            route = next(r for r in app.routes if r.path == '/api/diagnostics')
            print(json.dumps(route.endpoint(), indent=2))
    except Exception as exc:
        print('ACTION REQUIRED:', str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
