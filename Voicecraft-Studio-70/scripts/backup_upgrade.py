"""Private local pre-upgrade backup; standard library only, never uploads anything."""
import argparse,datetime,json,os,shutil,sys,zipfile
from pathlib import Path
EXCLUDE={'shared-models','models','model-cache','pip-cache','numba-cache','temporary','desktop-window','desktop-window-staging','upgrade-backups','__pycache__','.runtime','.venv','.venv-ai','node_modules','.git','.pytest_cache'}

def create_backup(install,local,data=None,destination=None):
    install=Path(install);local=Path(local)
    if data is None:
        configuration=local/'desktop.json';selection=local/'storage.txt'
        if selection.is_file() and selection.read_text(encoding='utf-8').strip():data=Path(selection.read_text(encoding='utf-8').strip())
        elif configuration.is_file():data=Path(json.loads(configuration.read_text(encoding='utf-8'))['data_directory'])
        else:data=Path('D:/Voicecraft-Studio-70') if Path('D:/').exists() else local/'data'
    data=Path(data)
    if not data.is_absolute() or data==Path(data.anchor):raise ValueError('Choose an application data folder rather than a disk root before upgrading.')
    destination=Path(destination or local/'upgrade-backups');destination.mkdir(parents=True,exist_ok=True)
    entries=[]
    for label,folder in [('previous-source',install/'app'),('family-data',data)]:
        if not folder.is_dir():continue
        for current,dirs,files in os.walk(folder,followlinks=False):
            current=Path(current)
            dirs[:]=[d for d in dirs if d.lower() not in EXCLUDE and not d.lower().startswith('.venv') and not (current/d).is_symlink() and (current/d).resolve().is_relative_to(folder.resolve()) and (current/d).resolve()!=destination.resolve()]
            for name in files:
                file=current/name
                if file.is_symlink() or file.suffix=='.pyc':continue
                entries.append((file,label+'/'+str(file.relative_to(folder))))
    for name in ['desktop.json','storage.txt']:
        if (local/name).is_file():entries.append((local/name,'launcher-settings/'+name))
    size=sum(file.stat().st_size for file,_ in entries)
    if shutil.disk_usage(destination).free<size+256*1024**2:raise RuntimeError('Not enough space for a safe backup. Free space before updating. Your existing application was not changed.')
    filename=destination/('before-natural-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.zip')
    partial=filename.with_suffix('.partial')
    try:
        with zipfile.ZipFile(partial,'w',zipfile.ZIP_DEFLATED) as package:
            for file,name in entries:package.write(file,name)
            package.writestr('BACKUP-NOTES.txt','Private pre-upgrade source, settings, profiles, original recordings and generated audio. Shared downloaded models/caches excluded. No files were removed.\n')
        with zipfile.ZipFile(partial) as package:
            if package.testzip():raise RuntimeError('Backup integrity check failed.')
        partial.rename(filename)
    finally:partial.unlink(missing_ok=True)
    (local/'upgrade-backup-error.txt').unlink(missing_ok=True)
    (local/'last-upgrade-backup.txt').write_text(str(filename),encoding='utf-8')
    return filename

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--install-dir',type=Path,required=True);args=parser.parse_args()
    local=Path(os.environ['LOCALAPPDATA'])/'Voicecraft-Studio-70';local.mkdir(parents=True,exist_ok=True)
    try:create_backup(args.install_dir,local)
    except Exception as error:
        (local/'upgrade-backup-error.txt').write_text(str(error),encoding='utf-8');sys.exit(1)
