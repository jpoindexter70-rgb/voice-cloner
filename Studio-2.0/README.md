# AI Voice Cloning Studio 2.0

New standalone application, written independently of the existing voice-cloner app. Family Voice Library is part of the main studio, with a compact sidebar and a card dashboard.

## Run

Linux/cloud:

```bash
cd /workspace/voice-cloner/Studio-2.0
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m studio
```

On Windows, extract into a separate directory such as `D:\AI-Voice-Cloning-Studio-App`, install Python 3.11, run `Install Studio 2.0.cmd`, then `Start Studio 2.0.cmd`. Open your browser at loopback port 8770. The batch scripts have not been tested on Windows.

Default Windows data is `D:\AI-Voice-Cloning-Studio`. If D: is unavailable, the app requires an explicit `STUDIO2_DATA_DIR` override; it does not silently move large data onto C:. Linux cloud defaults to this project's `.runtime` folder. Use `STUDIO2_DATA_DIR` to choose another private directory.

## Implemented

- Add, edit, select and delete multiple independent family profiles; optional PNG avatar.
- Documented adult permission, local authorization record and creation date. Revocation blocks reference playback, recording enrollment and generation requests.
- Child profiles are created in a locked state. No guardian verification implementation exists yet; no child playback, recording enrollment or generation is permitted.
- Microphone selection, live volume meter, record/stop, preview and WAV capture; browser permission required.
- WAV/FLAC import, preview and signal evaluation before saving. RMS, clipping and duration are signal checks, not an AI voice-quality score.
- Multiple recording sessions per profile; choose a primary voice reference. Adding recordings does not claim adaptation or retraining.
- Separate reference, sample, voice-model, generated-audio and settings folders per UUID; shared-models directory outside profile folders.
- Preferred language, accent and speed stored separately. These are preferences, not promises of engine capabilities.
- Persistent profiles and reference settings; local storage dashboard.
- Loopback binding, Host/Origin restrictions, session cookies and mutation tokens. No public sharing route.

## Still unimplemented

AI engine integration, real cloned speech generation, generated history playback/export, MP3 import/export, voice-to-voice conversion, real-time conversion, engine adaptation/retraining, independently verified guardian identity and managed restricted accounts. Generation is visibly disabled and the API returns an explicit unavailable error; no fabricated output is created. Naturalness and speaker similarity cannot yet be assessed.

The samples/generated-audio/voice-model folders reserve storage for future engine integration; currently sample playback uses the selected original reference. The UI labels it as a voice sample and does not call it generated speech.

Local documented adult permission is not identity verification. Anyone with access to the studio's local browser session can manage adult profiles. Use a private OS account and disk encryption. Profile deletion removes active local data, not exported files or external backups; it is not forensic erasure.

## Validation

`.venv/bin/python -m pytest -q`: four integration tests passed, exercising profile isolation, persisted settings/reference selection, actual WAV decoding, revocation, child locks, deletion isolation, input rejection, session/origin restrictions and truthful missing-engine errors. Linux synthetic browser recording is separate from physical microphone/Windows testing.

Existing applications and the existing voice-cloner source were left unchanged. This new app is published in the Studio-2.0 folder on its own Git branch. The original application is unchanged.

Browser validation also passed: profile creation, synthetic microphone recording, signal evaluation/save, actual sample playback, voice selection, consent revocation and deletion, with no JavaScript errors. Run `tests/browser_smoke.py` with Playwright and system Chromium against a clean test instance on port 8770; do not use personal data. Physical devices remain untested.
