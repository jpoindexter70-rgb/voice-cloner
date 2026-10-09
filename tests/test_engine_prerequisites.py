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
