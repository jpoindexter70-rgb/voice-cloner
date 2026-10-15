"""Independent engine adapters for Studio 2.0, serialized by its job worker."""
import gc
import os
import re
import time
from pathlib import Path
import numpy as np
from .models import verify, SPECS
from .seed_assets import installed as seed_installed


def split_text(text,limit=220):
    # Bound every piece, including a single long token; preserve all words.
    pieces=[]; current=''
    for sentence in re.split(r'(?<=[.!?])\s+',text.strip()):
        for word in sentence.split():
            if len(word)>limit:
                if current:pieces.append(current);current=''
                pieces.extend(word[i:i+limit] for i in range(0,len(word),limit))
            elif len(current)+len(word)+1>limit:
                pieces.append(current);current=word
            else:current=(current+' '+word).strip()
    if current:pieces.append(current)
    return pieces


class VoiceEngine:
    def __init__(self,root):
        self.root=Path(root); self.model=None; self.name=None; self.device=None; self.message='Engine idle'
        self.load_seconds=None
        self._reference_key=None
        self._cpu_fallback=set()
        self.conditioning_preparations=0

    def status(self):
        import importlib.util
        available=importlib.util.find_spec('chatterbox') is not None
        installed={name:all((self.root/name/file).exists() for file in spec['files']) and (self.root/name/'manifest.json').exists() for name,spec in SPECS.items()}
        return {'dependencies':available,'models':installed,'loaded':self.name,'device':self.device,'message':self.message,
                'languages':['English'],'live_conversion':{'implemented':True,'engine':'seed','requires':'A fresh passing profile CUDA benchmark'},'load_seconds':self.load_seconds,
                'conditioning_cached':self._reference_key is not None,
                'conditioning_preparations':self.conditioning_preparations,
                'cpu_fallback_engines':sorted(self._cpu_fallback),
                'conversion_engines':{'expressive':installed['expressive'],'seed':seed_installed(self.root)}}

    def unload(self,reset_fallback=True):
        self.model=None;self.name=None;self.device=None;gc.collect()
        self._reference_key=None
        if reset_fallback:self._cpu_fallback.clear()
        try:
            import torch
            if torch.cuda.is_available():torch.cuda.empty_cache()
        except ImportError:pass
        self.message='Engine unloaded; GPU memory released'

    def load(self,name,device='auto'):
        import torch
        import perth
        if perth.PerthImplicitWatermarker is None:raise RuntimeError('Watermark runtime unavailable; repair engine dependencies.')
        if name not in SPECS and name!='seed':raise RuntimeError('Unknown voice engine')
        chosen='cuda' if device=='auto' and torch.cuda.is_available() else 'cpu' if device=='auto' else device
        if device=='auto' and name in self._cpu_fallback:chosen='cpu'
        if chosen=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA is unavailable; choose Auto or CPU.')
        if self.name==name and self.device==chosen and self.model is not None:return
        self.unload(reset_fallback=False);self.message='Verifying and loading '+name+' on '+chosen
        started=time.monotonic()
        from .system import memory_bytes
        _,available=memory_bytes()
        required=(8 if name=='expressive' else 4)*1024**3
        if available is not None and available<required:
            raise RuntimeError('Not enough free system RAM for a safe '+name+' model load. Close other applications'+(' or select Chatterbox Turbo' if name=='expressive' else '')+'. This is a conservative safety threshold, not a measured GPU requirement.')
        path=self.root if name=='seed' else verify(self.root,name)
        # from_local only reads verified checkpoint directories. Keep the separate private-backup client online.
        os.environ['TRANSFORMERS_OFFLINE']='1'
        os.environ.setdefault('NUMBA_CACHE_DIR',str(self.root.parent/'numba-cache'))
        torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
        from chatterbox.tts import ChatterboxTTS
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        from .seed import SeedEngine
        klass=SeedEngine if name=='seed' else ChatterboxTTS if name=='expressive' else ChatterboxTurboTTS
        try:self.model=klass.from_local(path,chosen)
        except torch.cuda.OutOfMemoryError:
            if device!='auto':raise
            self.unload(reset_fallback=False);self._cpu_fallback.add(name)
            chosen='cpu';self.model=klass.from_local(path,chosen)
        self.name=name;self.device=chosen;self.message=name+' ready on '+chosen
        self.load_seconds=round(time.monotonic()-started,2)

    def prepare_reference(self,reference,settings):
        # Only the current reference is retained, never a cross-profile embedding library.
        path=Path(reference).resolve();stat=path.stat()
        expression=settings['expression'] if self.name=='expressive' else 0
        key=(self.name,self.device,str(path),stat.st_mtime_ns,stat.st_size,expression)
        if key!=self._reference_key:
            self._reference_key=None
            self.model.prepare_conditionals(str(path),exaggeration=expression)
            self._reference_key=key
            self.conditioning_preparations+=1

    def synthesize(self,text,reference,settings):
        import torch
        name=settings['engine'];self.load(name,settings['device'])
        options={'temperature':settings['temperature']}
        if settings.get('quality_mode')=='natural_studio':options.update(repetition_penalty=1.2,top_p=.95)
        if name=='expressive':options.update(exaggeration=settings['expression'],cfg_weight=settings['similarity'])
        def generate():
            seed=settings.get('sampling_seed')
            devices=list(range(torch.cuda.device_count())) if torch.cuda.is_available() else []
            with torch.random.fork_rng(devices=devices,enabled=seed is not None),torch.inference_mode():
                if seed is not None:torch.manual_seed(seed)
                self.prepare_reference(reference,settings)
                return self.model.generate(text,**options)
        try:
            audio=generate()
        except torch.cuda.OutOfMemoryError:
            if settings['device']!='auto':raise
            self.unload(reset_fallback=False);self._cpu_fallback.add(name);self.load(name,'cpu')
            audio=generate()
        values=audio.detach().cpu().numpy().reshape(-1)
        if len(values)==0 or not np.isfinite(values).all():raise RuntimeError('Engine returned invalid audio')
        return values,int(self.model.sr)

    def convert(self,source,reference,settings):
        import torch
        if settings.get('conversion_engine')=='seed':
            self.load('seed',settings['device'])
            try:return self.model.convert(source,reference,settings,settings.get('_adapter'))
            except torch.cuda.OutOfMemoryError:
                if settings['device']!='auto':raise
                self.unload(reset_fallback=False);self._cpu_fallback.add('seed');self.load('seed','cpu')
                return self.model.convert(source,reference,settings,settings.get('_adapter'))
        from chatterbox.vc import ChatterboxVC
        # Conversion uses Original's shared S3 generator, not another profile model.
        self.load('expressive',settings['device'])
        model=ChatterboxVC(self.model.s3gen,self.device)
        try:
            with torch.inference_mode():audio=model.generate(str(source),target_voice_path=str(reference))
        except torch.cuda.OutOfMemoryError:
            if settings['device']!='auto':raise
            del model;self.unload(reset_fallback=False);self._cpu_fallback.add('expressive')
            self.load('expressive','cpu');model=ChatterboxVC(self.model.s3gen,self.device)
            with torch.inference_mode():audio=model.generate(str(source),target_voice_path=str(reference))
        values=audio.detach().cpu().numpy().reshape(-1)
        return values,int(model.sr)
