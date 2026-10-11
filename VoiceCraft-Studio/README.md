# VoiceCraft Studio 1.0.0

**Your voice. Your stories.** A simple local voice-cloning and YouTube narration app, developed from the available Studio source. This is a new product release name, not a claim that the unavailable Family AI Voice Cloner Pro 0.3.0 source was recovered.

## Windows installation and launch

Double-click **VoiceCraft-Studio-1.0.0-Setup.exe**, choose a separate installation folder, and finish setup. Open the **VoiceCraft Studio** desktop shortcut. The installer bundles the Python Software Foundation's 64-bit Python 3.11.9 runtime. No separate Python installation, ZIP extraction, PowerShell, password, or visible console is required for normal use.

First launch shows a graphical setup window while it installs pinned dependencies and downloads and verifies official Chatterbox Turbo and Original checkpoints. Internet and several GB of free space are required for that first preparation. This is a network installer, not an offline model bundle. Valid existing VoiceCraft checkpoints are reused. Subsequent launches open the local browser interface; a tray icon provides **Open VoiceCraft** and **Exit VoiceCraft**. Closing the browser alone does not stop the engine. Setup errors remain in the graphical diagnostics window with a Retry button.

The app is served only on `127.0.0.1:8790`. Recordings are not uploaded. Models, audio, cache, and temporary files default to `D:\VoiceCraft-Studio` when D: exists; otherwise `%LOCALAPPDATA%\VoiceCraft-Studio\data` is used. **Storage & Privacy → Choose Storage Folder** opens a Windows folder picker. Restart from the tray/shortcut to use the selected folder. Changing folders does not move, merge, or delete existing libraries. Return to the earlier folder to see that library again. User configuration is `%LOCALAPPDATA%\VoiceCraft-Studio\desktop.json` and `storage.txt`.

The installer refuses a nonempty unrelated folder. Uninstall removes this application's installation files and shortcuts, preserving voice data, models, and other applications. Exported audio and backups require separate deletion. Your existing VoiceControlRoom/0.3.0 installation and database are not changed or automatically migrated: import your authorized original audio explicitly.

## Using the studio

1. Add a voice profile, using your own voice or documenting an adult speaker's permission. Child voices remain locked because independent guardian verification is not implemented.
2. Select the voice and click **Record My Voice** or **Import Recording**.
3. Use the recording script panel: short, full, or optional expressive passages. Read in your everyday voice, in a quiet room, with consistent microphone distance. The script is editable. Capture a clean 15–30-second sample; Turbo requires more than five seconds. Recording/import references are limited to 3–120 seconds and 25 MB.
4. Listen to your recording. Optionally preview pitch, speed, volume, and noise reduction before saving. Changed settings require a new preview. The original imported/recorded bytes are preserved separately. Saved references can also be edited into new copies. Select **Use as Reference** on the copy you want to condition the engine.
5. Paste a YouTube narration script, select a style, and adjust pitch, speed, and volume. Generate a short preview, listen, change settings and preview again, then generate the full narration.
6. Play, rename, adjust, or export generated audio as WAV/MP3. Finished-audio editing creates a new copy; it does not overwrite the original. Delete individual items, selected outputs, all history for a voice, all generated history, or an entire profile with confirmation.

There is no separate login/account system. Voice profiles are the user/speaker entries that can be removed. History clearing preserves original references and profiles. Revocation blocks access; deleting the profile removes its associated app data.

## Speaking styles and voice adjustments

Styles: **Normal / My Voice, Storytelling, Bedtime Reading, Energetic Character, Calm Narration, Horror / Suspense, YouTube Presenter, Food Narration, Toy / Product Demo, Product Review**.

`studio/styles.py` defines real delivery presets combining pacing, pitch, volume, inter-segment pauses, temperature, and Original's supported expression parameter. Turbo does **not** have a native named emotion/acting-style API; these are delivery presets, not guaranteed expressive acting. Preview them with your own reference. The worker preserves both user settings and effective preset settings in output metadata. Pitch/speed/volume are processed through FFmpeg after synthesis. Noise reduction uses adjustable FFmpeg spectral denoising. Strong processing may reduce voice similarity; keep the original and compare before saving.

A preview uses the first 24 words (up to 180 characters) and caps resulting audio at 5–10 seconds according to the preview endpoint. Very short scripts produce shorter previews; no filler is added. This is audio duration, not a promise of 5–10-second processing. CPU generation and first model loading can be slower.

## Project structure and integration

- `studio/app.py`: FastAPI API, profile isolation, consent, imports, reference/output edits, export, model setup, and deletion.
- `studio/static/`: browser interface; `app.js` retains the original capture/library paths, `simple.js` supplies the voiceover workflow, `voicecraft.js` adds recording scripts and editing/style controls. `cover.svg` and the matching desktop ICO are local assets.
- `studio/engine.py`: verified local `ChatterboxTurboTTS` and `ChatterboxTTS` integrations. Each segment prepares the correct profile's selected reference. The serialized worker prevents concurrent model inference; Auto handles unavailable CUDA and GPU-memory fallback.
- `studio/models.py`: official Hugging Face downloads pinned to tested revisions, with upstream size/hash verification. Models are shared across profiles.
- `studio/jobs.py`: persistent jobs, progress, cancellation, style application, audio processing, and recovery after interrupted work.
- `studio/audio.py`: real decode/encode and FFmpeg audio processing. `imageio-ffmpeg` supplies FFmpeg when no system binary is available.
- `scripts/desktop.py`: Windows dependency/model preparation, storage configuration, hidden subprocesses, and loopback startup.
- `packaging/launcher.c`: native graphical setup/diagnostics window and tray launcher. Its job object stops only its own process tree when exiting.
- `packaging/installer.nsi`, `build_windows.py`, `launcher.rc`, `voicecraft.ico`, `python-runtime.json`: editable Windows installer/launcher build sources and pinned runtime checksum.
- `tests/`: existing regressions plus VoiceCraft processing/style/edit tests and browser validation.

Legacy advanced modules/launchers are retained in source for compatibility. They are not the normal VoiceCraft desktop startup path. Earlier Studio documentation describes older builds; use this README and `docs/VOICECRAFT-VALIDATION.md` for this release.

## Dependencies and versions

Windows bundled Python **3.11.9 x64**; cloud validation Python **3.11.16**. Chatterbox and Turbo both use **chatterbox-tts 0.1.7**. PyTorch/torchaudio **2.6.0**; CPU validation used **2.6.0+cpu**. First Windows preparation detects NVIDIA with `nvidia-smi` and attempts CUDA **12.4** wheels; package-install failure falls back to CPU. Engine Auto falls back to CPU if CUDA is unavailable or GPU memory is exhausted. CUDA/RTX 2060 operation has not been physically verified. `VOICECRAFT_FORCE_CPU=1` forces CPU installation for automation.

Major pins: FastAPI **0.115.12**, Uvicorn **0.34.2**, SoundFile **0.13.1**, NumPy **1.26.4**, imageio-ffmpeg **0.6.0**, Transformers **5.2.0**, Diffusers **0.29.0**, setuptools **78.1.0**, munch **4.0.0**. `requirements-windows-lock.txt` constrains Windows transitive dependencies. `requirements-engine-lock.txt` preserves the earlier Linux engine environment. Models and virtual environments are excluded from source distribution.

## Rebuilding the Windows installer

Use Python 3.11 or newer for the build helper, a MinGW-w64 x64 compiler with windres, and NSIS 3.11 or newer with the amd64 Unicode target. Build tools are needed by developers only.

From the project folder:

```text
python packaging/build_windows.py
```

Output: `dist/VoiceCraft-Studio-1.0.0-Setup.exe` and `SHA256SUMS.txt`. Put MinGW/NSIS on PATH; or pass `--tools-root` for an extracted Linux cross-compiler installation. `--stage` and `--output` select isolated build/output locations. The helper fetches the official CPython NuGet package, checks its pinned SHA-256 and ZIP integrity, builds the GUI launcher with warnings treated as errors, and embeds only source and the runtime. It does not bundle personal recordings or model weights. The installer is not Authenticode-signed; a signing certificate has not been supplied.

For Linux development use the prepared Python 3.11 engine environment, install `requirements-engine.txt`, and start `python -m studio --no-browser` with explicit isolated `STUDIO2_DATA_DIR`, `STUDIO2_MODEL_DIR`, and `PORT`. Run `python -m pytest -q`. The CLI's older default port is 8770; the Windows desktop wrapper intentionally uses 8790.

Read `docs/VOICECRAFT-VALIDATION.md` for actual checks and hardware limitations. No test establishes a perfect duplicate of a person's voice or guarantees zero problems on every Windows installation.
