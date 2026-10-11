"""Runtime integrity checks exercise the same first-start installer code."""
import importlib.util,json,hashlib,zipfile
from pathlib import Path
import pytest

@pytest.fixture
def desktop(tmp_path,monkeypatch):
    script=Path(__file__).resolve().parents[1]/'scripts/desktop.py'
    spec=importlib.util.spec_from_file_location('desktop_runtime_test',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    app=tmp_path/'app';(app/'packaging').mkdir(parents=True);(app/'desktop').mkdir()
    (app/'desktop/main.cjs').write_text('local desktop source')
    (app/'packaging/voicecraft.ico').write_bytes(b'icon')
    module.APP=app
    return module,app

def test_renderer_verification_reuse_and_corruption_repair(desktop,tmp_path,monkeypatch):
    module,app=desktop;archive=tmp_path/'fixture.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('electron.exe',b'fixture executable');z.writestr('chrome.dll',b'fixture runtime')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (app/'packaging/electron-runtime.json').write_text(json.dumps({'url':'https://official.invalid/fixture.zip','sha256':digest}))
    downloads=[]
    def download(url,target):downloads.append(url);Path(target).write_bytes(archive.read_bytes())
    monkeypatch.setattr(module.urllib.request,'urlretrieve',download)
    exe=module.desktop_runtime();assert exe.read_bytes()==b'fixture executable';assert len(downloads)==1
    assert (exe.parent/'resources/app/main.cjs').read_text()=='local desktop source'
    assert module.desktop_runtime()==exe;assert len(downloads)==1
    (exe.parent/'chrome.dll').write_bytes(b'corrupt')
    module.desktop_runtime();assert len(downloads)==2;assert (exe.parent/'chrome.dll').read_bytes()==b'fixture runtime'

def test_renderer_rejects_wrong_hash(desktop,monkeypatch):
    module,app=desktop
    (app/'packaging/electron-runtime.json').write_text(json.dumps({'url':'https://official.invalid/fixture.zip','sha256':'0'*64}))
    monkeypatch.setattr(module.urllib.request,'urlretrieve',lambda url,target:Path(target).write_bytes(b'untrusted'))
    with pytest.raises(RuntimeError,match='checksum mismatch'):module.desktop_runtime()
    assert not (Path(module.os.environ['LOCALAPPDATA'])/'Voicecraft-Studio-70/desktop-window/Voicecraft70Window.exe').exists()

@pytest.mark.parametrize('window_fails',[False,True])
def test_window_lifecycle_stops_engine_without_browser(desktop,monkeypatch,window_fails):
    module,app=desktop
    import importlib.metadata,types,uvicorn,studio.app,studio.models,webbrowser,time
    monkeypatch.setattr(module.sys,'argv',['desktop.py'])
    executable=app/'Voicecraft70Window.exe';executable.write_bytes(b'fixture')
    monkeypatch.setattr(module,'desktop_runtime',lambda:executable)
    versions={'fastapi':'0.115.12','uvicorn':'0.34.2','soundfile':'0.13.1','chatterbox-tts':'0.1.7','munch':'4.0.0'}
    monkeypatch.setattr(importlib.metadata,'version',lambda package:versions[package])
    monkeypatch.setattr(studio.models,'verify',lambda *args:None)
    monkeypatch.setattr(studio.app,'create_app',lambda *args:types.SimpleNamespace(state=types.SimpleNamespace()))
    monkeypatch.setattr(webbrowser,'open',lambda *args:pytest.fail('A standalone launch must not open a browser'))
    servers=[]
    class Server:
        def __init__(self,config):self.started=False;self.should_exit=False;self.stopped=False;self.config=config;servers.append(self)
        def run(self):
            self.started=True
            while not self.should_exit:time.sleep(.005)
            self.stopped=True
    monkeypatch.setattr(uvicorn,'Server',Server)
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if command==[str(executable)] and window_fails:raise module.subprocess.CalledProcessError(1,command)
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess,'run',run)
    if window_fails:
        with pytest.raises(module.subprocess.CalledProcessError):module.main()
    else:module.main()
    assert servers[0].stopped and servers[0].should_exit
    assert servers[0].config.host=='127.0.0.1' and servers[0].config.port==8791
    assert [str(executable)] in calls
