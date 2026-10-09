# Voice Control Room Advanced

A private local voice studio with a FastAPI server, browser microphone recorder, persistent independent speaker profiles, a text-to-speech job system, Chatterbox Original/Turbo adapters, non-destructive audio processing, and Windows installation/startup/backup tools.

**Status:** Application storage, recording flow with a synthetic browser microphone, audio editing/conversion, and API behavior are testable in the cloud. Actual voice synthesis requires the official model checkpoints. Windows launcher, TONOR microphone, RTX 2060 fit, and personal voice quality are not validated until tested on your computer. Read [the test report](docs/TESTING.md) for exact outcomes. This is not yet certified complete under your requested 16 acceptance checks.

## Windows: preserve first, then install

1. Close your old local voice application. Do not delete `C:\VoiceCloner`.
2. Install **64-bit Python 3.11** from [python.org](https://www.python.org/downloads/windows/), including the Python launcher (`py`). Update your NVIDIA driver to one compatible with CUDA 12.4. The installer uses prebuilt torch/torchaudio 2.6.0 CUDA 12.4 wheels; no paid service is required.
3. Extract this application into a **separate folder**, for example `C:\VoiceControlRoom-Advanced`. Avoid extracting over an old installation before it has been backed up.
4. Double-click **Install or Repair.cmd** in the extracted folder. It checks that port 8765 is free, inventories and archives **all files** in the existing `C:\VoiceCloner` and new studio data directory, validates the archives, and stops if backup fails. It refuses symlinks/junctions rather than silently omitting external data. Full backups may need substantial free disk space, especially with old virtual environments/model caches.
5. After successful backup, it deploys the new application into a fresh version folder under `C:\VoiceCloner`, creates a fresh side-by-side Python environment, installs packages, secures the data/backup folders with Windows user ACLs, and downloads/verifies both models. Downloading several GB requires internet. Old source files, virtual environments, and data are not overwritten or deleted. Every installation uses a fresh version folder; remove obsolete versions manually only after verifying your backups. A `python-path.txt` file selects the new environment only after package checks pass.
6. Double-click the new **Voice Control Room Advanced** desktop shortcut, or open the new `C:\VoiceCloner\VoiceControlRoomAdvanced-<date>` folder and double-click **Start Voice Control Room.cmd**. It verifies the selected model checksums, loads the local engine, starts only on `127.0.0.1:8765`, and opens your browser after the server starts. GPU memory failure in Auto mode falls back to CPU. Loading can take time. Keep the console open; use the studio’s shutdown button or Ctrl+C to stop.
7. In **My Voice**, record or upload a clean 10–15 second reference. In **Generate Speech**, select My Voice, write a short sentence, generate, then compare to your reference before trusting the output. Saved references are automatically reused on later launches.

The new data directory is `%LOCALAPPDATA%\VoiceControlRoom`, intentionally separate from the unknown legacy installation. **Legacy voice profile formats are not automatically migrated.** After backup, locate your old WAV/MP3/FLAC/M4A recordings and explicitly import each into its correct profile. Do not import model pickle files or combine different speakers. The app never imports arbitrary local paths from browser requests.

## Everyday tools

- **Start Voice Control Room.cmd**: model verification, engine load, server startup, browser opening, duplicate-instance prevention.
- **Diagnostics.cmd**: packages, model files, data path, available GPU/VRAM, and FFmpeg.
- **Download Models.cmd**: explicit online checkpoint download/repair. Close the studio first. Model files record exact upstream revisions and SHA-256 manifests; large LFS files are checked against upstream hashes.
- **Install or Repair.cmd**: backup-first package/environment repair. Run from the extracted source folder or installed version folder after closing the server. Repair creates another version folder and a new desktop shortcut. Never deletes profiles or recordings.
- **Backup Data.cmd**: verified archive of new studio data. Close the studio first; an active server lock blocks backup. Backup archives contain private recordings; keep them protected.

Initial model downloads are the only intended remote model operation. Inference uses `from_local` and offline Hugging Face/Transformers mode. There is no cloud audio service or subscription. Microphone audio is sent only to your loopback server when you choose Save reference.

## Studio features

- Dashboard with real profile/recording counts and engine health.
- My Voice is always the default identity, with persistent references; family profiles are independently authorized and stored. Children require parent/guardian authorization.
- Microphone selection, live meter/waveform, timer, pause/resume/stop, browser preview, saved local reference. Chrome or Edge is recommended on Windows.
- Reference upload accepts common audio formats via FFmpeg, converts to mono 24 kHz WAV, and checks duration, loudness, and clipping. These heuristics do not measure voice similarity or signal-to-noise ratio.
- Text synthesis is serialized so only one model/generation uses memory at a time. Scripts up to 20,000 characters split into at most 240-character sentence/word segments with the same reference per segment. Progress and cancellation are real; cancellation waits for the current segment.
- Original Chatterbox expression exaggeration/CFG and sampling temperature are real engine parameters. Turbo disables unsupported controls. Segment pauses are actual inserted silence. No unsupported naturalness/identity sliders.
- A/B original/generated players, stop/replay/regeneration, saved clips, WAV/MP3 downloads, and user-rated quality comparisons with JSON export.
- Audio Editor trims, removes quiet spans, applies conservative spectral noise reduction, adjusts speed/pitch with FFmpeg, and saves an edited copy. Set the copy as primary explicitly if desired. Strong processing may reduce identity fidelity.
- Rename/add/delete speaker profiles and reference recordings. My Voice deletion clears its data while retaining an empty default profile.

There is no public sharing route. Generated clips are labeled in the UI and download filenames; Chatterbox’s upstream watermarker is retained. Exported audio may be renamed or copied by users; no access policy can control those copies.

## Privacy limits

Bind only to loopback using the supplied launcher. The server checks Host/Origin and uses same-origin session/CSRF tokens, no permissive CORS, and restrictive browser headers. The Windows installer applies user-only data access plus SYSTEM/Administrators. Other software running as your Windows user and administrators can still access files; this is not disk encryption. Use Windows device encryption/BitLocker and separate accounts as needed.

Deletion removes active profile audio and evaluations, and unloads model conditioning. Exported files, old installation files, and backups remain until you remove them separately. Filesystem unlink is not a guaranteed forensic wipe, especially on SSDs.

## Cloud / Linux development

The cloud checkout is already isolated; use it directly, without creating a worktree.

```bash
cd /workspace/voice-cloner
python -m venv .venv
.venv/bin/python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements-engine.txt -r requirements-dev.txt
export VCR_DATA_DIR=/workspace/voice-cloner/.runtime/studio-data
.venv/bin/python -m studio.cli download-models --engine all
.venv/bin/python -m studio.cli verify-models --engine all
.venv/bin/python -m studio.cli serve --no-browser --load-engine
```

The server can run without `--load-engine` to develop/import/edit audio before models are available. It will report missing models rather than simulate synthesis. Linux defaults to `~/.local/share/voice-control-room`; use `VCR_DATA_DIR` in this sandbox. CPU inference is slower. Python 3.11 is recommended; Linux Python 3.12 dependency/import checks were also run.

Run `.venv/bin/python -m pytest -q` for backend tests. The synthetic Chromium test is in `tests/browser_smoke.py`; see [TESTING](docs/TESTING.md) for setup. Test-generated tones and fake microphone audio are not evidence of cloned-voice quality.

See [engine evaluation](docs/ENGINE-EVALUATION.md), [recovery](docs/RECOVERY.md), and [acceptance testing](docs/TESTING.md). No changes have been pushed to GitHub automatically.

## If the installer appears inactive

The installer now prints numbered stages before Python checking, backup, folder setup, permissions, environment creation, package installation, and model downloads. Backup and archive verification display progress even while processing a large individual model file. The initial Python check fails with an actionable error after 20 seconds rather than waiting indefinitely. If you have an earlier ZIP showing only the installation title, download the latest ZIP into a separate folder; do not run two installers concurrently. Stop the previous installer with Ctrl+C before restarting. Interrupting backup does not delete source files; an incomplete ZIP must not be treated as a verified backup.

Report the last numbered stage and any error text. A stage label indicates what is running, not that it has passed. Windows behavior of these updated launcher/PowerShell steps still needs validation on your computer.

### Backup stops with “The system cannot find the path specified”

A file may have disappeared or changed between the scan and copying. The screenshot alone does not establish the cause; this can happen if another installer is changing an older environment. The updated backup refreshes its inventory and retries once, checks source stability before declaring success, and preserves failed archives as `.incomplete.zip` for possible individual-file recovery. Incomplete archives are not verified full backups. A second failure stops installation with a clear message; files are never silently skipped on a successful attempt. Incomplete attempts may consume additional disk space and are not automatically deleted.

Updated installers also acquire a Windows mutex to prevent two updated installations from running together. Older installers cannot participate in that lock. Save your work, restart Windows to stop any previous installer processes, download the latest source ZIP into a separate folder, and run exactly one Install or Repair.cmd. Keep the existing C:\VoiceCloner and voice-data folders intact. Do not restore an incomplete archive as if it were a full verified backup.
