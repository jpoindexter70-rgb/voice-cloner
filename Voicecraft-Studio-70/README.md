# Voicecraft Studio 70

**Your voice. Your stories.** A local Windows desktop voice-cloning application with its own embedded window. This preserves the VoiceCraft Studio 1.0.0 voice workflow while replacing its external-browser launch. No command window, password screen, or separate browser is required for normal use.

## Install and open

Download **Voicecraft-Studio-70-Setup.exe**, double-click it, complete installation, and open the **Voicecraft Studio 70** desktop shortcut. Do not extract the source ZIP or launch the legacy `.cmd` development helpers to use the desktop application.

First setup uses a graphical progress/diagnostics window. It downloads a checksum-verified official Electron desktop renderer, Python engine dependencies, and verified original Chatterbox and Chatterbox Turbo model files. Keep internet connected during first setup. Later inference and recordings remain local. Downloads can take several minutes or longer depending on connection speed. If setup fails, the graphical window displays the actual error and offers Retry. The installer is unsigned.

The app opens in its own window. Closing it asks for confirmation, stops its local engine, and ends its launcher; an unfinished generation can be interrupted. An engine process remains necessary internally, but no terminal or separate browser is visible.

## Features retained

- Voice recording with live meter, import, playback, original preservation, and short/full/expressive reading scripts.
- Separate authorized family profiles, per-profile recordings/settings/audio, consent revocation and child access restrictions.
- Chatterbox Turbo and original Chatterbox synthesis; in-app model installation/repair and local engine management.
- Pitch, speed, volume, and configurable recording noise reduction, with preview before saving.
- YouTube script editor, short audio previews, complete narration, generated-audio adjustment previews and edited copies.
- Normal, Storytelling, Bedtime Reading, Energetic Character, Calm Narration, Horror/Suspense, YouTube Presenter, Food Narration, Toy/Product Demo, Product Review presets.
- WAV/MP3 export through a native Save As dialog, rename, individual/bulk/history/profile deletion, backup and restore.
- Charcoal interface, black accents, silver microphone cover/icon, and native storage folder chooser.

Styles are auditable delivery presets rather than a guaranteed emotion/acting API. A 5–10-second preview describes audio length, not guaranteed processing time. Voice similarity depends on the input recording and model. Noise reduction cannot restore severely damaged audio.

## Storage and older installations

This release installs separately under `%LOCALAPPDATA%\Programs\Voicecraft Studio 70`. Its renderer/config live under `%LOCALAPPDATA%\Voicecraft-Studio-70`; its default voice data use `D:\Voicecraft-Studio-70` if D: exists, otherwise `%LOCALAPPDATA%\Voicecraft-Studio-70\data`. Electron window state/cache use `%APPDATA%\Voicecraft-Studio-70`. Models are shared by this app's profiles rather than copied per voice.

Older VoiceCraft/Voice Control Room installations and data are untouched. No automatic migration of older profiles/models is performed. To bring existing profiles across, create a backup in the older app and restore it through this app's existing backup/restore controls. Do not run two applications against the same data folder simultaneously. Choosing another folder changes the storage selection; it does not move files. Uninstall removes this installation's payload and shortcuts; voice data and downloaded renderer outside the installation remain available.

## Connections and project structure

- `studio/app.py`: local FastAPI API, profile/consent/storage/recording/edit/export/model operations and CSRF protections.
- `studio/static/`: existing interface and artwork. Same local controls render in the desktop window.
- `studio/engine.py`: original unmodified VoiceCraft 1.0.0 engine adapter, imports `ChatterboxTurboTTS` or `ChatterboxTTS` and loads verified local checkpoints.
- `studio/models.py`: official pinned Hugging Face revisions with size/hash validation and corrupt-cache repair.
- `studio/audio.py`, `jobs.py`, `styles.py`: FFmpeg processing, serialized generation, and delivery presets.
- `scripts/desktop.py`: installs engine dependencies and a hash-verified official renderer, starts the loopback-only engine on port **8791**, launches the embedded window, and stops the engine when the window closes.
- `desktop/main.cjs`: Electron desktop window; sandbox/context isolation on, Node access off, microphone permission only for the local UI, external navigation/new windows denied, native export dialogs, close confirmation and single-instance activation.
- `packaging/launcher.c`: native GUI first-setup diagnostics, hidden subprocesses, process-tree cleanup, tray activation during use, native storage chooser.
- `packaging/installer.nsi`: per-user x64 installer and uninstaller. No security settings are disabled.
- `packaging/build_windows.py`: validates the pinned PSF Python runtime and builds the launcher/installer; `python-runtime.json` and `electron-runtime.json` pin official download URLs and hashes.
- `tests/`: backend regression and desktop release checks. Tests use separate synthetic data.
- Legacy CMD/browser/deployment helpers remain for editable source compatibility; they are not the normal desktop launch route. The desktop launcher clears hosted-mode configuration.

No model weights, virtual environments, private recordings, tokens, or caches are distributed in the editable source ZIP.

## Versions and rebuilding

Product version: **70.0.0** (display name Voicecraft Studio 70). Windows bundled Python **3.11.9 x64**; cloud test Python **3.11.16**. Electron **44.7.0**. Both Chatterbox integrations use **chatterbox-tts 0.1.7**. Torch/torchaudio **2.6.0**, CPU build `+cpu` tested; installer selects CUDA **12.4** packages when NVIDIA is detected and falls back to CPU if GPU package installation fails. Physical CUDA execution must be tested on the target PC.

Major pins: FastAPI **0.115.12**, Uvicorn **0.34.2**, SoundFile **0.13.1**, NumPy **1.26.4**, imageio-ffmpeg **0.6.0**, setuptools **78.1.0**, munch **4.0.0**. Full Windows dependency constraints are in `requirements-windows-lock.txt`; renderer uses Node only internally and no npm install is required for normal app use.

To rebuild, install Python 3.11+, MinGW-w64 GCC/windres and NSIS 3.11+, then run from this directory:

```text
python packaging/build_windows.py
```

Output: `dist/Voicecraft-Studio-70-Setup.exe` and checksums. Linux cross-build additionally supports `--tools-root PATH`, `--stage PATH`, `--output PATH`. The renderer itself is downloaded on first launch from the official pinned release after SHA-256 validation; its app code is included in the installer.

For backend development, install the existing requirements into an isolated environment and run `python -m uvicorn studio.app:create_app --factory --host 127.0.0.1 --port 8791` with a separate `STUDIO2_DATA_DIR`. Run `python -m pytest tests -q`. For desktop development, run the pinned Electron runtime against `desktop/` with the local engine running. Consult `docs/STANDALONE-VALIDATION.md` for actual validation results and limitations.
