# Recovery without losing voice data

## What this cloud task can inspect

The selected GitHub checkout was empty (no files/commits or `main` ref), so no legacy application files or personal voice data were available to inspect. `C:\VoiceCloner` is on your Windows computer and is not mounted here. Its engine and profile format are unknown. Do not infer that Windows data is missing from the empty GitHub repository.

## Before installation or repair on Windows

Close the old application and new studio. Extract the new source into a separate folder first. The installer refuses a live server on port 8765, then uses a standard-library backup utility before installing packages. Every existing file in the old installation and new data directory is inventoried and archived; CRC validation and file counts are checked. Links/junctions or inaccessible files stop backup rather than disappearing from the inventory. The ephemeral server lock is excluded from backups.

Archives go to `%LOCALAPPDATA%\VoiceControlRoom-Backups`. They may contain recordings, configuration, and sensitive old files; protect them. The installer secures backup/data folders with Windows ACLs. Keep enough disk space for full existing environments and model caches. Backups are never purged automatically.

A new version folder under `C:\VoiceCloner` is created on each install/repair. Unknown legacy source, recordings, profiles, and environments are not overwritten. A uniquely named desktop shortcut points at the new version. The new voice data stays in `%LOCALAPPDATA%\VoiceControlRoom` across version upgrades.

## Restore existing voices

Inspect the verified archive or old installation for familiar recordings (`.wav`, `.mp3`, `.flac`, `.m4a`, `.ogg`). Listen locally, identify each speaker, and import their audio into a separate authorized profile. Choose one clean primary reference per person. My Voice is the default. Child profiles require an authorizing parent/guardian.

Do not automatically merge unknown JSON/profile databases or execute old `.pt`/pickle objects. The original engine is unknown, so compatibility cannot be assumed. The installer preserves those files for later inspection. No old profile migration has been executed or tested in this cloud environment.

## Common failures

| Symptom | Action |
|---|---|
| Python missing | Install Python 3.11 x64 with the `py` launcher, then run Install or Repair.cmd. |
| Python environment missing or packages fail import | Close the app and run Install or Repair.cmd. A fresh environment is created; voice data remains separate. |
| Missing model files or integrity error | Close the app and run Download Models.cmd while online; do not skip checksums or TLS verification. |
| CUDA unavailable | Run Diagnostics.cmd, check NVIDIA drivers, or select CPU/Auto in Settings. Prebuilt CUDA 12.4 torch wheels need a compatible driver. |
| GPU out of memory | Close GPU-heavy apps; use Auto for CPU fallback or CPU explicitly. One model is retained at a time. |
| Very slow CPU inference | Expected on large models. Begin with a short sentence; do not reduce identity quality by switching engines without listening comparisons. |
| Port 8765 conflict | Close the conflicting application. Launcher never kills other processes. An existing verified studio opens without starting a duplicate. |
| Browser microphone denied | Open loopback address with Chrome/Edge, allow microphone in site permissions, check Windows microphone privacy settings and input device selection. |
| Audio import rejected | Use a supported audio format, between 0.25 seconds and 10 minutes and under 100 MB. Clone references must be at least 6 seconds. Check FFmpeg diagnostics. |
| Poor resemblance | Compare a clean, naturally delivered reference and both engines. Try another saved reference before denoising or exaggerating expression. There is no guaranteed perfect match. |
| Profile database lost | Stop the app and restore the whole data folder from a verified backup. Unindexed WAV files are never deleted automatically; diagnostics counts them. Identify each speaker and reimport audio manually if the database cannot be recovered. |
| Database corruption | Stop the app, preserve the damaged directory, and restore a verified archive into a new directory; never delete recordings as a “repair.” Set `VCR_DATA_DIR` to the recovered directory for diagnosis. |
| Backup stops at a link/junction | Preserve that target separately. Do not remove the link or change backup code to omit it until the data is safely recovered. |

## Back up and restore the new studio

Close the studio and run Backup Data.cmd. Active-server file locking prevents a concurrent backup. For restore, close the app, copy the current directory aside without deleting it, inspect the ZIP, and restore the whole archive to a new directory. Database and `audio` must come from the same backup. The `models` subdirectory can be redownloaded. Launch using `VCR_DATA_DIR` pointed at the recovered directory, or restore verified data to the default path only after preserving the current folder.

Profile deletion removes live recordings/evaluations and clears engine conditioning. Exports, legacy data, backup copies, and SSD remnants are outside that deletion. Remove unwanted backup/export copies separately. No guaranteed forensic erasure is claimed.
