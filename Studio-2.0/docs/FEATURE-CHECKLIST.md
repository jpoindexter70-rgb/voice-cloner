# Studio 2.0 requirement audit — local computer edition

This checklist groups the uploaded specification and Family Voice Library request into 46 review items. The number is a review grouping, not a claim that a separately supplied numbered list of 46 items was received. All code is in this independent app; the existing applications are unchanged. The browser is the interface to the local Python inference server. No hosting account or deployment token is required for local use.

“Implemented” means source exists and the relevant Linux/backend/browser workflow was checked; physical Windows, microphone/output hardware and RTX 2060 checks remain distinct. Synthetic references establish inference, not personal speaker similarity.

| # | Requirement | Status / evidence or limit |
|---|---|---|
| 1 | Independent new application and configuration | Implemented in Studio-2.0; separate .venv-ai and data root |
| 2 | Modern dark dashboard and compact sidebar | Implemented; browser checked |
| 3 | Responsive family cards and Add Family Member | Implemented; browser checked |
| 4 | Multiple profiles without replacement | Implemented; isolation tests |
| 5 | Names and optional avatars | Implemented; PNG/JPEG/WebP validation, orientation correction, metadata-free normalized avatars |
| 6 | Preferred language and accent | Saved independently; installed engines synthesize English, not every stored language |
| 7 | Creation date, consent records and history | Implemented; records view plus creation/revocation/reauthorization history |
| 8 | Adult documented consent and revocation | Implemented; revoked audio/generation blocked |
| 9 | Verified guardian authorization and restricted child access | NOT implemented; child enrollment records are locked, no child audio access |
| 10 | Delete profile and associated local data | Implemented; shared engines and other profiles preserved |
| 11 | Profile selection cards and authorized dropdown | Implemented; selection saved across reload/restart |
| 12 | Per-profile settings and references | Implemented; job snapshots avoid identity/settings changes during processing |
| 13 | Multiple recording sessions and retained originals | Implemented; original download is byte-preserving |
| 14 | Additional voice adaptation/retraining | Experimental Seed final-head adaptation implemented and real CPU training/inference checked; candidate audition/rating required, no quality guarantee |
| 15 | Microphone selection | Implemented; synthetic device browser check; physical device unverified |
| 16 | Record, pause, resume, stop and preview | Implemented; browser checked, direct recorded microphone conversion |
| 17 | Microphone gain, waveform and responsive input meter | Implemented; software gain/clipping; browser checked |
| 18 | Microphone noise suppression and echo control | Implemented using browser-supported constraints; settings saved |
| 19 | Import WAV, FLAC, MP3, M4A and browser recordings | Implemented with real decoding; bounded size/duration |
| 20 | Reference signal evaluation before saving | Implemented; RMS, clipping, duration; no fabricated similarity score |
| 21 | Trim, denoise, speed and pitch reference preparation | Implemented; preview and evaluation gate before saving a separate copy |
| 22 | Real AI voice cloning | Actual verified Expressive/Turbo reference-conditioned inference checked |
| 23 | Natural text-to-speech | Actual audio generated; naturalness/accent/identity still requires authorized human listening |
| 24 | Emotion, conditioning, temperature, pauses | Supported controls wired; unsaved-settings auditions; Expressive-only controls disabled for Turbo |
| 25 | Generated pitch and speed controls | Implemented; 48 kHz trim/pitch/speed regression fixed and checked |
| 26 | Long text segmentation | Implemented; real multi-segment inference and later jobs reuse current conditioning |
| 27 | Batch generation | Implemented; actual browser two-script batch checked |
| 28 | Recorded voice-to-voice conversion | Real engine conversion checked; input limited to 30 seconds |
| 29 | Job progress, status and cancellation | Implemented; current model step completes before cancellation |
| 30 | Recovery, interrupted jobs and useful errors | Implemented; Retry Script, interrupted jobs, damaged-history preservation/recovery warnings |
| 31 | Playback, waveform seeking and output meter | Implemented; signal meter estimates decoded playback, not hardware output |
| 32 | WAV/MP3 export | Actual encoded files decoded and browser downloads checked |
| 33 | Saved generated history, deletion and listening ratings | Implemented; profile-scoped deletion preserves source references |
| 34 | Audio output device selection | Implemented when browser supports setSinkId; saved selection; physical routing unverified |
| 35 | Maintained engine evaluation and modular switching | Expressive/Turbo adapters and actual side-by-side auditions; other engine comparison documented |
| 36 | GPU acceleration, CPU fallback and model unloading | Implemented; configurable idle unload, sticky Auto CPU fallback unit-checked; actual CUDA/OOM behavior unverified |
| 37 | Hardware, RAM and GPU-memory dashboard | Real local measurements; unavailable values shown explicitly; hardware refresh |
| 38 | Recorded-job processing time and audio-duration ratio | Measured and saved on new clips; not claimed as microphone streaming latency |
| 39 | Real-time microphone conversion | Seed streaming implemented; fresh CUDA throughput benchmark required; physical GPU streaming remains unverified |
| 40 | OBS / virtual audio routing | Recorded playback can select an already installed virtual output when browser permits; live output uses AudioContext.setSinkId when supported; no virtual driver installation |
| 41 | D: models, recordings, caches/temp; storage dashboard and safe cleanup | Windows D: default; runtime temp/cache directed there; category dashboard; existing weights reused; missing D: requires explicit override |
| 42 | Reliable local launch, backup/restore and complete validation | Single launcher plus read-only diagnostics, verified ZIP backup/restore; backend/browser checked; actual Windows launch and RTX 2060 memory fit remain unverified |
| 43 | Per-profile adaptation checkpoints without base-model duplication | Implemented; real two-step training and adapted conversion passed, ~715 KB candidate |
| 44 | Audition/rating gate and activation rollback | Implemented; rated preview required; deactivate/delete preserves base weights and recordings |
| 45 | Bounded browser live transport and hardware readiness | AudioWorklet/WebSocket/playback protocol fixture checked; actual CPU benchmark blocks live; CUDA hardware remains unverified |
| 46 | Installation repair and visible build identification | One-click dependency/model readiness check, wsproto included, updated dashboard with build label and real library totals |

Child identity verification and unsupported synthesis languages remain unavailable. Seed adaptation is an experimental final-head method, not upstream full fine-tuning. Live readiness is measured per profile/settings/device. The original specification explicitly makes real-time support contingent on feasibility. These limits cannot be resolved by relabeling recorded conversion as live conversion.
