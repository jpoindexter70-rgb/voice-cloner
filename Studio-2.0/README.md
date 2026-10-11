# AI Voice Cloning Studio 2.0

Independent browser application with a new Family Voice Library and real neural voice engine integration. Existing Voice Control Room files are unchanged.

Implemented: separate family cards, names/avatars, authorization records, language/accent preferences, per-profile engine/settings, microphone capture with selection, pause/resume and live waveform/meter, import/preview/signal checks, original-preserving normalized references and edits, reference selection, serialized speech jobs, long-text segmentation, batch scripts, recorded voice conversion, progress/cancellation/recovery, generated history/playback, waveform seeking, listening ratings, WAV/MP3 export, model unloading, disk dashboard, safe temporary cleanup and private verified backup/restore. Child voices stay locked pending verified guardian authorization. English synthesis is supported; language preferences do not imply an unsupported engine language.

Real Expressive/Turbo inference, conversion and browser export checks passed. See [validation](docs/VALIDATION.md) for exact scope. Naturalness and personal similarity are not yet assessed with family speech. Live conversion and verified child-account access remain unavailable.

## Browser hosting, with no repeated user installation

The hosted app needs an actual hosting account, not a download link. The prepared deployment uses a private Hugging Face Docker Space on free CPU hardware and a private dataset for profile persistence. No paid hardware/storage upgrade is requested. Actual account quotas apply. Securely supply `HF_DEPLOY_TOKEN` with permission to create/write your private Space and dataset, and `STUDIO2_HOST_PASSWORD` of at least 16 characters. Do not paste them into chat or commit them. Environment requirements are saved in the cloud configuration draft.

Run `.venv-ai/bin/python scripts/deploy_space.py` after credentials are injected. It creates only its new private repositories, stores the password in hosted secret settings, and uploads only the new app source. Partial deployment state contains repository identities only; retry resumes resources this script created. Existing unrecognized repositories are not overwritten. Verify actual Space build/startup, password rejection, functional requests and a generated clip before calling deployment ready.

Hosted audio/settings live on the private server and, when configured, the owner's private dataset. They are not automatically stored on the user's D: drive. Historical private dataset revisions are backups that require separate removal for complete deletion. Real dataset synchronization is unverified until connected. HTTPS and password authentication are mandatory for hosted mode; it has no public sharing route. Optional shared-household passwords are not per-child restricted accounts.

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

Full neural synthesis needs the server; opening a standalone HTML file does not run PyTorch. The `browser` directory is the earlier library-only companion, clearly labeled as such. The user does not need further partial downloads to obtain a hosted app; deployment account access is the remaining prerequisite for an address.
