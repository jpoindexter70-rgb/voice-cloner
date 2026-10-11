"""Optional local installation: isolated app, D: data, verified models."""
import os
import subprocess
import sys
from pathlib import Path


def run(command,env):subprocess.run(command,check=True,env=env)


def main():
    if sys.version_info[:2]!=(3,11):raise RuntimeError('Use Python 3.11 for the local engine installation.')
    source=Path(__file__).resolve().parents[1];os.chdir(source)
    data=Path(os.environ['STUDIO2_DATA_DIR']) if os.getenv('STUDIO2_DATA_DIR') else Path('D:/AI-Voice-Cloning-Studio') if os.name=='nt' else source/'.runtime'
    if os.name=='nt' and not os.getenv('STUDIO2_DATA_DIR') and not Path('D:/').exists():raise RuntimeError('D: is unavailable. Choose STUDIO2_DATA_DIR explicitly; no automatic C: fallback.')
    data.mkdir(parents=True,exist_ok=True);(data/'temporary').mkdir(exist_ok=True)
    env=dict(os.environ,STUDIO2_DATA_DIR=str(data),PIP_CACHE_DIR=str(data/'pip-cache'),HF_HOME=str(data/'model-cache'),NUMBA_CACHE_DIR=str(data/'numba-cache'),TMP=str(data/'temporary'),TEMP=str(data/'temporary'),TMPDIR=str(data/'temporary'))
    environment=source/'.venv-ai';python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    print('[1/4] Preparing the separate Studio 2.0 Python environment',flush=True)
    if not python.exists():run([sys.executable,'-m','venv',str(environment)],env)
    use_cuda=False
    if os.name=='nt':
        try:use_cuda=subprocess.run(['nvidia-smi'],capture_output=True,timeout=10).returncode==0
        except (OSError,subprocess.TimeoutExpired):pass
    index='https://download.pytorch.org/whl/cu124' if use_cuda else 'https://download.pytorch.org/whl/cpu'
    print('[2/4] Installing trusted engine packages ('+('CUDA 12.4' if use_cuda else 'CPU')+')',flush=True)
    run([str(python),'-m','pip','install','torch==2.6.0','torchaudio==2.6.0','--index-url',index],env)
    run([str(python),'-m','pip','install','-r','requirements-engine.txt'],env)
    run([str(python),'-m','pip','check'],env)
    print('[3/4] Checking shared models; valid existing weights are reused',flush=True)
    for engine in ('expressive','turbo'):
        check=subprocess.run([str(python),'-m','studio.models','verify','--root',str(data/'shared-models'),'--engine',engine],env=env,capture_output=True)
        if check.returncode:
            run([str(python),'-m','studio.models','download','--root',str(data/'shared-models'),'--engine',engine],env)
        else:print('Reusing verified '+engine+' model; no download needed.',flush=True)
    check=subprocess.run([str(python),'-m','studio.seed_assets','verify','--root',str(data/'shared-models')],env=env,capture_output=True)
    if check.returncode:run([str(python),'-m','studio.seed_assets','download','--root',str(data/'shared-models')],env)
    else:print('Reusing verified Seed conversion models; no download needed.',flush=True)
    print('[4/4] Full local engine installation complete. Start Studio 2.0.cmd opens the browser.',flush=True)


if __name__=='__main__':main()
