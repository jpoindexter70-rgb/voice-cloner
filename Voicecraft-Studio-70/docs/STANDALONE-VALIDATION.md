# Voicecraft Studio 70 validation

Release 70.1.2; validation performed October 11, 2026. The older VoiceCraft Studio 1.0.0 source remains unchanged; its previous download is retained at its original commit. The Chatterbox engine adapter is byte-identical to VoiceCraft Studio 1.0.0.

## Verified in this environment

- **51 backend tests passed**, with two upstream deprecation warnings. These include existing 37 audio/profile/consent/jobs/security/model tests, nine desktop-runtime/lifecycle and startup-gate cases, and five tone-control/persistence cases.
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

## 70.1.0 paste correction

Added native editing menu roles for Ctrl+V, Ctrl+C, Ctrl+X, Select All, Undo/Redo and an editable right-click menu with Paste. The script remains a regular textarea and no clipboard contents are uploaded. A real Electron clipboard test checks single-line and multiline Unicode narration pasted through Ctrl+V and invokes the editable right-click menu. Preview cancellation and every voice-engine/backend behavior are unchanged by this patch.

Run `node tests/desktop_clipboard.cjs` with ELECTRON_EXE, VOICECRAFT_TEST_ORIGIN and the same desktop test environment described above.

## Expanded voice adjustments

Actual FFmpeg signal tests quantify the intended bass, treble and presence-band gain, softness high-frequency reduction and unchanged duration. API tests check profile-setting persistence, invalid range rejection, generation settings, recording/generated-audio previews, and preservation of original references. Additional real desktop checks exercise all sliders, unsupported Turbo control disabling, real Turbo and Original previews, recording tone preview/editing, settings after reload and the home dashboard.

Expanded-control desktop results passed with real Turbo and Original checkpoints: Turbo preview 4.52 seconds, Original preview 4.12 seconds. The microphone cover/profile dashboard, per-profile controls, recording tone preview/editing and reload persistence passed. A layout review changed the additional-controls panel from a crowded horizontal row to a responsive grid. Windows FFmpeg tone/noise processing also passed under Wine using the pinned Windows runtime. Physical Windows renderer, microphone and GPU checks remain unverified as stated above.

## 70.1.1 direct startup

- The native launcher starts hidden. Routine runtime/dependency/model verification does not expose Setup & Diagnostics. Python signals installation or repair explicitly before downloads; failures reveal captured diagnostics with Retry setup.
- The actual compiled Windows launcher was exercised under Wine with isolated Python startup fixtures: warm launch, process exit and reopening, failure followed by Retry setup, required repair, a setup marker split across pipe reads, and a repeated shortcut request during quiet startup. Window visibility and disabled Open Studio before readiness were checked through Win32 APIs. All passed. These fixtures verify launcher behavior, not physical Windows model inference.
- Python runtime tests check that verified renderer/model reuse stays quiet, renderer corruption and missing models request setup, integrity failures are rejected, and closing/failing desktop processes stop the local engine.
- Installer remains per-user and preserves existing profile data and downloaded models. No Chatterbox adapter, audio controls, or preview cancellation behavior was changed.

The 70.1.1 regression run repeated the real Electron desktop workflow with synthetic audio: all ten Turbo styles, microphone capture, import/edit previews, playback, native MP3 export, full narration, history deletion, reload persistence, external navigation blocking, and close confirmation. It passed. Native Ctrl+V with multiline Unicode and the right-click Paste menu passed again. Automated backend/runtime suite: 48 passed, two upstream deprecation warnings.

## 70.1.2 fast opening

- The desktop window starts before the owned local-engine process. A local opening page automatically transitions to the workspace when the loopback server responds. No external browser or console is launched.
- A real Electron test deliberately delayed engine launch by three seconds. The desktop window appeared in **241 ms** in the Linux test environment; the workspace then opened while real model checks/loading continued. The test created a profile, entered a script and imported a synthetic reference during startup, waited for Turbo readiness, then generated a real **2.8-second** audio preview. Generation controls were disabled until ready, then enabled automatically. This timing excludes Windows bundled-Python/renderer verification and is not a promise for the target PC.
- Existing installed Windows renderer preparation, including full SHA-256 verification, took **1.281 seconds under Wine**. Verification remains enabled, including model verification before use.
- Automated tests exercise desktop-before-engine process ordering, window-close cleanup, failed engine-process cleanup, server-before-model-check ordering, model installation when missing, Turbo preloading, failed-load status, and API generation/install/unload gates while profiles remain available. **51 tests passed** with two upstream warnings.
- Turbo is preloaded without a family reference. The idle timer starts again after loading; consent and per-profile reference selection still apply to every generation. Deleting/revoking a profile during startup cannot unload a model while it is loading. The Chatterbox engine adapter remains unchanged.
- Physical Windows desktop timing, microphone hardware and GPU execution remain unverified in this environment.

The final 70.1.2 desktop regression run passed all ten real Turbo styles, synthetic microphone capture, recording import and adjustment previews, original preservation, playback, generated-audio editing, full narration, MP3 export, history deletion, reload persistence, navigation restrictions and close confirmation. The Windows launcher visibility/reopening/repair/retry integration fixtures also passed again under Wine.
