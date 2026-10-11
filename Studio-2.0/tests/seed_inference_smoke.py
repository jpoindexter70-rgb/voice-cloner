"""Opt-in real Seed inference/adaptation using an explicitly synthetic reference."""
from studio.seed import SeedEngine
from pathlib import Path
import time,soundfile as sf
start=time.monotonic();engine=SeedEngine(Path('.runtime/shared-models'),'cpu')
ref=next(Path('.runtime/performance-inference-qa/family-profiles').glob('*/references/*'))
source=Path('.runtime/seed-test-input.wav');values,sr=sf.read(ref);sf.write(source,values[:sr*3],sr)
print('REAL Seed loaded in',round(time.monotonic()-start,2),'seconds',flush=True)
start=time.monotonic();audio,rate=engine.convert(source,ref,{'seed_steps':4,'seed_cfg':.7})
assert len(audio)>rate and len(audio)<rate*5
sf.write('.runtime/seed-validation.wav',audio,rate)
print('REAL Seed conversion',len(audio)/rate,'seconds in',round(time.monotonic()-start,2),'seconds',flush=True)
target=Path('.runtime/seed-validation-adaptation.safetensors')
result=engine.adapt([ref],target,2,lambda current,total,loss:print('REAL adaptation',current,total,loss,flush=True))
assert target.stat().st_size<5_000_000
print('REAL adaptation checkpoint verified:',target.stat().st_size,flush=True)
engine.select_adapter(target)
audio,rate=engine.convert(source,ref,{'seed_steps':4,'seed_cfg':.7},target)
assert len(audio)>rate
print('REAL adapted conversion passed',flush=True)
