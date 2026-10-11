"""Build native x64 launcher + per-user NSIS installer on Windows or Linux."""
import argparse,hashlib,json,os,shutil,subprocess,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tools-root',type=Path);parser.add_argument('--output',type=Path,default=ROOT/'dist');parser.add_argument('--stage',type=Path,default=ROOT/'.runtime/windows-stage');args=parser.parse_args()
    stage=args.stage.resolve();stage.mkdir(parents=True,exist_ok=True);args.output.mkdir(parents=True,exist_ok=True)
    tools=args.tools_root.resolve() if args.tools_root else None
    def executable(names):
        for name in names:
            if tools:
                for directory in [tools/'usr/bin',tools/'bin']:
                    for suffix in ('','.exe'):
                        path=directory/(name+suffix)
                        if path.is_file():return str(path)
            found=shutil.which(name)
            if found:return found
        raise RuntimeError('Install required build tool: '+names[0])
    gcc=executable(['x86_64-w64-mingw32-gcc-posix','x86_64-w64-mingw32-gcc','gcc']);windres=executable(['x86_64-w64-mingw32-windres','windres']);nsis=executable(['makensis'])
    runtime=stage/'runtime';spec=json.loads((ROOT/'packaging/python-runtime.json').read_text());archive=stage/'python.nupkg'
    if not archive.exists():urllib.request.urlretrieve(spec['url'],archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=spec['sha256']:raise RuntimeError('Python runtime checksum mismatch; refusing to build.')
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        if package.testzip():raise RuntimeError('Damaged Python package')
        for item in package.infolist():
            if item.filename.startswith('tools/') and not item.is_dir():
                relative=Path(item.filename[6:])
                if '..' in relative.parts or relative.is_absolute():raise RuntimeError('Invalid package path')
                target=runtime/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(package.read(item))
    app=stage/'app'
    if app.exists():shutil.rmtree(app)
    shutil.copytree(ROOT,app,ignore=shutil.ignore_patterns('.runtime','.venv*','__pycache__','.pytest_cache','dist','*.pyc'))
    resource=stage/'launcher.o';builddir=ROOT/'packaging';extra=[];windextra=[]
    if tools and os.name!='nt':
        extra=['-B',str(tools/'usr/bin')+'/', '-B',str(tools/'usr/x86_64-w64-mingw32/lib')+'/', '-I',str(tools/'usr/x86_64-w64-mingw32/include')]
        windextra=['-I',str(tools/'usr/x86_64-w64-mingw32/include')]
    subprocess.run([windres,*windextra,'launcher.rc','-O','coff','-o',str(resource)],check=True,cwd=builddir)
    subprocess.run([gcc,*extra,'-municode','-mwindows','-O2','-Wall','-Werror','launcher.c',str(resource),'-o',str(stage/'VoiceCraft.exe'),'-lshell32','-lole32','-static-libgcc'],check=True,cwd=builddir)
    # The stage-only Python download and compiler object must never become installer payload.
    payload=stage/'payload';payload.mkdir(exist_ok=True)
    for name in ('app','runtime'):
        target=payload/name
        if target.exists():shutil.rmtree(target)
        shutil.copytree(stage/name,target)
    shutil.copy(stage/'VoiceCraft.exe',payload/'VoiceCraft.exe')
    env=dict(os.environ)
    if tools and os.name!='nt':env['NSISDIR']=str(tools/'usr/share/nsis')
    output=(args.output/'VoiceCraft-Studio-1.0.0-Setup.exe').resolve()
    prefix='/' if os.name=='nt' else '-'
    subprocess.run([nsis,prefix+'DSTAGE='+str(payload),prefix+'DOUTPUT='+str(output),'installer.nsi'],check=True,cwd=builddir,env=env)
    (args.output/'SHA256SUMS.txt').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
    print('Built',output)

if __name__=='__main__':main()
