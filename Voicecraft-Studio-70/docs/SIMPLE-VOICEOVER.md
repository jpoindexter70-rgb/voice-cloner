# Build 2.1.1 — simplified original Studio

This release simplifies the existing Codex Studio 2.1.0. It retains the FastAPI/Jobs/Chatterbox adapters, original sidebar/card/workspace layout, data format, Windows CMD/Python launchers, D: defaults and existing installed Chatterbox weights. No replacement app or framework was introduced.

The visible workflow is: Add Voice Profile → select profile → Record My Voice or Import Recording → select a clean reference → paste narration → preview or generate → play/export. Existing Original is still available, with Turbo default for new profiles. Existing profiles retain their selected engine until changed. Turbo needs a reference longer than five seconds and currently synthesizes English.

Charcoal/black/white styling keeps the same layout. Experimental live conversion, adaptation, batch/engine comparison and advanced synthesis settings are removed from the normal interface. Their legacy backend/data compatibility is retained to avoid destroying existing saved data. Decorative hero waveform bars are hidden; the recording meter/waveform use real Web Audio input samples. Local startup has no password screen; no PowerShell is required for normal installation/startup.

Pitch and speed range controls display values, save per profile and reset independently. They perform existing FFmpeg post-processing; strong adjustments can affect likeness. Reference editing has equivalent range controls/reset/preview-before-save. Microphone gain remains available; playback volume uses the browser's native audio controls.

Profiles, saved recordings/imports and generated audio can be renamed. Profile, recording and generated deletion are distinct and confirmed in the UI. History supports individual deletion, selected-file bulk deletion, all history for one voice and all voices. Deletion removes WAV/MP3 output, profile indexes and corresponding persisted completed/failed/interrupted generation jobs. Active jobs block destructive history operations. Profiles and original/reference recordings survive generation-history clearing. Exported external files/backups cannot be recalled by local history deletion.

Short Preview uses the first 24 words (at most 180 characters), generates with the selected engine/reference and current adjustments, then limits saved output to at most 10 seconds. A short sentence may produce less than five seconds. It does not pad/repeat speech, and generation speed is hardware dependent. Full Voiceover keeps the existing long-text segmentation and persistent inference worker.

The same Open/Install/Start Studio 2.0.cmd launchers are used. Required Chatterbox weights are verified/reused; disabled advanced Seed models are no longer required by the launch-readiness check or downloaded in ordinary bootstrap. Existing Seed weights and data are not deleted. Engine availability is shown in the workspace. Installation/download still occurs through the existing launcher/Python bootstrap, not a pretend browser install button. Python 3.11 64-bit must already be installed.

## Verification

32 backend tests pass, including existing regressions plus preview duration/adjustments, renaming, cross-profile protection, bulk deletion validation, WAV/MP3 removal, saved references/profiles preservation and history/recording names after app recreation. Fixture tests are explicitly orchestration checks, not AI quality proof.

A real Chromium end-to-end check passed recording/meter input from a synthetic browser microphone, capture/stop/import, pitch/speed value persistence/reset, actual Turbo short preview and full narration, playback time advancing, actual MP3 download, selected and complete history deletion and browser reload. Actual CPU Turbo preview: 4.07 seconds audio in 30.1 seconds processing including loading; full narration: 3.89 seconds audio in 9.6 seconds processing. These are small synthetic-reference checks, not promised RTX 2060 timings or personal voice similarity ratings.

Physical Windows launch/install, Intel i7-9700K/RTX 2060 VRAM and CUDA behavior, a physical microphone/TONOR input meter, hardware output devices and personal voice quality remain unverified in this Linux cloud. A browser microphone fixture exercises the actual Web Audio/RMS path but is not a physical microphone test. No unsupported hardware claim is made.

See requirements files and preserved engine evaluation for package versions: Python 3.11, torch/torchaudio 2.6.0, chatterbox-tts 0.1.7 (Original and Turbo), Windows CUDA wheel configuration cu124/12.4. The complete Linux lock is a CPU snapshot, not a Windows CUDA lock.

The additional real Chromium management workflow passed: documented adult consent, microphone track silence returning the meter to zero and restored input responding again, six-second recording capture/save, recording rename/delete, independent profile switching, profile rename/delete, reload preservation and mobile-width checks. These used browser-generated microphone data, not a physical microphone.

Reproducible browser tests are included as tests/browser_simple_voiceover.py and tests/browser_simple_management.py. They require Playwright and its Chromium separately, an isolated empty Studio data directory on port 8779 (or STUDIO2_TEST_ORIGIN), shared verified models, and STUDIO2_TEST_REFERENCE pointing to an explicitly synthetic reference longer than five seconds. Run voiceover then management against the same isolated QA server. They intentionally refuse ordinary populated profile directories. Browser input remains a synthetic microphone fixture.

Final running-build check passed: 2.1.1 identification, real installed Turbo availability, advanced controls hidden, reference pitch/speed sliders/reset and preview-before-save gating, with no JavaScript errors.
