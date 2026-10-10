"""Real installed engine prerequisites; no speech checkpoint or voice likeness claim."""
import inspect
import numpy as np
import torch
import perth
from chatterbox.tts import ChatterboxTTS
from chatterbox.tts_turbo import ChatterboxTurboTTS


def test_real_engine_imports_and_packaged_watermarker():
    assert 'audio_prompt_path' in inspect.signature(ChatterboxTTS.generate).parameters
    assert 'audio_prompt_path' in inspect.signature(ChatterboxTurboTTS.generate).parameters
    # Perth hides an ImportError and sets this to None with incompatible setuptools.
    assert perth.PerthImplicitWatermarker is not None
    torch.set_num_threads(2)
    model=perth.PerthImplicitWatermarker()
    samples=(.1*np.sin(np.arange(48000)*.05)).astype(np.float32)
    with torch.inference_mode():
        output=model.apply_watermark(samples,sample_rate=24000)
    assert len(output)>45000 and np.isfinite(output).all()


def test_installer_runtime_checks_load_each_model_and_unload(tmp_path, monkeypatch):
    from studio import cli
    from studio.engine import Engine
    monkeypatch.setenv('VCR_DATA_DIR', str(tmp_path))
    loaded, unloaded = [], []
    def load(self, name, device):
        assert self.lock.locked()
        loaded.append((name, device))
        self.message = name + ' fixture loaded'
    monkeypatch.setattr(Engine, 'load', load)
    monkeypatch.setattr(Engine, 'unload', lambda self: unloaded.append(True))
    cli.check_runtime(load_models=True)
    assert loaded == [('chatterbox', 'auto'), ('turbo', 'auto')]
    assert len(unloaded) == 2


def test_installer_model_load_failure_is_not_reported_as_success(tmp_path, monkeypatch):
    import pytest
    from studio import cli
    monkeypatch.setenv('VCR_DATA_DIR', str(tmp_path))
    with pytest.raises(RuntimeError, match='model files missing'):
        cli.check_runtime(load_models=True)
