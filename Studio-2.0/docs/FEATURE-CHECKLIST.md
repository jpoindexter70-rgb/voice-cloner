# Studio 2.0 requirement audit — local computer edition

This checklist groups the uploaded specification and Family Voice Library request into 42 review items. The number is a review grouping, not a claim that a separately supplied list of 42 items was received. All code is in this independent app; the existing applications are unchanged. The browser is the interface to the local Python inference server. No hosting account or deployment token is required for local use.

“Implemented” means source exists and the relevant Linux/backend/browser workflow was checked; physical Windows, microphone/output hardware and RTX 2060 checks remain distinct. Synthetic references establish inference, not personal speaker similarity.

| # | Requirement | Status / evidence or limit |
|---|---|---|
| 1 | Independent new application and configuration | Implemented in Studio-2.0; separate .venv-ai and data root |
| 2 | Modern dark dashboard and compact sidebar | Implemented; browser checked |
| 3 | Responsive family cards and Add Family Member | Implemented; browser checked |
| 4 | Multiple profiles without replacement | Implemented; isolation tests |
| 5 | Names and optional avatars | Implemented; image validation |
| 6 | Preferred language and accent | Saved independently; installed engines synthesize English, not every stored language |
| 7 | Creation date, consent records and history | Implemented; records view and adult reauthorization |
| 8 | Adult documented consent and revocation | Implemented; revoked audio/generation blocked |
| 9 | Verified guardian authorization and restricted child access | NOT implemented; child enrollment records are locked, no child audio access |
| 10 | Delete profile and associated local data | Implemented; shared engines and other profiles preserved |
| 11 | Profile selection cards and authorized dropdown | Implemented; selection saved across reload/restart |
| 12 | Per-profile settings and references | Implemented; job snapshots avoid identity/settings changes during processing |
| 13 | Multiple recording sessions and retained originals | Implemented; original download is byte-preserving |
| 14 | Additional voice adaptation/retraining | Installed engines use zero-shot references; retraining is NOT supported |
| 15 | Microphone selection | Implemented; synthetic device browser check; physical device unverified |
| 16 | Record, pause, resume, stop and preview | Implemented; browser checked |
| 17 | Microphone gain, waveform and responsive input meter | Implemented; software gain/clipping; browser checked |
| 18 | Microphone noise suppression and echo control | Implemented using browser-supported constraints; settings saved |
| 19 | Import WAV, FLAC, MP3, M4A and browser recordings | Implemented with real decoding; bounded size/duration |
| 20 | Reference signal evaluation before saving | Implemented; RMS, clipping, duration; no fabricated similarity score |
| 21 | Trim, denoise, speed and pitch reference preparation | Implemented; preview and evaluation gate before saving a separate copy |
| 22 | Real AI voice cloning | Actual verified Expressive/Turbo reference-conditioned inference checked |
| 23 | Natural text-to-speech | Actual audio generated; naturalness/accent/identity still requires authorized human listening |
| 24 | Emotion, conditioning, temperature, pauses | Supported controls wired; Expressive-only controls disabled for Turbo |
| 25 | Generated pitch and speed controls | Implemented; 48 kHz trim/pitch/speed regression fixed and checked |
| 26 | Long text segmentation | Implemented; real two-segment inference checked |
| 27 | Batch generation | Implemented; actual browser two-script batch checked |
| 28 | Recorded voice-to-voice conversion | Real engine conversion checked; input limited to 30 seconds |
| 29 | Job progress, status and cancellation | Implemented; current model step completes before cancellation |
| 30 | Recovery, interrupted jobs and useful errors | Implemented; restart and failed-job resubmission checks |
| 31 | Playback, waveform seeking and output meter | Implemented; signal meter estimates decoded playback, not hardware output |
| 32 | WAV/MP3 export | Actual encoded files decoded and browser downloads checked |
| 33 | Saved generated history, deletion and listening ratings | Implemented; profile-scoped deletion preserves source references |
| 34 | Audio output device selection | Implemented when browser supports setSinkId; saved selection; physical routing unverified |
| 35 | Maintained engine evaluation and modular switching | Expressive/Turbo adapters; other engine comparison documented |
| 36 | GPU acceleration, CPU fallback and model unloading | Implemented; CPU/unload checked; physical CUDA/OOM behavior unverified |
| 37 | Hardware, RAM and GPU-memory dashboard | Real local measurements; unavailable values shown explicitly; hardware refresh |
| 38 | Recorded-job processing time and audio-duration ratio | Measured and saved on new clips; not claimed as microphone streaming latency |
| 39 | Real-time microphone conversion | NOT implemented; actual cloud CPU conversion slower than real time; user's GPU unmeasured |
| 40 | OBS / virtual audio routing | Recorded playback can select an already installed virtual output when browser permits; no virtual driver installation or live conversion |
| 41 | D: models, recordings, caches/temp; storage dashboard and safe cleanup | Windows D: default; runtime temp/cache directed there; category dashboard; existing weights reused; missing D: requires explicit override |
| 42 | Reliable local launch, backup/restore and complete validation | Single launcher plus read-only diagnostics, verified ZIP backup/restore; backend/browser checked; actual Windows launch and RTX 2060 memory fit remain unverified |

No controls pretend to implement child identity verification, unsupported languages, retraining or live conversion. The original specification explicitly makes real-time support contingent on feasibility. These limits cannot be resolved by relabeling recorded conversion as live conversion.
