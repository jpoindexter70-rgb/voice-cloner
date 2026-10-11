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


def process(path,target,speed=1,pitch=0,start=0,end=None,denoise=False,volume=1,noise_strength=12,warmth=0,brightness=0,softness=0,clarity=0):
    filters=[]
    if start or end is not None:
        trim = f'atrim=start={start}'
        if end is not None:trim += f':end={end}'
        filters.extend([trim, 'asetpts=PTS-STARTPTS'])
    if pitch:
        factor=2**(pitch/12)
        input_rate = sf.info(path).samplerate
        filters.extend([f'asetrate={input_rate}*{factor}', 'aresample=24000',f'atempo={1/factor}'])
    if speed!=1:filters.append(f'atempo={speed}')
    if denoise and noise_strength:filters.append(f'afftdn=nr={noise_strength}:nf=-35:tn=1')
    if warmth:filters.append(f'bass=g={warmth}:f=180:t=q:w=0.7')
    if brightness:filters.append(f'treble=g={brightness}:f=3500:t=q:w=0.7')
    if clarity:filters.append(f'equalizer=f=2500:t=q:w=1:g={clarity*.06}')
    if softness:
        filters.extend([f'lowpass=f={12000-80*softness}:p=2',f'acompressor=threshold=0.2:ratio={1+softness*.03}:attack=15:release=150:makeup=1'])
    if volume!=1:filters.append(f'volume={volume}')
    filters.append('alimiter=limit=0.97:level=false:latency=true')
    command=[ffmpeg(),'-v','error','-nostdin','-y','-i',str(path)]
    if filters:command.extend(['-af',','.join(filters)])
    command.extend(['-ac','1','-ar','24000',str(target)])
    result=subprocess.run(command,capture_output=True,timeout=180)
    if result.returncode:raise RuntimeError('Audio processing failed: '+result.stderr.decode(errors='replace')[:300])


def voice_processing(settings):
    return {key:settings.get(key,default) for key,default in [('speed',1),('pitch',0),('volume',1),('denoise',False),('noise_strength',12),('warmth',0),('brightness',0),('softness',0),('clarity',0)]}

def needs_processing(settings):
    options=voice_processing(settings)
    return options['speed']!=1 or options['pitch']!=0 or options['volume']!=1 or options['denoise'] or any(options[key] for key in ('warmth','brightness','softness','clarity'))
