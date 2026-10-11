"""Local Seed-VC tiny adapter. Architecture source is GPL-3.0; see seed_vendor/NOTICE.md."""
import json
import math
from pathlib import Path
import numpy as np
import soundfile as sf
from .seed_assets import verify_all
from .models import sha256


class SeedEngine:
    sr=22050
    @classmethod
    def from_local(cls,root,device):return cls(root,device)
    def __init__(self,root,device):
        import torch, yaml
        from transformers import Wav2Vec2Model,Wav2Vec2FeatureExtractor
        from .seed_vendor.modules.commons import recursive_munch,build_model,load_checkpoint
        from .seed_vendor.modules.campplus.DTDNN import CAMPPlus
        from .seed_vendor.modules.hifigan.generator import HiFTGenerator
        from .seed_vendor.modules.hifigan.f0_predictor import ConvRNNF0Predictor
        torch.set_num_threads(4)
        self.device=device;paths=verify_all(root)
        config=yaml.safe_load((paths['seed-core']/'config_dit_mel_seed_uvit_xlsr_tiny.yml').read_text())
        self.config=config;params=recursive_munch(config['model_params']);params.dit_type='DiT'
        self.model=build_model(params,stage='DiT')
        self.model,*_=load_checkpoint(self.model,None,str(paths['seed-core']/'DiT_uvit_tat_xlsr_ema.pth'),load_only_params=True,ignore_modules=[],is_distributed=False)
        for net in self.model.values():net.eval().to(device)
        self.model.cfm.estimator.setup_caches(max_batch_size=1,max_seq_length=8192)
        self.encoder=Wav2Vec2Model.from_pretrained(str(paths['seed-content']),local_files_only=True)
        self.encoder.encoder.layers=self.encoder.encoder.layers[:12]
        self.encoder.eval().to(device)
        self.extractor=Wav2Vec2FeatureExtractor.from_pretrained(str(paths['seed-content']),local_files_only=True)
        self.speaker=CAMPPlus(feat_dim=80,embedding_size=192)
        self.speaker.load_state_dict(torch.load(paths['seed-speaker']/'campplus_cn_common.bin',map_location='cpu',weights_only=True));self.speaker.eval().to(device)
        hift=yaml.safe_load((Path(__file__).parent/'seed_vendor/configs/hifigan.yml').read_text())
        self.vocoder=HiFTGenerator(**hift['hift'],f0_predictor=ConvRNNF0Predictor(**hift['f0_predictor']))
        self.vocoder.load_state_dict(torch.load(paths['seed-vocoder']/'hift.pt',map_location='cpu',weights_only=True));self.vocoder.eval().to(device)
        for net in (self.encoder,self.speaker,self.vocoder):
            for parameter in net.parameters():parameter.requires_grad_(False)
        self.prompt=None;self.reference_key=None;self.adapter_key=None
        self.final_parameters={name:p for name,p in self.model.cfm.named_parameters() if name.startswith(('estimator.final_layer.', 'estimator.final_mlp.'))}
        self.baseline={name:p.detach().cpu().clone() for name,p in self.final_parameters.items()}
    def wave(self,path,limit=None):
        import torch,torchaudio
        data,sr=sf.read(path,dtype='float32',always_2d=True)
        if limit:data=data[:int(sr*limit)]
        values=torch.from_numpy(data.mean(axis=1)).to(self.device)
        return torchaudio.functional.resample(values,sr,self.sr) if sr!=self.sr else values
    def features(self,wave):
        import torch,torchaudio
        from .seed_vendor.modules.audio import mel_spectrogram
        sample=torchaudio.functional.resample(wave,self.sr,16000)
        inputs=self.extractor(sample.detach().cpu().numpy(),sampling_rate=16000,return_tensors='pt',padding=True)
        semantic=self.encoder(inputs.input_values.to(self.device)).last_hidden_state.float()
        feat=torchaudio.compliance.kaldi.fbank(sample.unsqueeze(0),num_mel_bins=80,dither=0,sample_frequency=16000)
        style=self.speaker((feat-feat.mean(0,keepdim=True)).unsqueeze(0))
        mel=mel_spectrogram(wave.unsqueeze(0),n_fft=1024,num_mels=80,sampling_rate=self.sr,hop_size=256,win_size=1024,fmin=0,fmax=8000,center=False)
        return semantic,mel,style
    def select_adapter(self,path=None):
        import torch
        from safetensors.torch import load_file
        key=None
        if path:
            path=Path(path);meta=json.loads(path.with_suffix('.json').read_text())
            digest=sha256(path)
            if digest!=meta['sha256']:raise ValueError('Adaptation checkpoint integrity failed')
            key=(str(path.resolve()),digest)
        if key==self.adapter_key:return
        values=self.baseline if path is None else load_file(str(path),device='cpu')
        if set(values)!=set(self.final_parameters):raise ValueError('Adaptation contains unexpected parameter names')
        with torch.no_grad():
            for name,param in self.final_parameters.items():
                if values[name].shape!=param.shape:raise ValueError('Adaptation shape does not match the shared engine')
                param.copy_(values[name].to(self.device))
        self.adapter_key=key;self.reference_key=None;self.prompt=None
    def prepare(self,reference):
        import torch
        reference=Path(reference);stat=reference.stat();key=(str(reference.resolve()),stat.st_size,stat.st_mtime_ns,self.adapter_key)
        if self.reference_key!=key:
            semantic,mel,style=self.features(self.wave(reference,3))
            condition=self.model.length_regulator(semantic,ylens=torch.tensor([mel.shape[-1]],device=self.device),n_quantizers=3,f0=None)[0]
            self.prompt=(condition,mel,style);self.reference_key=key
    def convert_values(self,values,sr,reference,steps=4,cfg=0.7,adapter=None):
        import torch,torchaudio
        self.select_adapter(adapter)
        with torch.inference_mode():
            self.prepare(reference);prompt,mel,style=self.prompt
            wave=torch.as_tensor(values,dtype=torch.float32,device=self.device)
            if sr!=self.sr:wave=torchaudio.functional.resample(wave,sr,self.sr)
            sample=torchaudio.functional.resample(wave,self.sr,16000)
            inputs=self.extractor(sample.cpu().numpy(),sampling_rate=16000,return_tensors='pt')
            semantic=self.encoder(inputs.input_values.to(self.device)).last_hidden_state.float()
            length=max(1,int(len(wave)//256));condition=self.model.length_regulator(semantic,ylens=torch.tensor([length],device=self.device),n_quantizers=3,f0=None)[0]
            combined=torch.cat([prompt,condition],dim=1)
            target=self.model.cfm.inference(combined,torch.tensor([combined.shape[1]],device=self.device),mel,style,None,n_timesteps=steps,inference_cfg_rate=cfg)
            output=self.vocoder(target[:,:,mel.shape[-1]:]).squeeze().cpu().numpy().reshape(-1)
        if not len(output) or not np.isfinite(output).all():raise ValueError('Seed engine returned invalid audio')
        return output,self.sr
    def convert(self,source,reference,settings,adapter=None):
        values,sr=sf.read(source,dtype='float32',always_2d=True)
        return self.convert_values(values.mean(axis=1),sr,reference,settings.get('seed_steps',4),settings.get('seed_cfg',.7),adapter)
    def adapt(self,recordings,target,steps,progress):
        """Experimental final-head adaptation; frozen shared engine weights are never rewritten."""
        import torch
        from safetensors.torch import save_file
        self.select_adapter(None)
        samples=[]
        with torch.no_grad():
            for path in recordings:
                semantic,mel,style=self.features(self.wave(path,4))
                lengths=torch.tensor([mel.shape[-1]],device=self.device)
                condition=self.model.length_regulator(semantic,ylens=lengths,n_quantizers=3,f0=None)[0]
                samples.append((mel,condition,style,lengths))
        if not samples:raise ValueError('Add an authorized reference before adaptation')
        for net in self.model.values():
            for p in net.parameters():p.requires_grad_(False)
        for p in self.final_parameters.values():p.requires_grad_(True)
        optimizer=torch.optim.AdamW(self.final_parameters.values(),lr=1e-5)
        losses=[]
        try:
            for step in range(steps):
                progress(step,steps,None)
                mel,condition,style,lengths=samples[step%len(samples)]
                prompt=torch.tensor([int(mel.shape[-1]*.25)],device=self.device)
                optimizer.zero_grad(set_to_none=True)
                loss,_=self.model.cfm(mel,lengths,prompt,condition.clone(),style)
                if not torch.isfinite(loss):raise ValueError('Adaptation loss is invalid; no checkpoint saved')
                loss.backward();torch.nn.utils.clip_grad_norm_(self.final_parameters.values(),1.0);optimizer.step()
                losses.append(float(loss.detach()));progress(step+1,steps,losses[-1])
            target=Path(target)
            save_file({name:p.detach().cpu().contiguous() for name,p in self.final_parameters.items()},str(target))
            metadata={'sha256':sha256(target),'steps':steps,'losses':losses,'method':'Experimental final-head flow-matching adaptation; not upstream full fine-tuning','activated':False}
            target.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
            return metadata
        finally:
            for p in self.final_parameters.values():p.requires_grad_(False)
            self.adapter_key='training';self.select_adapter(None)
