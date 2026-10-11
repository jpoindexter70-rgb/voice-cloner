"""Private, checksum-verified profile archives without model duplication."""
import hashlib
import json
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path,PurePosixPath


def backup(families,target):
    manifest={'format':'studio2-private-backup-v2','files':{}}
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for path in sorted(Path(families).rglob('*')):
            if path.is_symlink():raise ValueError('Backup refuses filesystem links; preserve their targets separately.')
            if not path.is_file():continue
            relative=path.relative_to(families).as_posix()
            # Per-profile adaptations can be large and are deliberate user data; shared base models live outside this tree.
            digest=hashlib.sha256()
            with path.open('rb') as source,z.open(relative,'w') as out:
                for block in iter(lambda:source.read(4*1024*1024),b''):digest.update(block);out.write(block)
            manifest['files'][relative]={'sha256':digest.hexdigest(),'size':path.stat().st_size}
        z.writestr('manifest.json',json.dumps(manifest))
    with zipfile.ZipFile(target) as z:
        if z.testzip():raise ValueError('Backup integrity verification failed.')
    return target


def restore(payload,families):
    families=Path(families);allowed={'references','original-recordings','voice-models','generated-audio','samples','settings'}
    with tempfile.TemporaryDirectory(dir=families.parent,prefix='restore-') as temp:
        staging=Path(temp)
        with zipfile.ZipFile(payload) as z:
            if len(z.namelist()) != len(set(z.namelist())):raise ValueError('Archive contains duplicate paths')
            if z.getinfo('manifest.json').file_size>2_000_000 or sum(i.file_size for i in z.infolist())>500_000_000:raise ValueError('Backup exceeds safe restore limits')
            manifest=json.loads(z.read('manifest.json'))
            if not isinstance(manifest,dict) or not isinstance(manifest.get('files'),dict):raise ValueError('Invalid backup manifest')
            if manifest.get('format')!='studio2-private-backup-v2':raise ValueError('Not a Studio 2.0 private backup')
            if set(z.namelist())!=set(manifest['files'])|{'manifest.json'}:raise ValueError('Archive contents do not match the manifest')
            if sum(i.file_size for i in z.infolist())>500_000_000:raise ValueError('Backup exceeds the 500 MB restore limit')
            for name,expected in manifest['files'].items():
                if not isinstance(expected,dict) or not isinstance(expected.get('size'),int) or expected['size']<0 or not isinstance(expected.get('sha256'),str) or len(expected['sha256'])!=64:raise ValueError('Invalid backup file metadata')
                parts=PurePosixPath(name).parts
                if len(parts)<3 or str(uuid.UUID(parts[0]))!=parts[0] or parts[1] not in allowed or any(p in ('.','..') or '\\' in p or ':' in p for p in parts):raise ValueError('Invalid archive path')
                target=staging.joinpath(*parts)
                if target.is_relative_to(staging) is False:raise ValueError('Invalid archive path')
                target.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256();size=0
                with z.open(name) as source,target.open('wb') as out:
                    for block in iter(lambda:source.read(4*1024*1024),b''):
                        size+=len(block)
                        if size>expected['size']:raise ValueError('Invalid archive size')
                        digest.update(block);out.write(block)
                if size!=expected['size'] or digest.hexdigest()!=expected['sha256']:raise ValueError('Backup checksum verification failed')
            for profile in staging.iterdir():
                settings=profile/'settings/profile.json';data=json.loads(settings.read_text())
                if data['id']!=profile.name or not isinstance(data.get('recordings'),list) or not isinstance(data.get('generated'),list):raise ValueError('Invalid profile metadata')
                for group,key in [('references','recordings'),('generated-audio','generated')]:
                    for record in data[key]:
                        rid=record['id']
                        if str(uuid.UUID(rid))!=rid:raise ValueError('Invalid recording identifier')
                        file=profile/group/(rid+'.wav' if group=='generated-audio' else rid)
                        if not file.exists():raise ValueError('Backup is missing indexed audio')
                if data.get('primary_reference') is not None and data['primary_reference'] not in [r['id'] for r in data['recordings']]:raise ValueError('Invalid primary reference')
                versions=set()
                for item in data.get('adaptations',[]):
                    version=item['id']
                    if str(uuid.UUID(version))!=version or version in versions:raise ValueError('Invalid adaptation identifier')
                    versions.add(version)
                    checkpoint=profile/'voice-models'/(version+'.safetensors')
                    metadata=json.loads(checkpoint.with_suffix('.json').read_text())
                    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=metadata['sha256'] or item['sha256']!=metadata['sha256']:raise ValueError('Adaptation checkpoint checksum failed')
                if data.get('active_adaptation') and data['active_adaptation'] not in versions:raise ValueError('Invalid active adaptation')
                if data.get('minor'):data['consent_status']='guardian_verification_pending'
                if data.get('consent_status') not in ('authorized','revoked','guardian_verification_pending'):raise ValueError('Invalid consent status')
                settings.write_text(json.dumps(data,indent=2))
        restored=0;skipped=0
        for path in staging.iterdir():
            target=families/path.name
            if target.exists():skipped+=1;continue
            shutil.move(str(path),target);restored+=1
    return {'restored':restored,'existing_profiles_preserved':skipped}
