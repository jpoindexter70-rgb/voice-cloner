# VoiceCraft Studio 1.0.0 verification

Release validation was performed in the available Linux cloud workspace, using a real Chromium browser and real local Chatterbox models. Windows x64 installer/runtime checks used Wine 10 under an isolated virtual display. This is not a physical Windows PC test.

## Passed

- **37 backend regression tests**, including profile separation, consent/revocation/child locking, corruption recovery, original preservation, reference editing, persisted settings, jobs/cancellation, WAV/MP3, profile deletion, and individual/bulk/global history clearing.
- New checks cover unsaved recording previews, independent pitch/tempo, volume scaling, adjustable noise filtering, all style preset settings, generated-audio copies, cross-profile access refusal, and model-install concurrency/corrupt-model repair. A synthetic 440 Hz tone shifted down six semitones without changing duration; a noise fixture's high-frequency energy fell to about 1% while tone amplitude stayed within 1%.
- Full real browser workflow (passed against both Linux and Windows/Wine backends): synthetic microphone enable/RMS/capture/stop, recording script choices, unsaved pitch/volume/noise previews and reset, import/save with originals preserved, per-profile controls, **real Turbo inference for every requested style plus Normal**, playback progression, finished-audio preview/save, actual MP3 download, full narration using selected preview settings, bulk/current-history deletion, reload persistence, and mobile-width overflow. No JavaScript page errors.
- Real Turbo previews in the final Linux browser run took about 9–19 seconds after first loading; first preview took 31.1 seconds. Outputs were about 4–5 seconds for the test text. These are machine-specific observations, not timing guarantees.
- Built-in model setup verified/reused the actual pinned Turbo files. A real official tokenizer-asset download and repair after deliberate QA cache corruption also passed. Downloader checkpoints and manifests are pinned to tested official revisions and verified by upstream hashes; corrupt-file repair forces a fresh official download instead of trusting a stale local cache.
- Native x64 GUI launcher compiled with `-Wall -Werror`; NSIS amd64 installer compiled successfully, with a bundled, pinned-hash Python Software Foundation NuGet runtime (Python 3.11.9 x64). Rebuild helper executed from documented project directory.
- Installer silent installation, installed GUI launcher runtime smoke check, shortcut creation, and uninstall executed under Wine. Uninstall preserved separate VoiceCraft and older VoiceControlRoom QA data sentinels. The native storage folder picker selected and saved the chosen QA directory under Wine. No changes were made to the user's actual computer.
- All pinned Windows wheels installed into a separate Python 3.11.9 test runtime. `pip check` passed. Windows SoundFile, FastAPI, Uvicorn, NumPy, PyTorch/torchaudio 2.6.0+cpu, Original and Turbo adapter imports succeeded; a real tensor operation passed.
- Real Turbo and Original speech generation succeeded through Windows CPU wheels under Wine: Turbo produced a valid 3.16-second WAV in 47.2 seconds and Original a 3.76-second WAV in 28.6 seconds, including verification/model loading. The test reference was synthetic upstream test speech, not a personal family recording.

## Limits

Physical Windows installation/SmartScreen behavior, a physical microphone and speakers, NVIDIA driver compatibility, CUDA 12.4/RTX 2060 6 GB behavior, and personal speaker similarity remain unverified. The installer is unsigned because no Authenticode certificate is available. Do not disable Windows security protections.

Wine needed test-only OpenMP topology environment adjustments because its NUMA Windows API is incomplete. Those adjustments are not shipped as application requirements and do not establish a problem on actual Windows.

Styles are audible delivery presets using supported parameters and FFmpeg processing. They are not a native Turbo emotion API or a guarantee of convincing acting. Background-noise reduction cannot remove every unwanted sound without affecting speech. Script quality and model correctness do not prove an exact duplicate of a person's voice.

First installation requires internet for trusted dependencies and official checkpoints. It does not include model weights. There is no independently verified guardian process, so child profiles remain locked. No separate password/account system exists; speaker profiles provide the removable library entries.

The unavailable Family AI Voice Cloner Pro 0.3.0 installer/source was not reverse-engineered or silently altered. VoiceCraft was developed from the available Studio source in a separate folder. Existing installations/databases and personal recordings are preserved.
