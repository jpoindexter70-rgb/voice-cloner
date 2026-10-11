# Studio 2.0 — browser edition

Download Studio-2.0.html and open it in Chrome or Edge. This is a self-contained browser app with no Python, package installer, desktop server or old application required. Microphone use requires permission. Some managed browsers block local HTML; direct local-file startup is unverified on Windows.

Implemented: independent family profiles, optional PNG pictures, microphone selection and WAV recording, import/preview/signal evaluation, multiple saved references and primary reference selection, profile settings, adult permission records, revocation and deletion, and private backup export/restore. Profiles and original audio are kept in IndexedDB in this browser on this computer. Clearing browser/site data may erase the library. Export a private backup under Storage & Privacy and save it to D:; the browser edition does not automatically write folders on D:. Keep the HTML file in a fixed location and use the same browser. Restoring a backup skips existing profile IDs.

Child profiles remain locked until a verified guardian process exists. Adult permission is locally documented, not independently identity verified. Any person with this OS/browser account can access browser data; browser storage is not encryption or a verified restricted account system. Backups contain private recordings and permission records. Revocation blocks app playback and new recording enrollment; it cannot recall backups or other copies.

AI cloned speech, conversion, engine training and generated-audio export are UNIMPLEMENTED. Sample playback plays the original reference. No placeholder engine output or synthetic voice quality claims.

Validation: Linux system Chromium via a static HTTP file server, with no application backend, passed profile creation, synthetic microphone recording, evaluation/save, sample playback, selection, revocation/deletion, backup export/restore and persistence after reload. No JS errors. This cloud machine's managed browser policy blocks file:// navigation; direct file opening, physical microphones and Windows remain unverified.

Developer reproduction: serve this folder using a static HTTP server on loopback port 8771; run tests/browser_only_smoke.py using Playwright with /usr/bin/chromium against a clean isolated browser context. Do not target personal data.
