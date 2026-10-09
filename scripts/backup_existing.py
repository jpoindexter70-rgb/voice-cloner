"""Standard-library-only backup with visible progress, before dependency installation."""
import os
import sys
import time
import zipfile
from pathlib import Path
from datetime import datetime


def main():
    source, destination = [Path(arg).resolve() for arg in sys.argv[1:3]]
    if source == destination or source in destination.parents:
        raise RuntimeError('Backup destination is inside the installation.')
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / (source.name + '-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.zip')
    print('Scanning existing files for backup:', source, flush=True)
    files = []
    reported = time.monotonic()
    for directory, dirs, names in os.walk(source, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        for name in dirs + names:
            path = Path(directory) / name
            if path.is_symlink() or (getattr(path.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
                raise RuntimeError(f'Link/junction found: {path}. Preserve its target separately; installation stopped.')
        files.extend(Path(directory) / name for name in names if name != 'server.lock' or Path(directory) != source)
        if time.monotonic() - reported >= 2:
            print('Scanning... found', len(files), 'files so far.', flush=True)
            reported = time.monotonic()
    total = sum(file.stat().st_size for file in files)
    print(f'Backing up {len(files)} files ({total / 1024**3:.2f} GB). Source files will remain unchanged.', flush=True)
    completed = 0
    reported = time.monotonic()
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for index, file in enumerate(files, 1):
            # Stream in bounded chunks so even a single large model file shows progress.
            info = zipfile.ZipInfo.from_file(file, file.relative_to(source))
            info.compress_type = zipfile.ZIP_DEFLATED
            info._compresslevel = 1  # Python 3.11 ZipInfo has no public compress_level attribute.
            with file.open('rb') as original, archive.open(info, 'w', force_zip64=True) as saved:
                while chunk := original.read(1024 * 1024):
                    saved.write(chunk)
                    completed += len(chunk)
                    if time.monotonic() - reported >= 2:
                        print(f'Backup progress: {completed / 1024**3:.2f} / {total / 1024**3:.2f} GB; file {index}/{len(files)}.', flush=True)
                        reported = time.monotonic()
    print('Backup copied. Verifying every archived file before continuing...', flush=True)
    verified = 0
    reported = time.monotonic()
    with zipfile.ZipFile(target) as archive:
        entries = archive.infolist()
        if len(entries) != len(files):
            raise RuntimeError('Backup verification failed. Installation stopped.')
        for index, entry in enumerate(entries, 1):
            with archive.open(entry) as saved:
                while chunk := saved.read(1024 * 1024):
                    verified += len(chunk)
                    if time.monotonic() - reported >= 2:
                        print(f'Verification progress: {verified / 1024**3:.2f} / {total / 1024**3:.2f} GB; file {index}/{len(entries)}.', flush=True)
                        reported = time.monotonic()
            # ZipFile validates the file CRC when its contents reach EOF.
    print('VERIFIED BACKUP:', target, flush=True)
    print('Inventory:', len(files), 'files. Source files unchanged.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BACKUP FAILED:', str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
