# AI Voice Cloning Studio 2.0

Independent browser application with a new Family Voice Library and real neural voice engine integration. Existing Voice Control Room files are unchanged.

Implemented: separate family cards, names/avatars, authorization records, language/accent preferences, per-profile engine/settings, microphone capture with selection, pause/resume and live waveform/meter, import/preview/signal checks, original-preserving normalized references and edits, reference selection, serialized speech jobs, long-text segmentation, batch scripts, recorded voice conversion, progress/cancellation/recovery, generated history/playback, waveform seeking, listening ratings, WAV/MP3 export, model unloading, disk dashboard, safe temporary cleanup and private verified backup/restore. Child voices stay locked pending verified guardian authorization. English synthesis is supported; language preferences do not imply an unsupported engine language.

Real Expressive/Turbo inference, conversion and browser export checks passed. See [validation](docs/VALIDATION.md) for exact scope. Naturalness and personal similarity are not yet assessed with family speech. Live conversion and verified child-account access remain unavailable.

## Use on your Windows computer

The intended setup is local: the browser opens the Studio running on your own computer. No Hugging Face account, hosting token or hosted password is needed. On first use, public model/package downloads need internet; verified installed models are reused on repair and inference reads local checkpoints. Audio is not sent to a model service.

Open **Open Studio 2.0.cmd** inside this new application's folder. It prepares the separate engine environment if missing and then opens the browser. Python 3.11 64-bit with the Windows `py` launcher must already be installed. An existing Studio session is reused. Keep its console open during use. The existing Start and Install launchers remain available. **Studio 2.0 Diagnostics.cmd** reads local hardware and engine status without changing recordings or printing credentials. These launchers still require physical Windows validation.

Data, shared model weights, model/package caches and processing temp files default to `D:\AI-Voice-Cloning-Studio`. The Python environment stays inside this separate project, so keep the project on D: as well to avoid placing its packages on C:. A missing D: fails clearly instead of silently filling C:. Device, gain/noise, and selected-profile preferences are saved locally.

See [all 42 review items](docs/FEATURE-CHECKLIST.md) for implemented features and remaining limits. No new download is needed to configure cloud hosting because cloud hosting is outside this local-only workflow. The optional hosting code is not invoked by local launch.

## Development / optional local Windows server

Use the existing checkout; each cloud task is already isolated and does not need a new worktree.

```bash
cd /workspace/voice-cloner/Studio-2.0
python3.11 -m venv .venv-ai
.venv-ai/bin/python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv-ai/bin/python -m pip install -r requirements-engine.txt -c requirements-engine-lock.txt
.venv-ai/bin/python -m studio.models download --root .runtime/shared-models --engine all
.venv-ai/bin/python -m studio
```

Linux data defaults to this project's `.runtime`. `STUDIO2_DATA_DIR` selects data; `STUDIO2_MODEL_DIR` can share verified base checkpoints while keeping QA data separate. Windows defaults to `D:\AI-Voice-Cloning-Studio`, and requires an explicit override when D: is unavailable. Models are shared across profiles; no duplicate per-family model downloads. The two engine variants have distinct decoder weights. Windows/GPU installation and devices still need validation there.

Full neural synthesis needs the server; opening a standalone HTML file does not run PyTorch. The `browser` directory is the earlier library-only companion, clearly labeled as such. Use the local launcher for the complete engine interface; the standalone HTML companion cannot run the engine.
