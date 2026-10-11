"""Adapter control tests with explicit fixtures; not counted as real AI inference."""
import types
import sys
import torch
from studio.engine import VoiceEngine
from studio.app import VoiceSettings


def test_conditioning_reused_only_for_same_reference_and_expression(tmp_path):
    class ModelFixture:
        sr=24000
        def __init__(self):self.prepared=[]
        def prepare_conditionals(self,path,**options):self.prepared.append((path,options))
        def generate(self,*args,**options):return torch.ones(1,2400)*.1
    engine=VoiceEngine(tmp_path);engine.model=ModelFixture();engine.name='expressive';engine.device='cpu'
    engine.load=lambda *args:None
    a,b=tmp_path/'a.wav',tmp_path/'b.wav';a.write_bytes(b'a');b.write_bytes(b'b')
    settings=VoiceSettings(device='cpu').model_dump()
    engine.synthesize('First',a,settings);engine.synthesize('Next segment',a,settings)
    assert len(engine.model.prepared)==1
    engine.synthesize('Other profile',b,settings)
    engine.synthesize('Original profile again',a,settings)
    assert len(engine.model.prepared)==3
    engine.synthesize('Changed expression',a,{**settings,'expression':.9})
    assert len(engine.model.prepared)==4
    a.write_bytes(b'changed reference')
    engine.synthesize('Changed file',a,{**settings,'expression':.9})
    assert len(engine.model.prepared)==5
    engine.unload();assert engine._reference_key is None and engine.model is None


def test_auto_oom_fallback_stays_on_cpu_until_explicit_unload(tmp_path,monkeypatch):
    import studio.engine as module
    calls=[]
    class LoaderFixture:
        @classmethod
        def from_local(cls,path,device):
            calls.append(device)
            if device=='cuda':raise torch.cuda.OutOfMemoryError('Explicit test fixture')
            return object()
    monkeypatch.setitem(sys.modules,'chatterbox.tts',types.SimpleNamespace(ChatterboxTTS=LoaderFixture))
    monkeypatch.setitem(sys.modules,'chatterbox.tts_turbo',types.SimpleNamespace(ChatterboxTurboTTS=LoaderFixture))
    monkeypatch.setattr(module,'verify',lambda *args:tmp_path)
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(torch.cuda,'empty_cache',lambda:None)
    engine=VoiceEngine(tmp_path)
    engine.load('expressive','auto');engine.load('expressive','auto')
    assert calls==['cuda','cpu'] and engine.device=='cpu'
    assert engine.status()['cpu_fallback_engines']==['expressive']
    engine.unload();engine.load('expressive','auto')
    assert calls==['cuda','cpu','cuda','cpu']
    engine.unload()
