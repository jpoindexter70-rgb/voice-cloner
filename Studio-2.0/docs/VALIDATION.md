# Validation and remaining prerequisites

Executed in this cloud machine:

- Isolated Python 3.11 environment with pinned CPU torch/torchaudio 2.6.0 and chatterbox-tts 0.1.7. `pip check` passes.
- 18 backend integration tests pass: separate profile settings/reference history, persistence after app recreation, adult consent/revocation, locked children, actual WAV/MP3 processing, serialized jobs, batch orchestration, cancellation without partial results, failure/retry, non-destructive editing, safe profile deletion, hosted authentication/Origin protection, verified ZIP backup/restore and malformed/tampered backup rejection.
- Real verified checkpoints loaded; Expressive and Turbo produced actual reference-conditioned speech. Recorded voice conversion ran with the real shared S3 engine. WAV and MP3 outputs were decoded; model unloading completed.
- Real two-segment synthesis produced 15.56 seconds of audio in 65.8 seconds, using one selected profile reference.
- Browser tests: synthetic microphone selection/recording, preview, reference save, playback and selection. Browser REAL synthesis, playback advancing, WAV/MP3 downloads, two-script batch, actual recorded conversion, private ZIP backup and fixture deletion pass with no JavaScript errors.
- Docker image built after resolving this cloud builder's proxy DNS and installing with the existing trusted CA bundle; no TLS/signature/hash checks were disabled. The private container refused unauthenticated access and performed REAL synthesis plus MP3 export using verified mounted checkpoints. This is a local container behind simulated HTTPS ingress, not a public deployment.

Additional local-only work:

- Saved local device/gain/noise/profile preferences survive restart. Unauthorized remembered-profile changes are refused.
- Actual FFmpeg edit previews preserve originals, do not add profile records and clean their temporary preview files. Trim/pitch/speed now respect input sample rate and trim before speed processing; a 48 kHz duration/frequency regression check passes.
- Original downloads preserve bytes and reject other profiles. Generated deletion removes only the selected profile's clip and encoded MP3.
- Hardware dashboard measures OS/Python/CPU/RAM/disk and actual CUDA memory when available. Newly generated clips record total processing seconds and audio-duration ratio, explicitly not live latency.
- New local browser check passed: saved microphone/gain/noise/profile after reload, permission record, original download, preview gating/edit save, hardware/memory and storage categories, with no JavaScript errors. Device input was synthetic, not physical hardware.
- Local launcher directs runtime caches/temp to the data drive, reuses existing verified weights on repair and reopens a running Studio without starting another inference server.

Not executed or unavailable:

- Optional hosting, outside the current local-only scope: no Hugging Face deployment token or studio password is injected; account access returned HTTP 401. The deployment script prepares a private free-CPU Space and a private dataset for durable profile storage. Actual hosted deployment and dataset syncing require account access and must be tested before claiming durability. An isolated mirror fixture verifies the profile save/restore/delete hooks; it is not a live dataset test.
- Independently verified guardian authorization and restricted child accounts. Child enrollment/playback/generation stays locked; local self-attestation is not presented as verification.
- Windows launchers, physical microphone/output hardware, RTX 2060 peak VRAM and actual CUDA fallback. Browser output routing is capability-dependent and gives explicit unsupported-device errors.
- Real-time conversion/virtual audio devices, engine adaptation/retraining, personal listening quality/similarity. Zero-shot references do not train a per-profile model. Original sources are retained separately from normalized references and edits.

The browser-only single HTML edition is a library-only offline companion; it does not execute the neural engine. The full app uses this independent browser UI and its own AI server. Never label the HTML companion as the complete voice-cloning app.
