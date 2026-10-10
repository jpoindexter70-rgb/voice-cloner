# Family AI Voice Cloner Pro

A local Python desktop voice studio built from the existing Voice Control Room project. The new desktop launcher embeds the interface in a native Qt window and manages its own loopback Python backend. Windows packaging bundles Python and dependencies; users do not need to install Python or start a separate server.

**Windows 0.3.0 CPU desktop release:** [Download the verified installer and matching source ZIP](https://github.com/jpoindexter70-rgb/voice-cloner/releases/tag/desktop-preview-45fa4ac27a67). The exact artifact passed installed runtime/native-window checks, genuine Original/Turbo neural generation, real two-speaker story/preview/sentence replacement, repair/reinstallation and uninstall preservation, plus automatic installation verification and a separate system-only PATH/native-screen check. It is unsigned and does not certify the complete 46-feature specification or physical consumer hardware. See [verification](docs/FEATURE-VERIFICATION.md).

## Everyday workflow

1. Launch the installed desktop application from its shortcut.
2. Open Family Voice Library, create an authorized family profile, then record or upload a clean reference of at least six seconds. Child profiles require guardian authorization.
3. In Local AI Engine Manager, download the official model after confirming the storage/network requirement, select it in Settings and load it. Downloads are explicit; inference uses local checkpoints offline.
4. Select the family voice and reference in Text-to-Speech Studio, enter text, preview a sentence or queue the full recording. Saved per-person voice controls and pronunciation replacements are applied.
5. Listen to the actual generated recording in Generation Queue or Recording Library, then export WAV or MP3.
6. Use Story Creator for chapter text, narrator and character voices. Generated sentences are added to the project's timeline. Edit start/trim/gain/track roles, add music and effects, enable ducking and export audio/SRT/VTT.
7. Use Projects and History to recover versions. Interrupted queue jobs can resume from saved segment audio. Backup and restore are available in Settings.

Private data remains under `%LOCALAPPDATA%\VoiceControlRoom` on Windows, separate from application files. Repair/update/uninstall preserve that directory. Backups contain private recordings; keep them protected. Never enroll an unauthorized speaker or upload recordings to external services without explicit permission.

## Current capabilities and limits

Independent family profiles and references; native-window recording with microphone selection, meter, optional countdown, pause/resume and review; WAV/MP3 import/export; non-destructive trim, pitch, speed, gain, normalization and conservative denoising; saved presets and pronunciation; sentence/chapter story jobs; persistent queue/checkpoints; versioned projects; editable audio timeline, music ducking and sentence-boundary captions; real engine status and diagnostics.

The initial Windows candidate uses CPU PyTorch. RTX 2060 acceleration, physical microphones, personal resemblance and clean consumer-PC installation require separate evidence. Original exposes exaggeration/CFG; Turbo disables those controls and accepts upstream paralinguistic text tags. Dedicated emotion categories, accent transfer, speaker-similarity knobs and a distinct high-quality model mode are not implemented as pretend sliders. Phrase emphasis uses separately synthesized phrase audio and increased gain; boundaries may be audible.

Model files are not bundled in the installer: download them through the application once, then use inference offline. This candidate is unsigned unless legitimate signing is added and verified. Do not bypass Windows security.

## Development

Use the existing isolated checkout directly; no worktree is necessary. On Linux, `bash scripts/cloud-install.sh` prepares the pinned Python 3.11 CPU environment and models. Set `VCR_DATA_DIR` to a writable development directory, then run `.venv-311/bin/python -m studio.cli serve --no-browser` for browser development or `.venv-311/bin/python -m studio.desktop` for the native window (install `requirements-desktop.txt` first). Run `.venv-311/bin/python -m pytest -q`. Browser fixtures are in `tests/browser_smoke.py` and `tests/browser_workflows.py`. Fixtures and adapters are not neural inference or physical hardware evidence.

See [Windows packaging](docs/DESKTOP-BUILD.md), [engine evaluation](docs/ENGINE-EVALUATION.md), [historical tests](docs/TESTING.md), [recovery](docs/RECOVERY.md), and [third-party notices](docs/THIRD-PARTY-NOTICES.md). The earlier terminal/browser installation instructions are retained in [legacy documentation](docs/LEGACY-STUDIO.md) for existing installations; they are not the new desktop installation flow.
