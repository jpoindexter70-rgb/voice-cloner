# AI Voice Cloning Studio — Build 2.1.1

The original Studio has been simplified for voiceovers. Use **Open Studio 2.0.cmd**; existing launchers and locally installed Chatterbox models are preserved. Read [the simplified workflow and verification](docs/SIMPLE-VOICEOVER.md).

Record/import a voice → choose a profile → set pitch/speed → paste narration → short preview/full generation → playback/WAV/MP3 export. Rename/delete recordings and audio; clear selected, per-profile or all generation history without deleting saved voices.

The following original documentation describes retained architecture and legacy components; experimental features are no longer shown in the simplified interface.

# AI Voice Cloning Studio 2.0

Independent browser application with a new Family Voice Library and real neural voice engine integration. Existing Voice Control Room files are unchanged.

Implemented: separate family cards, names/avatars, authorization records, language/accent preferences, per-profile engine/settings, microphone capture with selection, pause/resume and live waveform/meter, import/preview/signal checks, original-preserving normalized references and edits, reference selection, serialized speech jobs, long-text segmentation, batch scripts, recorded voice conversion, progress/cancellation/recovery, generated history/playback, waveform seeking, listening ratings, WAV/MP3 export, model unloading with a saved idle policy, hardware/memory readings, disk dashboard, safe temporary cleanup and private verified backup/restore. Child voices stay locked pending verified guardian authorization. English synthesis is supported; language preferences do not imply an unsupported engine language.

Voice settings can be auditioned before saving. Compare Expressive/Turbo with one script and reference; record microphone speech directly into queued conversion. Long scripts reuse current voice conditioning; reference/profile changes reprepare it. Failed or interrupted speech has a Retry Script control.

Real Expressive/Turbo inference, conversion, settings auditions, comparison, cached multi-segment generation and browser export checks passed. See [validation](docs/VALIDATION.md) for exact scope. Naturalness and personal similarity are not yet assessed with family speech. Seed recorded conversion and experimental per-profile adaptation have passed real CPU inference checks. Live conversion is implemented with a fresh CUDA benchmark gate; actual Windows/GPU streaming and verified child-account access still require validation.

Seed candidates save only the final flow-matching head (about 715 KB), not duplicate base models. Audition and rate a candidate before activating it. Live conversion measures three warmed-up inference blocks and requires CUDA with 20% processing headroom; it stops when input or output falls behind. Measurements exclude physical microphone and output-device latency. Speech synthesis remains Expressive/Turbo; Seed is a conversion engine.

Studio 2.0 now includes GPL-3.0 Seed architecture code and is distributed under [GPL-3.0](LICENSE). Model weights and other dependencies retain their respective upstream licenses.

## Use on your Windows computer

The intended setup is local: the browser opens the Studio running on your own computer. No Hugging Face account, hosting token or hosted password is needed. On first use, public model/package downloads need internet; verified installed models are reused on repair and inference reads local checkpoints. Audio is not sent to a model service.

Open **Open Studio 2.0.cmd** inside this new application's folder. It prepares the separate engine environment if missing or incomplete and then opens the browser. Python 3.11 64-bit with the Windows `py` launcher must already be installed. An existing Studio session is reused. Keep its console open during use. The existing Start and Install launchers remain available. **Studio 2.0 Diagnostics.cmd** reads local hardware and engine status without changing recordings or printing credentials. These launchers still require physical Windows validation.

Data, shared model weights, model/package caches and processing temp files default to `D:\AI-Voice-Cloning-Studio`. The Python environment stays inside this separate project, so keep the project on D: as well to avoid placing its packages on C:. A missing D: fails clearly instead of silently filling C:. Device, gain/noise, and selected-profile preferences are saved locally.

See [all 46 review items](docs/FEATURE-CHECKLIST.md) for implemented features and remaining limits. No new download is needed to configure cloud hosting because cloud hosting is outside this local-only workflow. The optional hosting code is not invoked by local launch.

## Development / optional local Windows server

Use the existing checkout; each cloud task is already isolated and does not need a new worktree.

```bash
cd /workspace/voice-cloner/Studio-2.0
python3.11 -m venv .venv-ai
.venv-ai/bin/python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv-ai/bin/python -m pip install -r requirements-engine.txt -c requirements-engine-lock.txt
.venv-ai/bin/python -m studio.models download --root .runtime/shared-models --engine all
.venv-ai/bin/python -m studio.seed_assets download --root .runtime/shared-models
.venv-ai/bin/python -m studio
```

Linux data defaults to this project's `.runtime`. `STUDIO2_DATA_DIR` selects data; `STUDIO2_MODEL_DIR` can share verified base checkpoints while keeping QA data separate. Windows defaults to `D:\AI-Voice-Cloning-Studio`, and requires an explicit override when D: is unavailable. Models are shared across profiles; no duplicate per-family model downloads. The two engine variants have distinct decoder weights. Windows/GPU installation and devices still need validation there.

Full neural synthesis needs the server; opening a standalone HTML file does not run PyTorch. The `browser` directory is the earlier library-only companion, clearly labeled as such. Use the local launcher for the complete engine interface; the standalone HTML companion cannot run the engine.
