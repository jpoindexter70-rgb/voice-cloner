"""Public official Seed-VC assets, verified through the shared downloader."""
from pathlib import Path
from .models import download, verify
ASSETS={
 'seed-core':{'revision':'257283f9f41585055e8f858fba4fd044e5caed6e','repository':'Plachta/Seed-VC','files':['DiT_uvit_tat_xlsr_ema.pth','config_dit_mel_seed_uvit_xlsr_tiny.yml']},
 'seed-speaker':{'revision':'e4b6ede7ce16997aff4ae69fbca1f0175e2afede','repository':'funasr/campplus','files':['campplus_cn_common.bin']},
 'seed-vocoder':{'revision':'24c40509c3c5ea6fe06b5f8790ff99e3714a6bee','repository':'FunAudioLLM/CosyVoice-300M','files':['hift.pt']},
 'seed-content':{'revision':'1a640f32ac3e39899438a2931f9924c02f080a54','repository':'facebook/wav2vec2-xls-r-300m','files':['config.json','preprocessor_config.json','pytorch_model.bin']},
}
def installed(root):
 return all((Path(root)/name/'manifest.json').exists() and all((Path(root)/name/f).exists() for f in spec['files']) for name,spec in ASSETS.items())
def verify_all(root):
 return {name:verify(root,name,spec) for name,spec in ASSETS.items()}
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['download','verify']);parser.add_argument('--root',required=True);args=parser.parse_args()
 for name,spec in ASSETS.items():(download if args.command=='download' else verify)(args.root,name,spec)
