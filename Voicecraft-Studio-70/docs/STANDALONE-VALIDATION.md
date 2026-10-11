# Voicecraft Studio 70 validation

Release 70.0.0; validation performed October 11, 2026. Original VoiceCraft Studio files and prior installers remain unchanged. The Chatterbox engine adapter is byte-identical to VoiceCraft Studio 1.0.0.

## Verified in this environment

- **41 backend tests passed**, with two upstream deprecation warnings. These include existing 37 audio/profile/consent/jobs/security/model tests and four desktop-runtime/lifecycle cases.
- Desktop runtime first installation verifies the official Electron 44.7.0 Windows archive SHA-256 and ZIP integrity. Installed runtime files are checked on later launches; corrupted runtime files trigger repair. Wrong-hash downloads are rejected before execution. A missing first-start destination folder discovered in Windows validation was fixed and retested.
- Lifecycle tests verify loopback port 8791, no external-browser launch, and engine shutdown both when the desktop window exits normally and when the window process fails.
- A real **Electron 44.7.0 Linux window** executed the retained interface against the real local engine: synthetic microphone capture, script choices, recording adjustments/preview/reset, import and original preservation, per-profile volume/style settings, all ten Turbo presets using actual downloaded checkpoints, playback, generated-audio editing, full narration, native export integration, history deletion, persistence after reload, and narrow-layout checks. No frontend errors occurred.
- Electron renderer Node access is disabled, context isolation and sandbox options are enabled, and external navigation/new windows are refused. Microphone capture uses a synthetic test device; the app's permission handler remains active.
- Export testing invokes the desktop Save As integration with a scripted test-only destination and verifies real MP3 bytes. The human interaction with the Save As dialog and physical microphone picker were not tested on a physical PC. JavaScript confirmation responses are scripted in the release harness to avoid two simultaneous debugger clients answering the same dialog.
- Native desktop-close confirmation cancellation retains the app window; the test harness confirms closure afterward. Cancel/confirm choices are scripted only by tests, not shipped as application overrides.
- Official Electron Windows `--version` returned **44.7.0** under Wine 10.0. Its SHA-256 and archive integrity were verified before testing.
- The x64 NSIS installer built successfully with warnings treated as errors in native launcher compilation. Installer execution and installed launcher's bundled Python `--check-runtime` succeeded under Wine. Windows bundled runtime is Python **3.11.9 x64**.
- Silent uninstall removed the QA installation while preserving synthetic voice-data sentinels, the downloaded renderer, and older VoiceCraft/Voice Control Room data sentinels.
- Windows native storage-folder picker opens, accepts the selected folder, saves the selection, and reports success under Wine.
- Linux dependency consistency (`pip check`), Python compilation, and desktop JavaScript syntax checks passed.

## Limits and checks not claimed as passed

- This cloud machine is Linux. Wine did not reliably render the **Windows Electron window** with normal Windows sandbox behavior; this is an unverified Windows UI integration check. The real Linux Electron window workflow above is not a substitute for a physical Windows test.
- The target Windows PC, real microphone, output sound device, NVIDIA driver, RTX 2060, and CUDA 12.4 execution were not available here. CUDA package selection/fallback remains the existing implementation; physical GPU execution is unverified.
- No guaranteed zero-error installation, exact voice duplication, native emotion acting, or generation-time promise is made. Presets change supported audio/delivery parameters; short preview length is not processing speed.
- Earlier VoiceCraft 1.0.0 validation includes real Windows CPU inference with both Chatterbox adapters and a browser-driven Windows backend workflow. That is historical evidence for the unchanged adapter, not a newly performed Windows standalone-window test.
- Installed desktop renderer first download was supplied from the independently verified official archive in the Wine preparation check; Windows Python HTTP retrieval on a physical PC was not tested. The official download was retrieved with TLS verification on Linux and checksum validated.
- The installer is unsigned. A signing certificate was not provided.

## Reproduce release checks

Use a new empty synthetic QA data directory; never run these tests against personal profiles. Install Python development dependencies from existing files and run:

```text
python -m pytest tests -q
```

Start the backend with `STUDIO2_DATA_DIR` pointing to the QA directory, `STUDIO2_MODEL_DIR` pointing to verified checkpoints, and port 8791. For desktop testing, use the official Electron 44.7.0 runtime. Install the pinned test dependency with `npm ci --prefix desktop --ignore-scripts`, then run `node tests/desktop_smoke.cjs` with:

- `ELECTRON_EXE`: official renderer executable.
- `PYTHON_EXE`: Python interpreter with Playwright.
- `VOICECRAFT_TEST_REFERENCE`: synthetic, authorized reference WAV.
- `VOICECRAFT_TEST_ORIGIN`: matching loopback test engine URL.
- `VOICECRAFT_TEST_EXPORT`: disposable MP3 output path.
- `NODE_PATH`: desktop/node_modules, if needed for Node module resolution.

The harness requires an empty profile library and performs real model inference. On this isolated Linux container only, `VOICECRAFT_LINUX_QA_NO_SANDBOX=1` was necessary because container namespace policy blocks Chromium's OS sandbox. This sets a test-process command argument; the shipped application does not disable its sandbox or Windows security settings.
