# Testing report and remaining acceptance checks

This report distinguishes execution from implementation. **The requested application is not yet fully validated.** Real model inference and voice quality remain blocked by missing checkpoints and lack of a personal voice sample. Native Windows testing needs your computer.

## Executed in this cloud environment

- Python 3.11.16 and Python 3.12.14, Linux CPU, approximately 33 GiB RAM; no NVIDIA GPU.
- FastAPI/Uvicorn server successfully started on loopback. Native HTTP application health and browser functional requests succeeded.
- Recommended Python 3.11 dependency installation completed; `pip check` passed. Chatterbox Original and Turbo classes imported with CPU torch/torchaudio 2.6.0. The published package API matches the adapter calls.
- `python -m pytest -q`: **18 passed**, no skipped tests, two upstream deprecation warnings (Perth/pkg_resources and Starlette/AnyIO) on Python 3.11. Earlier 11-test baseline also passed on Python 3.12. Latest expanded suite is reported for Python 3.11 only.
- A real packaged Perth watermark model was initialized and used to watermark a synthetic tone. This exposed and fixed a setuptools incompatibility: setuptools 78.1.0 is now pinned because newer releases remove pkg_resources, causing Perth to silently disable its watermarker. No checkpoint/TTS inference is implied.
- Real FFmpeg decoding/processing and MP3 encoding were executed, exported audio was decoded/probed, and expected durations were checked. The bundled imageio-ffmpeg fallback was also exercised without relying on system FFmpeg. Backend fixtures use synthesized test tones, not speech.
- Headless system Chromium, Playwright 1.51.0: all eight navigation sections; profile creation/deletion; synthetic microphone selection, recording, pause/resume, stop, save; actual browser audio playback advancing its time; waveform/edit; WAV/MP3 downloads; useful missing-model error; Turbo controls disabling. **No JavaScript page errors.** This is a fake-device Linux browser test, not a physical microphone or Windows test.
- Tests cover same-origin/session security, blocked unapproved enrollment, guardian authorization, independent primary references, disk persistence after application recreation, original-preserving edits, quiet-span removal, bad uploads, missing models, settings validation, export labels, rating persistence, deletion, active-job protection, long-script segmentation, verified ZIP backup, backup locking, link refusal, and rejecting tampered checkpoint hashes.
- Test adapters exercise generation orchestration, reference reuse across segments, progress, cancellation, and simulated GPU-memory CPU fallback. These tests **do not execute AI synthesis** and cannot validate naturalness/identity or real CUDA behavior.
- Windows Python 3.11 x64 wheel metadata was resolved for all 107 initially pinned non-torch packages; the compatible setuptools 78.1.0 wheel was also retrieved without dependencies. CUDA 12.4 Windows wheel metadata for torch/torchaudio 2.6.0 was also found. This proves artifact availability, not Windows installation/runtime success. An initial full cross-platform pip dry run failed because pip evaluated Linux-only NVIDIA dependency markers on the Linux host; it is not a confirmed Windows dependency defect.
- Native process shutdown/restart preserved a saved profile, its primary reference, and playable audio; the named fixture was then deleted. Native duplicate-instance detection reused the running verified studio; attempting backup with an active studio lock returned the expected actionable error. Graceful API shutdown completed.

## Required 16 checks

| # | Acceptance check | Result |
|---|---|---|
| 1 | Application starts | PASS on Linux CPU, native server + browser requests. Windows pending. |
| 2 | AI engine loads | BLOCKED: imports pass, but checkpoint downloads return HTTP 403 from the cloud egress proxy. No loaded-model claim. |
| 3 | Microphone recording | PASS with Chromium synthetic device. TONOR/Windows hardware and permissions UNRUN. |
| 4 | Audio files upload | PASS: WAV and MP3 import, browser WebM recording conversion, malformed-upload rejection. |
| 5 | Voice references save | PASS: local files, quality metadata, primary reference, permission checks. |
| 6 | Profiles reload after restart | PASS: disk-backed application recreation; a full native server process shutdown/restart also preserved profile, primary reference, and audio. |
| 7 | TTS generates real audio | BLOCKED: no checkpoints; adapter/orchestration tests are not an inference substitute. |
| 8 | Resembles reference speaker | UNRUN: needs authorized actual speech samples, synthesis, and listening comparisons. |
| 9 | Audio playback | PASS in Chromium with fixture audio. Physical speaker/headphone output UNRUN. |
| 10 | WAV export | PASS: backend decoding and browser download. |
| 11 | MP3 export | PASS: actual FFmpeg encoding, duration probe, reimport, browser download. |
| 12 | Profiles remain separate | PASS: independent references; cross-profile primary reference is rejected; deletion preserves other profiles. |
| 13 | Long-text generation | PARTIAL: segmentation, per-segment same-reference conditioning and joining tested with adapters; actual long-script inference UNRUN. |
| 14 | Missing dependencies useful errors | PARTIAL: missing-model/missing Python/PyTorch messages implemented; missing-model behavior executed. Native Windows broken-environment launch UNRUN. |
| 15 | Restart without losing data | PASS for persisted API data across application recreation; a full native server process shutdown/restart. |
| 16 | Windows launcher | UNRUN on Windows. CLI startup, duplicate detection, lock enforcement, shutdown tested on Linux; batch/PowerShell scripts require Windows acceptance. |

## External blockers

The required Hugging Face model endpoints return HTTP 403 (egress restriction). No missing credential is established; do not request a token to work around network policy. Network destinations were saved in the environment draft: `huggingface.co`, `cdn-lfs.huggingface.co`, `cdn-lfs-us-1.huggingface.co`, `cas-bridge.xethub.hf.co`, `cas-server.xethub.hf.co`, `transfer.xethub.hf.co`. Review/save the settings to apply access, then retry the documented model command. Checkpoint model cards/licenses also need direct verification after access is available.

This machine cannot access `C:\VoiceCloner`, your real microphone, Windows ACL behavior, or the RTX 2060. Existing installation backup/restore, one-click Windows install/launcher, driver/CUDA compatibility, 6 GB peak VRAM, real CPU fallback, and hardware audio must be tested there. No personal voice recordings were supplied, so “best engine for your voice” and voice similarity scores cannot be claimed.

## Reproduce automated tests

```bash
cd /workspace/voice-cloner
.venv-311/bin/python -m pytest -q
```

For browser testing on Linux with system Chromium, start an isolated test server with the documented CLI and a separate `VCR_DATA_DIR`; do not run fake-device tests against personal voice data. Install Playwright 1.51.0 in the test Python environment, then run `tests/browser_smoke.py`. It creates a uniquely named test speaker, records a synthetic device, and deletes that profile on success. On failure, inspect and remove only its test profile. The script currently targets port 8765 and `/usr/bin/chromium`.

## Windows and real-voice acceptance procedure

1. Start with a verified backup of the old installation; verify that original files remain intact after installing into the new version folder. Test repair with the server closed and confirm new studio voice data remains intact.
2. Double-click the desktop shortcut and wait for engine load/browser opening. Use Engine Status to confirm selected engine/device. Launch again and ensure no duplicate server starts. Confirm Ctrl+C and the UI shutdown stop it gracefully.
3. Record from the actual TONOR microphone, pause/resume, preview, save; close/reopen the studio and play the saved reference. Import WAV/MP3 and export both formats. Test edits without replacing originals.
4. Enroll only authorized speakers, independently. For a child, verify missing guardian authorization is rejected. Verify cross-speaker references cannot be selected. Delete a temporary profile and check other voices remain.
5. Execute the multi-sentence and paragraph comparison in ENGINE-EVALUATION.md for Original and Turbo with the same real reference. Evaluate identity first, then naturalness/pronunciation/clarity/consistency, and save ratings. Record peak VRAM and generation time. Keep actual exports and metadata.
6. Run a long script and listen across boundaries for voice consistency, repetition, truncation, omissions, and unnatural pauses. Check cancellation and recovery after a failed generation.
7. Temporarily move one checkpoint aside (do not delete it), verify actionable startup diagnostics, restore it, and rerun checksum validation. Test a broken temporary environment using a disposable copy, not your only installation.
8. Test CPU explicitly and Auto on the RTX 2060. Report actual memory behavior; the test adapter’s simulated memory error is not evidence of hardware fallback.

Do not mark unrun checks passed. Any model/hardware defect found here should be diagnosed before calling the project complete.

## Installer feedback repair

After a user reported a window displaying only the installation title, numbered installer stages and streaming backup/CRC-verification progress were added. The preinstall backup preservation test was rerun and passed. The initial Python launcher check now has a 20-second timeout. These PowerShell/batch changes are not executed on native Windows here; the screenshot alone does not establish whether Python startup or the old silent backup caused the apparent stall.

## Backup source disappearance repair

A subsequent Windows screenshot showed WinError 3 while backing up a pkg_resources file in an older version's virtual environment. The root cause on that machine is not proven. The backup now records source metadata, streams and verifies archive CRCs, checks the final source inventory, and retries once after a disappeared/changed source file. Failed attempts are retained as explicitly incomplete archives and are never reported as verified full backups. Two updated installers are serialized with a Windows named mutex.

Three focused Python tests passed after this change: existing preinstall archive preservation, simulated dependency-file disappearance with the reference recording preserved, and continuous source changes causing a bounded failure without a verified-backup claim. Native Windows mutex behavior and successful retry on the user's machine remain unrun here. The earlier 18-test full-suite results above refer to the earlier run; no new full-suite count is claimed for this focused change.

## Windows access-permission repair and resume

The user's subsequent screenshot confirmed both backups were verified and stage 5 failed at Set-Acl with SeSecurityPrivilege required. The DACL implementation now retrieves only AccessControlSections.Access, replaces ordinary access rules, and writes with FileSystemInfo.SetAccessControl. It does not request audit/SACL changes or set ownership. This API change is not executed on Windows in the cloud; no native success is claimed.

Resume Installation.cmd explicitly requires previously completed backups and no later voice-data changes. It rechecks existing ZIP contents/CRCs rather than copying another full archive. Five focused tests passed: the preceding three backup tests, prior-archive revalidation without source mutation/new copying, and rejection of missing/corrupt prior archives. Incomplete archives are excluded. Resume deliberately preserves an earlier backup state and does not claim current files match it; users with later recordings/profile changes must use normal installation.
