"""Standard-library-only backup, usable before dependencies are installed."""
import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime


def main():
    source, destination = [Path(arg).resolve() for arg in sys.argv[1:3]]
    if source == destination or source in destination.parents:
        raise RuntimeError('Backup destination is inside the installation.')
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / (source.name + '-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.zip')
    files = []
    for directory, dirs, names in os.walk(source, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        for name in dirs + names:
            path = Path(directory) / name
            if path.is_symlink() or (getattr(path.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
                raise RuntimeError(f'Link/junction found: {path}. Preserve its target separately; installation stopped.')
        files.extend(Path(directory) / name for name in names if name != 'server.lock' or Path(directory) != source)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for file in files:
            archive.write(file, file.relative_to(source))
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() or len(archive.infolist()) != len(files):
            raise RuntimeError('Backup verification failed. Installation stopped.')
    print('VERIFIED BACKUP:', target)
    print('Inventory:', len(files), 'files. Source files unchanged.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BACKUP FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
