"""One model at a time, serialized generation, explicit local-only inference."""
import gc
import hashlib
import json
import importlib.metadata
import os
import re
import threading
from pathlib import Path

MODELS = {
    'chatterbox': {'repo': 'ResembleAI/chatterbox', 'files': ['ve.safetensors', 't3_cfg.safetensors', 's3gen.safetensors', 'tokenizer.json', 'conds.pt']},
    'turbo': {'repo': 'ResembleAI/chatterbox-turbo', 'files': ['ve.safetensors', 't3_turbo_v1.safetensors', 's3gen_meanflow.safetensors', 'tokenizer.json', 'tokenizer_config.json', 'conds.pt']},
}


def verify_manifest(directory, name):
    manifest_file = directory / 'manifest.json'
    if not manifest_file.exists():
        raise RuntimeError('No verified model manifest. Run Download Models.cmd.')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    if manifest.get('repository') != MODELS[name]['repo']:
        raise RuntimeError('Model manifest repository mismatch. Run Download Models.cmd.')
    for filename in MODELS[name]['files']:
        if filename not in manifest.get('files', {}):
            raise RuntimeError('Incomplete model manifest. Run Download Models.cmd.')
    for filename, details in manifest['files'].items():
        if Path(filename).name != filename:
            raise RuntimeError('Invalid manifest filename.')
        path = directory / filename
        if not path.is_file():
            raise RuntimeError('Model integrity check failed: ' + filename)
        value = hashlib.sha256()
        with path.open('rb') as file:
            for chunk in iter(lambda: file.read(4 * 1024 * 1024), b''):
                value.update(chunk)
        if value.hexdigest() != details['sha256']:
            raise RuntimeError('Model integrity check failed: ' + filename + '. Run Download Models.cmd.')


def segments(text, limit=240):
    text = re.sub(r'\s+', ' ', text).strip()
    result = []
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        words = sentence.split()
        chunk = ''
        for word in words:
            if len(word) > limit:
                raise ValueError('A word is too long; insert spaces into long identifiers.')
            if len(chunk) + len(word) + 1 > limit:
                result.append(chunk)
                chunk = word
            else:
                chunk = (chunk + ' ' + word).strip()
        if chunk:
            if result and len(result[-1]) + len(chunk) + 1 <= limit:
                result[-1] += ' ' + chunk
            else:
                result.append(chunk)
    return result


class Engine:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.Lock()
        self.model = None
        self.loaded = None
        self.device = None
        self.revision = None
        self.message = 'Model not loaded.'

    def model_path(self, name):
        return self.root / name

    def missing(self, name):
        return [f for f in MODELS[name]['files'] if not (self.model_path(name) / f).is_file()]

    def status(self):
        try:
            version = importlib.metadata.version('chatterbox-tts')
        except importlib.metadata.PackageNotFoundError:
            version = None
        return {'package_version': version, 'loaded': self.loaded, 'device': self.device,
                'message': self.message, 'models': {name: {'missing': self.missing(name), 'path': str(self.model_path(name))} for name in MODELS},
                'busy': self.lock.locked(), 'revision': self.revision}

    def unload(self):
        self.model = None
        self.loaded = None
        self.revision = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def load(self, name, preference):
        os.environ.setdefault('HF_HOME', str(self.root / '.cache'))
        os.environ.setdefault('NUMBA_CACHE_DIR', str(self.root / '.numba-cache'))
        missing = self.missing(name)
        if missing:
            raise RuntimeError(f'{name} model files missing: {", ".join(missing)}. Double-click Download Models.cmd while online.')
        try:
            import torch
            from chatterbox.tts import ChatterboxTTS
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            import perth
            if perth.PerthImplicitWatermarker is None:
                raise ImportError('Perth watermarker unavailable; restore the pinned setuptools 78.1.0 with Install or Repair.cmd.')
        except (ImportError, OSError) as exc:
            raise RuntimeError('Engine import failed. Run Install or Repair.cmd; see terminal details: ' + str(exc)) from exc
        selected = 'cuda' if preference == 'auto' and torch.cuda.is_available() else ('cpu' if preference == 'auto' else preference)
        if selected == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable. Choose CPU or Auto; update the NVIDIA driver and repair the CUDA PyTorch install.')
        if self.loaded == name and self.device == selected:
            return
        verify_manifest(self.model_path(name), name)
        self.unload()
        torch.set_num_threads(min(8, os.cpu_count() or 4))
        cls = ChatterboxTTS if name == 'chatterbox' else ChatterboxTurboTTS
        self.message = f'Loading {name} on {selected}…'
        try:
            self.model = cls.from_local(self.model_path(name), device=selected)
        except torch.cuda.OutOfMemoryError:
            self.unload()
            if preference != 'auto':
                raise RuntimeError('GPU memory exhausted. Close GPU applications or choose CPU / Auto.')
            selected = 'cpu'
            self.model = cls.from_local(self.model_path(name), device='cpu')
        self.loaded, self.device = name, selected
        self.revision = json.loads((self.model_path(name) / 'manifest.json').read_text(encoding='utf-8')).get('revision')
        self.message = f'{name} ready on {selected}. No recordings are uploaded.'

    def generate(self, text, reference, settings, controls, progress, cancelled):
        import numpy as np
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError('PyTorch is missing. Run Install or Repair.cmd.') from exc
        self.load(settings['engine'], settings['device'])
        parts = segments(text)
        wavs = []
        for idx, part in enumerate(parts):
            if cancelled():
                raise RuntimeError('Generation cancelled. No incomplete recording was saved.')
            progress(idx, len(parts))
            kwargs = {'audio_prompt_path': str(reference), 'temperature': controls.temperature}
            if settings['engine'] == 'chatterbox':
                kwargs.update(exaggeration=controls.exaggeration, cfg_weight=controls.cfg_weight)
            try:
                with torch.inference_mode():
                    wav = self.model.generate(part, **kwargs)
            except torch.cuda.OutOfMemoryError:
                if settings['device'] != 'auto' or self.device != 'cuda':
                    raise RuntimeError('GPU memory exhausted. Choose Auto for CPU fallback, or CPU.')
                self.unload()
                self.load(settings['engine'], 'cpu')
                with torch.inference_mode():
                    wav = self.model.generate(part, **kwargs)
                self.message += ' GPU ran out of memory; generation continued on CPU.'
            arr = wav.detach().cpu().numpy().reshape(-1)
            if not len(arr) or not np.isfinite(arr).all():
                raise RuntimeError('Engine returned invalid audio.')
            wavs.append(arr)
            if idx < len(parts) - 1:
                wavs.append(np.zeros(int(self.model.sr * controls.pause_ms / 1000), dtype=np.float32))
            progress(idx + 1, len(parts))
        if cancelled():
            raise RuntimeError('Generation cancelled. No recording was saved.')
        return np.concatenate(wavs), self.model.sr
