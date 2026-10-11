"""Real decode/encode and conservative non-destructive processing."""
import io
import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf


def ffmpeg():
    binary=shutil.which('ffmpeg')
    if binary:return binary
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode(payload, temporary=None):
    try:return sf.read(io.BytesIO(payload),dtype='float32',always_2d=True)
    except Exception:
        with tempfile.TemporaryDirectory(prefix='studio2-decode-', dir=temporary) as temp:
            source=Path(temp)/'source';target=Path(temp)/'decoded.wav';source.write_bytes(payload)
            result=subprocess.run([ffmpeg(),'-v','error','-nostdin','-y','-i',str(source),'-t','121','-ac','1','-ar','24000',str(target)],capture_output=True,timeout=45)
            if result.returncode or not target.exists():raise ValueError('This audio format cannot be decoded; use WAV, FLAC, MP3 or a browser recording.')
            return sf.read(target,dtype='float32',always_2d=True)


def wav_bytes(values,sr):
    out=io.BytesIO();sf.write(out,values,sr,format='WAV',subtype='PCM_16');return out.getvalue()


def process(path,target,speed=1,pitch=0,start=0,end=None,denoise=False):
    filters=[]
    if pitch:
        factor=2**(pitch/12)
        filters.extend([f'asetrate=24000*{factor}', 'aresample=24000',f'atempo={1/factor}'])
    if speed!=1:filters.append(f'atempo={speed}')
    if denoise:filters.append('afftdn=nf=-25')
    command=[ffmpeg(),'-v','error','-nostdin','-y','-i',str(path),'-ss',str(start)]
    if end is not None:command.extend(['-t',str(end-start)])
    if filters:command.extend(['-af',','.join(filters)])
    command.extend(['-ac','1','-ar','24000',str(target)])
    result=subprocess.run(command,capture_output=True,timeout=180)
    if result.returncode:raise RuntimeError('Audio processing failed: '+result.stderr.decode(errors='replace')[:300])
