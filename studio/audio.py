import shutil
import subprocess
import uuid
import numpy as np
import soundfile as sf
from scipy import signal

MAX_SECONDS = 600


def ffmpeg():
    system = shutil.which('ffmpeg')
    if system:
        return system
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode(source, target):
    proc = subprocess.run([ffmpeg(), '-nostdin', '-v', 'error', '-y', '-protocol_whitelist', 'file,pipe',
                           '-format_whitelist', 'wav,mp3,flac,ogg,mov,matroska,webm,aac,aiff', '-i', str(source),
                           '-t', str(MAX_SECONDS + 1), '-vn', '-ac', '1', '-ar', '24000',
                           '-c:a', 'pcm_s16le', str(target)], capture_output=True, timeout=120)
    if proc.returncode:
        raise ValueError('Cannot decode this recording. Use WAV, MP3, FLAC, OGG, M4A, or browser WebM audio.')
    audio, sr = sf.read(target, dtype='float32')
    if len(audio) < sr // 4 or len(audio) > sr * MAX_SECONDS:
        raise ValueError('Recordings must be between 0.25 seconds and 10 minutes.')
    if not np.isfinite(audio).all():
        raise ValueError('Recording contains invalid samples.')
    return analyze(audio, sr)


def analyze(audio, sr):
    audio = np.asarray(audio).reshape(-1)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    seconds = len(audio) / sr
    warnings = []
    if seconds < 6:
        warnings.append('For cloning, record at least 6 seconds; 10–15 seconds of clear speech is preferable.')
    if seconds > 20:
        warnings.append('Engine conditioning uses only the first 6–15 seconds; trim to the clearest passage.')
    clipped = float(np.mean(np.abs(audio) >= .995))
    if clipped > .001:
        warnings.append('Clipping detected. Reduce microphone gain and record again.')
    if rms < .01:
        warnings.append('Very quiet audio. Move closer to the microphone or increase gain.')
    windows = [audio[i:i + max(1, sr // 20)] for i in range(0, len(audio), max(1, sr // 20))]
    quiet_rms = float(np.quantile([np.sqrt(np.mean(w ** 2)) for w in windows], .1))
    if quiet_rms > .02:
        warnings.append('The quietest passages are loud. Check for background noise or record pauses; continuous speech can also trigger this warning.')
    return {'seconds': round(seconds, 3), 'sample_rate': sr, 'peak_db': round(20 * np.log10(max(peak, 1e-9)), 1),
            'rms_db': round(20 * np.log10(max(rms, 1e-9)), 1), 'clipped_fraction': clipped,
            'quiet_floor_db': round(20 * np.log10(max(quiet_rms, 1e-9)), 1), 'warnings': warnings}


def waveform(path, points=800):
    x, sr = sf.read(path, dtype='float32')
    groups = np.array_split(x, min(points, len(x)))
    return {'peaks': [float(np.max(np.abs(g))) for g in groups], 'seconds': len(x) / sr}


def edit(source, target, start, end, remove_silence, denoise, speed, pitch, volume=1, normalize=False):
    x, sr = sf.read(source, dtype='float32')
    duration = len(x) / sr
    end = duration if end is None else end
    if not 0 <= start < end <= duration + .001:
        raise ValueError('Trim range must be within the recording.')
    x = x[int(start * sr):int(min(end, duration) * sr)]
    if remove_silence:
        # Retain 100 ms around speech; remove silent spans, not individual samples.
        hop = int(.02 * sr)
        frames = [x[i:i + hop] for i in range(0, len(x), hop)]
        active = np.array([np.sqrt(np.mean(f ** 2)) > .008 for f in frames])
        active = np.convolve(active.astype(int), np.ones(11), mode='same') > 0
        # np.convolve('same') can be longer for tiny clips.
        active = active[:len(frames)]
        x = np.concatenate([f for f, keep in zip(frames, active) if keep]) if active.any() else np.array([], dtype=np.float32)
    if len(x) < sr // 4:
        raise ValueError('Editing leaves less than 0.25 seconds. Reduce trimming or disable silence removal.')
    if denoise:
        # Conservative spectral gate estimated from the quietest 10% of frames.
        _, _, spec = signal.stft(x, sr, nperseg=1024, noverlap=768)
        mag = np.abs(spec)
        noise = np.quantile(mag, .1, axis=1, keepdims=True)
        mask = np.clip(1 - (noise / np.maximum(mag, 1e-8)) ** 2, .2, 1)
        _, x = signal.istft(spec * mask, sr, nperseg=1024, noverlap=768)
    sf.write(target, x, sr, subtype='PCM_16')
    if speed != 1 or pitch != 0:
        ratio = 2 ** (pitch / 12)
        tempo = speed / ratio
        stages = []
        while tempo < .5:
            stages.append('atempo=0.5'); tempo /= .5
        while tempo > 2:
            stages.append('atempo=2'); tempo /= 2
        stages.append(f'atempo={tempo}')
        filters = f'asetrate={sr * ratio},aresample={sr},' + ','.join(stages)
        temp = target.with_name(uuid.uuid4().hex + '.wav')
        try:
            proc = subprocess.run([ffmpeg(), '-nostdin', '-v', 'error', '-y', '-i', str(target),
                                   '-af', filters, str(temp)], capture_output=True, timeout=120)
            if proc.returncode:
                raise ValueError('FFmpeg could not apply pitch/speed processing.')
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
    x, sr = sf.read(target, dtype='float32')
    if normalize:
        peak = np.max(np.abs(x))
        if peak > 0:
            x = x * (.95 / peak)
    x = np.clip(x * volume, -1, 1)
    sf.write(target, x, sr, subtype='PCM_16')
    return analyze(x, sr)


def export_mp3(source, target, synthetic=False):
    proc = subprocess.run([ffmpeg(), '-nostdin', '-v', 'error', '-y', '-i', str(source),
                           '-c:a', 'libmp3lame', '-q:a', '2', '-metadata',
                           'comment=AI-GENERATED SYNTHETIC AUDIO; Voice Control Room' if synthetic else 'comment=Reference recording; Voice Control Room', str(target)],
                          capture_output=True, timeout=120)
    if proc.returncode:
        raise ValueError('MP3 export failed. Run diagnostics to check FFmpeg.')
