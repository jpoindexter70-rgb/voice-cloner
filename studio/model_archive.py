"""Offline import of the exact official model revisions shipped with this application."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile

from .engine import MODELS, verify_manifest


def import_archive(source, destination, name):
    if name not in MODELS:
        raise ValueError('Choose an integrated model.')
    approved = json.loads(Path(__file__).with_name('model-revisions.json').read_text())[name]
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='model-import-', dir=destination.parent) as temporary:
        staging = Path(temporary) / 'model'; staging.mkdir()
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(approved['files']) | {'manifest.json'}:
                raise ValueError('Import a complete model ZIP with files at its root and the application manifest.')
            if sum(entry.file_size for entry in archive.infolist()) > 8 * 1024**3:
                raise ValueError('Model archive exceeds the 8 GB size limit.')
            if archive.getinfo('manifest.json').file_size > 1024**2:
                raise ValueError('Model manifest is too large.')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest.get('repository') != approved['repository'] or manifest.get('revision') != approved['revision']:
                raise ValueError('This archive is not the supported official model revision.')
            for filename, expected in approved['files'].items():
                info = archive.getinfo(filename)
                sha256 = hashlib.sha256()
                blob = hashlib.sha1(b'blob ' + str(info.file_size).encode() + b'\0')
                with archive.open(filename) as src, (staging / filename).open('wb') as dest:
                    while chunk := src.read(4 * 1024 * 1024):
                        dest.write(chunk); sha256.update(chunk); blob.update(chunk)
                if ('sha256' in expected and sha256.hexdigest() != expected['sha256']) or (
                    'git_blob_sha1' in expected and blob.hexdigest() != expected['git_blob_sha1']):
                    raise ValueError('Model file does not match the independently pinned upstream hash: ' + filename)
            (staging / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        verify_manifest(staging, name)
        previous = None
        if destination.exists():
            previous = destination.with_name(destination.name + '-before-import-' + uuid.uuid4().hex)
            destination.rename(previous)
        try:
            staging.rename(destination)
        except Exception:
            if previous and not destination.exists():
                previous.rename(destination)
            raise
    return {'imported': True, 'revision': approved['revision'], 'preserved_previous_model': str(previous) if previous else None}
