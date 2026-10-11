"""Bundled Windows runtime: graphical launcher owns this process, never a console."""
import os,sys,json,subprocess,time,threading,webbrowser,hashlib
from pathlib import Path
APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
if os.name=='nt':
    _Popen=subprocess.Popen
    class QuietPopen(_Popen):
        def __init__(self,*args,**kwargs):
            kwargs['creationflags']=kwargs.get('creationflags',0)|subprocess.CREATE_NO_WINDOW
            super().__init__(*args,**kwargs)
    subprocess.Popen=QuietPopen

def configuration():
    location=Path(os.getenv('LOCALAPPDATA',str(Path.home())))/'VoiceCraft-Studio'
    location.mkdir(parents=True,exist_ok=True)
    config=location/'desktop.json'
    if not config.exists():
        preferred=Path('D:/VoiceCraft-Studio') if os.name=='nt' and Path('D:/').exists() else location/'data'
        config.write_text(json.dumps({'data_directory':str(preferred)},indent=2),encoding='utf-8')
    result=json.loads(config.read_text(encoding='utf-8'))
    selection=location/'storage.txt'
    if selection.exists():
        chosen=selection.read_text(encoding='utf-8').strip()
        if chosen and Path(chosen).is_absolute():result['data_directory']=chosen;config.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def run(command):
    print('Preparing local engine packages. This can take several minutes on first use.',flush=True)
    subprocess.run(command,check=True,cwd=APP)

def main():
    if '--check-runtime' in sys.argv:
        assert sys.version_info[:2]==(3,11) and sys.maxsize>2**32
        print('VOICECRAFT_RUNTIME_OK',flush=True);return
    os.environ['PYTHONUTF8']='1'
    for name in ('STUDIO2_PUBLIC_ORIGIN','STUDIO2_PASSWORD','STUDIO2_BACKUP_REPO','STUDIO2_BACKUP_TOKEN'):os.environ.pop(name,None)
    config=configuration();data=Path(config['data_directory']);data.mkdir(parents=True,exist_ok=True)
    os.environ['STUDIO2_DATA_DIR']=str(data);os.environ['PORT']='8790'
    for name,folder in [('HF_HOME','model-cache'),('NUMBA_CACHE_DIR','numba-cache'),('PIP_CACHE_DIR','pip-cache'),('TMP','temporary'),('TEMP','temporary'),('TMPDIR','temporary')]:
        target=data/folder;target.mkdir(exist_ok=True);os.environ[name]=str(target)
    from importlib.metadata import version,PackageNotFoundError
    ready=True
    for package,expected in [('fastapi','0.115.12'),('uvicorn','0.34.2'),('soundfile','0.13.1'),('chatterbox-tts','0.1.7'),('munch','4.0.0')]:
        try:ready=ready and version(package)==expected
        except PackageNotFoundError:ready=False
    if ready:
        check=subprocess.run([sys.executable,'-c',"import torch,torchaudio,soundfile,fastapi,uvicorn,numpy; from chatterbox.tts_turbo import ChatterboxTurboTTS; from chatterbox.tts import ChatterboxTTS; assert torch.__version__.split('+')[0]=='2.6.0'; assert torchaudio.__version__.split('+')[0]=='2.6.0'"],capture_output=True,cwd=APP)
        ready=check.returncode==0
    if not ready:
        cuda=False
        if os.name=='nt' and not os.getenv('VOICECRAFT_FORCE_CPU'):
            try:cuda=subprocess.run(['nvidia-smi'],capture_output=True,timeout=10).returncode==0
            except (OSError,subprocess.TimeoutExpired):pass
        index='https://download.pytorch.org/whl/cu124' if cuda else 'https://download.pytorch.org/whl/cpu'
        print('Installing '+('NVIDIA CUDA 12.4' if cuda else 'CPU')+' engine runtime.',flush=True)
        try:run([sys.executable,'-m','pip','install','--disable-pip-version-check','torch==2.6.0','torchaudio==2.6.0','--index-url',index])
        except subprocess.CalledProcessError:
            if not cuda:raise
            print('GPU package installation unavailable; preparing CPU fallback.',flush=True)
            run([sys.executable,'-m','pip','install','--disable-pip-version-check','torch==2.6.0','torchaudio==2.6.0','--index-url','https://download.pytorch.org/whl/cpu'])
        run([sys.executable,'-m','pip','install','--disable-pip-version-check','-r',str(APP/'requirements-runtime.txt'),'-c',str(APP/'requirements-windows-lock.txt')])
        run([sys.executable,'-m','pip','check'])
    from studio.models import verify,download
    model_root=data/'shared-models'
    for name in ('turbo','expressive'):
        try:verify(model_root,name);print('Reusing verified '+name+' models.',flush=True)
        except (OSError,ValueError,KeyError,RuntimeError):
            print('Preparing '+name+' models. Official downloads require internet; your recordings stay on this computer.',flush=True)
            download(model_root,name)
    from studio.app import create_app
    import uvicorn
    app=create_app(data);server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8790,log_level='warning'))
    app.state.shutdown=lambda:setattr(server,'should_exit',True)
    def ready_notice():
        for _ in range(600):
            if server.started:
                print('VOICECRAFT_READY',flush=True);webbrowser.open('http://127.0.0.1:8790');return
            if server.should_exit:return
            time.sleep(.1)
    threading.Thread(target=ready_notice,daemon=True).start();server.run()

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        traceback.print_exc();print('Setup could not finish. Existing recordings were preserved. Keep this message for diagnostics and reopen VoiceCraft to retry.',flush=True);sys.exit(1)
