"""Standard-library backup: visible progress, stable inventory, and one bounded retry."""
import argparse
import os
import sys
import time
import zipfile
from pathlib import Path
from datetime import datetime


class SourceChanged(RuntimeError):
    pass


def fingerprint(stat):
    return stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_dev


def inventory(source):
    files = {}
    reported = time.monotonic()
    for directory, dirs, names in os.walk(source, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        for name in dirs + names:
            path = Path(directory) / name
            stat = path.stat(follow_symlinks=False)
            if path.is_symlink() or (getattr(stat, 'st_file_attributes', 0) & 0x400):
                raise RuntimeError(f'Link/junction found: {path}. Preserve its target separately; installation stopped.')
            if name in names and (name != 'server.lock' or Path(directory) != source):
                files[path.relative_to(source).as_posix()] = fingerprint(stat)
        if time.monotonic() - reported >= 2:
            print('Scanning... found', len(files), 'files so far.', flush=True)
            reported = time.monotonic()
    return files


def backup_attempt(source, destination):
    print('Scanning existing files for backup:', source, flush=True)
    files = inventory(source)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = destination / (source.name + '-' + stamp + '.zip')
    partial = target.with_suffix('.incomplete.zip')
    total = sum(details[0] for details in files.values())
    print(f'Backing up {len(files)} files ({total / 1024**3:.2f} GB). Source files will remain unchanged.', flush=True)
    completed = 0
    reported = time.monotonic()
    try:
        with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for index, (name, expected) in enumerate(files.items(), 1):
                file = source / name
                info = zipfile.ZipInfo.from_file(file, name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info._compresslevel = 1  # Python 3.11 has no public compress_level field.
                with file.open('rb') as original:
                    if fingerprint(os.fstat(original.fileno())) != expected:
                        raise SourceChanged('File changed after scanning: ' + str(file))
                    with archive.open(info, 'w', force_zip64=True) as saved:
                        while chunk := original.read(1024 * 1024):
                            saved.write(chunk)
                            completed += len(chunk)
                            if time.monotonic() - reported >= 2:
                                print(f'Backup progress: {completed / 1024**3:.2f} / {total / 1024**3:.2f} GB; file {index}/{len(files)}.', flush=True)
                                reported = time.monotonic()
                    if fingerprint(os.fstat(original.fileno())) != expected:
                        raise SourceChanged('File changed while being copied: ' + str(file))
        print('Backup copied. Verifying every archived file before continuing...', flush=True)
        verified = 0
        reported = time.monotonic()
        with zipfile.ZipFile(partial) as archive:
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
                # ZipFile verifies CRC at EOF, not merely the number of entries.
        print('Checking that source files stayed unchanged during backup...', flush=True)
        if inventory(source) != files:
            raise SourceChanged('The source file inventory changed during backup.')
        partial.rename(target)
    except Exception:
        if partial.exists():
            print('Incomplete archive retained for recovery:', partial, flush=True)
            print('This incomplete archive is NOT a verified full backup.', flush=True)
        raise
    print('VERIFIED BACKUP:', target, flush=True)
    print('Inventory:', len(files), 'files. Source files unchanged.', flush=True)
    return target


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents:
        raise RuntimeError('Backup destination is inside the installation.')
    destination.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            return backup_attempt(source, destination)
        except (FileNotFoundError, SourceChanged) as exc:
            print('BACKUP SOURCE CHANGED OR DISAPPEARED:', str(exc), flush=True)
            if attempt == 1:
                raise RuntimeError('Backup could not capture stable source files. Close all other installers and applications using this folder, restart Windows, and retry. No source files were deleted.') from exc
            print('Refreshing the inventory and retrying once. Missing files are not silently skipped; any existing incomplete archive is retained.', flush=True)


def verify_existing(source, destination):
    """Revalidate a previous archive; does not claim it captures current changes."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    candidates = [p for p in destination.glob(source.name + '-*.zip')
                  if not p.name.endswith('.incomplete.zip')]
    if not candidates:
        raise RuntimeError('No previous backup archive for ' + str(source) + '. Use Install or Repair.cmd instead.')
    # Filenames carry the creation timestamp; copying an older ZIP must not make it newest.
    target = max(candidates, key=lambda p: p.name)
    print('Rechecking previous backup:', target, flush=True)
    checked = 0
    reported = time.monotonic()
    with zipfile.ZipFile(target) as archive:
        entries = archive.infolist()
        total = sum(entry.file_size for entry in entries)
        if source.is_dir() and any(source.iterdir()) and not entries:
            raise RuntimeError('Previous archive is empty. Use Install or Repair.cmd.')
        for index, entry in enumerate(entries, 1):
            with archive.open(entry) as file:
                while chunk := file.read(1024 * 1024):
                    checked += len(chunk)
                    if time.monotonic() - reported >= 2:
                        print(f'Archive verification: {checked / 1024**3:.2f} / {total / 1024**3:.2f} GB; file {index}/{len(entries)}.', flush=True)
                        reported = time.monotonic()
    print('PREVIOUS ARCHIVE INTEGRITY VERIFIED:', target, flush=True)
    print('This preserves the earlier backup state, not files changed since that backup.', flush=True)
    return target


def main():
    parser = argparse.ArgumentParser(description='Back up files or recheck a prior archive to resume installation.')
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    if args.verify_existing:
        verify_existing(args.source, args.destination)
    else:
        backup(args.source, args.destination)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BACKUP FAILED:', str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
