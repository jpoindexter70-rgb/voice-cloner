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

def test_renderer_verification_reuse_and_corruption_repair(desktop,tmp_path,monkeypatch,capsys):
    module,app=desktop;archive=tmp_path/'fixture.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('electron.exe',b'fixture executable');z.writestr('chrome.dll',b'fixture runtime')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (app/'packaging/electron-runtime.json').write_text(json.dumps({'url':'https://official.invalid/fixture.zip','sha256':digest}))
    downloads=[]
    def download(url,target):downloads.append(url);Path(target).write_bytes(archive.read_bytes())
    monkeypatch.setattr(module.urllib.request,'urlretrieve',download)
    exe=module.desktop_runtime();assert 'VOICECRAFT_SETUP_REQUIRED' in capsys.readouterr().out;assert exe.read_bytes()==b'fixture executable';assert len(downloads)==1
    assert (exe.parent/'resources/app/main.cjs').read_text()=='local desktop source'
    assert module.desktop_runtime()==exe;assert len(downloads)==1;assert 'VOICECRAFT_SETUP_REQUIRED' not in capsys.readouterr().out
    (exe.parent/'chrome.dll').write_bytes(b'corrupt')
    module.desktop_runtime();assert 'VOICECRAFT_SETUP_REQUIRED' in capsys.readouterr().out;assert len(downloads)==2;assert (exe.parent/'chrome.dll').read_bytes()==b'fixture runtime'

def test_renderer_rejects_wrong_hash(desktop,monkeypatch):
    module,app=desktop
    (app/'packaging/electron-runtime.json').write_text(json.dumps({'url':'https://official.invalid/fixture.zip','sha256':'0'*64}))
    monkeypatch.setattr(module.urllib.request,'urlretrieve',lambda url,target:Path(target).write_bytes(b'untrusted'))
    with pytest.raises(RuntimeError,match='checksum mismatch'):module.desktop_runtime()
    assert not (Path(module.os.environ['LOCALAPPDATA'])/'Voicecraft-Studio-70/desktop-window/Voicecraft70Window.exe').exists()

@pytest.mark.parametrize('engine_fails',[False,True])
def test_window_launches_before_engine_and_closing_stops_both(desktop,monkeypatch,engine_fails):
    module,app=desktop
    monkeypatch.setattr(module.sys,'argv',['desktop.py'])
    executable=app/'Voicecraft70Window.exe'
    monkeypatch.setattr(module,'desktop_runtime',lambda:executable)
    calls=[]
    class Process:
        def __init__(self,command,**kwargs):
            self.command=command;self.returncode=None;self.terminated=False;self.polls=0;calls.append(self)
        def poll(self):
            self.polls+=1
            if self.command==[str(executable)] and not engine_fails and self.polls>2:self.returncode=0
            if '--engine-process' in self.command and engine_fails:self.returncode=1
            return self.returncode
        def terminate(self):self.terminated=True;self.returncode=0
        def wait(self,**kwargs):return self.returncode
    monkeypatch.setattr(module.subprocess,'Popen',Process)
    if engine_fails:
        with pytest.raises(RuntimeError,match='startup stopped'):module.main()
    else:module.main()
    assert calls[0].command==[str(executable)]
    assert '--engine-process' in calls[1].command
    assert all(p.returncode is not None for p in calls)
    assert calls[0 if engine_fails else 1].terminated

@pytest.mark.parametrize('models_missing',[False,True])
@pytest.mark.parametrize('load_fails',[False,True])
def test_interface_starts_before_model_checks_and_preloads_turbo(desktop,monkeypatch,models_missing,load_fails):
    module,app=desktop
    import importlib.metadata,types,uvicorn,studio.app,studio.models,time
    versions={'fastapi':'0.115.12','uvicorn':'0.34.2','soundfile':'0.13.1','chatterbox-tts':'0.1.7','munch':'4.0.0','torch':'2.6.0','torchaudio':'2.6.0'}
    monkeypatch.setattr(importlib.metadata,'version',lambda package:versions[package])
    servers=[];events=[]
    class Engine:
        def load(self,name):
            assert servers[0].started;events.append(('load',name))
            if load_fails:raise RuntimeError('Fixture model load failure')
    application=types.SimpleNamespace(state=types.SimpleNamespace(voice_engine=Engine(),jobs=types.SimpleNamespace(last_activity=0)))
    monkeypatch.setattr(studio.app,'create_app',lambda *args:application)
    def verify(root,name):
        assert servers[0].started;events.append(('verify',name))
        if models_missing:raise RuntimeError('Missing fixture model')
    monkeypatch.setattr(studio.models,'verify',verify)
    monkeypatch.setattr(studio.models,'download',lambda root,name:events.append(('download',name)))
    class Server:
        def __init__(self,config):self.started=False;self.should_exit=False;self.config=config;servers.append(self)
        def run(self):
            self.started=True
            while not self.should_exit:
                if application.state.startup.get('ready') or application.state.startup.get('failed'):return
                time.sleep(.005)
    monkeypatch.setattr(uvicorn,'Server',Server)
    module.engine_main()
    assert application.state.startup['ready']==(not load_fails)
    if load_fails:assert application.state.startup['failed'] and 'model load failure' in application.state.startup['message']
    assert ('load','turbo') in events
    assert ('download','turbo') in events if models_missing else not any(e[0]=='download' for e in events)
    assert servers[0].should_exit


def test_starting_engine_blocks_generation_but_not_profiles(tmp_path):
    from tests.test_jobs import AdapterFixture,open_client,person,wait
    client=open_client(tmp_path,AdapterFixture());profile=person(client)
    try:
        client.app.state.startup={'ready':False,'message':'Voice engine starting.'}
        assert client.get('/api/startup').json()['ready'] is False
        assert client.get('/api/profiles').status_code==200
        body={'text':'Startup gate test','settings':profile['settings'],'seconds':5}
        assert client.post('/api/profiles/'+profile['id']+'/preview',json=body).status_code==503
        assert client.post('/api/engine/setup/turbo').status_code==409
        assert client.post('/api/engine/unload').status_code==409
        client.app.state.startup={'ready':True,'message':'Ready'}
        job=client.post('/api/profiles/'+profile['id']+'/preview',json=body)
        assert job.status_code==200,job.text
        assert wait(client,job.json())['status']=='completed'
    finally:client.close()
