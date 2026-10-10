# Python desktop application and Windows installer

The desktop app is implemented in `studio/desktop.py`. It owns a private Python/FastAPI backend thread, chooses a free loopback port, verifies server startup before opening the embedded Qt WebEngine interface, and shuts down its backend when the desktop window closes. It uses one local desktop instance per data directory and activates an existing window on repeated launch. No browser shortcut or separately started terminal/backend is required.

PyInstaller bundles CPython 3.11, PySide6, CPU PyTorch/torchaudio 2.6.0, Chatterbox 0.1.7, audio libraries and FFmpeg. Inno Setup packages the resulting directory into a genuine per-user Windows installer with desktop and Start menu shortcuts and an uninstaller. Application files are separate from `%LOCALAPPDATA%\VoiceControlRoom`, which holds family data and models. Repair, update and uninstall must retain that data directory. Models download from the application after confirmation; reference recordings are never sent to the model service.

The initial candidate bundles CPU PyTorch. It does not claim GPU acceleration or RTX 2060 compatibility. The source backend retains CUDA support for separately validated GPU packages, with Auto fallback on actual CUDA memory errors.

## Reproducible build

The `Windows desktop installer` GitHub Actions workflow runs on Windows Server 2022 with Python 3.11. It installs pinned packages, runs the complete backend suite, freezes the Python application, exercises the frozen runtime and real fixture audio exports, creates the installer, installs that exact artifact, tests the installed runtime and native embedded interface, reinstalls it, and verifies uninstall preserves user data. The downloadable candidate artifact is uploaded only after those checks pass.

The corresponding source ZIP uses `git archive HEAD`, so it matches the workflow commit. Build-generated output and private data are excluded. SHA-256 sums are generated beside the installer.

To reproduce on a Windows development machine:

```text
python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-desktop.txt -r requirements-dev.txt
python -m pip check
python -m pytest -q
python -m PyInstaller --noconfirm --clean packaging/family-voice.spec
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging/windows-installer.iss
```

These are developer build commands, not instructions for an installer user. No user needs to install Python manually for the packaged desktop application.

## Acceptance boundaries

`--self-test <report.json>` exercises real packaged imports, the packaged watermark runtime, profile/reference storage, WAV and MP3 transport. It uses a synthetic tone and does not validate neural synthesis. `--smoke-test <report.json>` opens a genuine native window and asserts that its embedded interface retrieved profile metadata from the local backend. It records a screenshot. These checks are not physical microphone/GPU tests and do not establish personal voice similarity.

A hosted Windows runner has developer tools installed. Tests of the bundled executable are useful evidence that the application carries its runtime; they do not certify a clean consumer PC. A clean-machine installation and the user's RTX 2060/microphone still need separate acceptance.

No signing credential has been established. Do not bypass SmartScreen or weaken Windows security. The candidate must be identified as unsigned unless a legitimate signature is added and verified. A passing installer pipeline alone does not establish all 46 requested features or all model/hardware acceptance checks; see `FEATURE-VERIFICATION.md`.

## Confirmed corrections

- Replaced terminal/browser startup for the new desktop path with a Python native window, local server lifecycle, visible startup diagnostics and rotating logs.
- Used spec-relative absolute paths to fix frozen builds searching inside `packaging/scripts`.
- Added explicit `backports.tarfile` for the vendored setuptools/pkg_resources dependency exposed by a frozen Linux launch.
- Added unique backup-attempt suffixes because the Windows clock returned identical timestamps for rapid retries.
- Explicitly closed temporary SQLite connections: SQLite transaction context managers alone do not close handles, which prevented Windows backup cleanup.
- Decomposed extreme pitch/speed combinations into supported FFmpeg tempo stages.
- Corrected Turbo's required tokenizer files to the official GPT-2 `vocab.json`/`merges.txt` pair; upstream does not publish the previously required `tokenizer.json`.
