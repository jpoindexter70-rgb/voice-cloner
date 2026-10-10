"""Native Qt desktop window owning the lifetime of its private Python backend."""
import argparse
import hashlib
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback

from .storage import data_directory


def setup_logging(root):
    logs = root / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(logs / 'desktop.log', maxBytes=2_000_000, backupCount=4, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s', force=True)
    # Windowed executables have no stdout/stderr; upstream tools expect file objects.
    if sys.stdout is None:
        sys.stdout = (logs / 'runtime.log').open('a', encoding='utf-8', buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    return logs


class Backend:
    def __init__(self, root):
        self.root = root
        self.server = None
        self.app = None
        self.error = None
        self.url = None
        self.thread = threading.Thread(target=self.run, name='local-backend', daemon=True)

    def run(self):
        from .cli import data_lock
        try:
            with data_lock(self.root):
                import uvicorn
                from .app import create_app
                self.app = create_app(self.root)
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    listener.listen(128)
                    self.url = 'http://127.0.0.1:' + str(listener.getsockname()[1])
                    self.server = uvicorn.Server(uvicorn.Config(
                        self.app, host='127.0.0.1', log_config=None, access_log=False))
                    self.app.state.shutdown = self.stop
                    self.server.run(sockets=[listener])
        except Exception:
            self.error = traceback.format_exc()
            logging.exception('Local backend failed')

    def stop(self):
        if self.server:
            self.server.should_exit = True


def self_test(destination):
    """Check the packaged backend/audio/runtime, never claim neural inference."""
    import tempfile
    import numpy as np
    import soundfile as sf
    from fastapi.testclient import TestClient
    from .app import create_app
    from .cli import check_runtime
    check_runtime()
    with tempfile.TemporaryDirectory(prefix='family-voice-selftest-') as root:
        with TestClient(create_app(root)) as client:
            client.get('/').raise_for_status()
            client.headers['X-VCR-Token'] = client.get('/api/session').json()['token']
            profile = client.post('/api/profiles', json={'name': 'Packaged test', 'consent': True})
            profile.raise_for_status()
            stream = io.BytesIO()
            sf.write(stream, .1 * np.sin(np.arange(240000) * .05), 24000, format='WAV')
            result = client.post('/api/profiles/' + profile.json()['id'] + '/references',
                files={'file': ('fixture.wav', stream.getvalue(), 'audio/wav')}, data={'consent': 'true'})
            result.raise_for_status()
            ident = result.json()['id']
            for fmt in ('wav', 'mp3'):
                response = client.get(f'/api/assets/{ident}/export/{fmt}')
                response.raise_for_status()
                assert len(response.content) > 1000
            assert client.get('/api/health').json()['application'] == 'voice-control-room-advanced'
    report = {'packaged_backend': True, 'engine_imports_watermarker': True,
              'fixture_upload_wav_mp3': True, 'real_synthesis': 'unrun', 'physical_microphone': 'unrun'}
    Path(destination).write_text(json.dumps(report, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', metavar='REPORT')
    parser.add_argument('--smoke-test', metavar='REPORT')
    args = parser.parse_args()
    root = data_directory()
    root.mkdir(parents=True, exist_ok=True)
    logs = setup_logging(root)
    if args.self_test:
        try:
            self_test(args.self_test)
            return 0
        except Exception:
            logging.exception('Packaged self-test failed')
            Path(args.self_test).write_text(json.dumps({'error': traceback.format_exc()}), encoding='utf-8')
            return 1

    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QMessageBox, QFileDialog
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

    app = QApplication(sys.argv[:1])
    app.setApplicationName('Family AI Voice Cloner Pro')
    app.setStyleSheet('QWidget { background:#191c21; color:#f0f1f2; } QPushButton { padding:8px; }')
    key = 'family-voice-' + hashlib.sha256(str(root).encode()).hexdigest()[:24]
    peer = QLocalSocket()
    peer.connectToServer(key)
    if peer.waitForConnected(800):
        peer.write(b'activate'); peer.waitForBytesWritten(800)
        return 0
    single = QLocalServer()
    # A crashed process leaves a Unix socket; an active process was checked above.
    QLocalServer.removeServer(key)
    if not single.listen(key):
        QMessageBox.critical(None, 'Already starting', 'Another copy of the application is starting. Please wait.')
        return 1

    backend = Backend(root)
    window = QMainWindow()
    window.setWindowTitle('Family AI Voice Cloner Pro')
    window.resize(1440, 960)
    label = QLabel('Starting your local Python studio…\nYour recordings remain on this computer.')
    label.setMargin(36)
    window.setCentralWidget(label)
    window.show()
    browser = QWebEngineView()
    # An off-the-record profile avoids storing session cookies after shutdown.
    profile = QWebEngineProfile(app)
    page = QWebEnginePage(profile, browser)
    browser.setPage(page)

    def activate():
        connection = single.nextPendingConnection()
        if connection:
            connection.disconnectFromServer()
        window.showNormal(); window.raise_(); window.activateWindow()
    single.newConnection.connect(activate)

    def permission(origin, feature):
        allowed = str(origin.toString()).rstrip('/') == backend.url
        if allowed and feature == QWebEnginePage.Feature.MediaAudioCapture:
            allowed = QMessageBox.question(window, 'Microphone permission',
                'Allow this local studio to record from your microphone? Audio stays on your computer.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
        else:
            allowed = False
        page.setFeaturePermission(origin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                                  if allowed else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
    page.featurePermissionRequested.connect(permission)

    def download(request):
        filename, _ = QFileDialog.getSaveFileName(window, 'Export audio or project', request.downloadFileName())
        if filename:
            path = Path(filename)
            request.setDownloadDirectory(str(path.parent))
            request.setDownloadFileName(path.name)
            request.accept()
        else:
            request.cancel()
    profile.downloadRequested.connect(download)

    closing = False
    def close_event(event):
        nonlocal closing
        busy = backend.app and (backend.app.state.engine.lock.locked() or any(
            j['status'] in ('queued', 'running') for j in backend.app.state.jobs.values()))
        if busy and not args.smoke_test:
            QMessageBox.information(window, 'Work is in progress',
                'Cancel generation or wait for the current model operation before closing. Your work is saved locally.')
            event.ignore(); return
        closing = True
        backend.stop()
        event.accept()
    window.closeEvent = close_event
    app.aboutToQuit.connect(backend.stop)
    backend.thread.start()
    timer = QTimer()
    started = time.monotonic()
    loaded = False
    smoke_pending = False

    def smoke_result(value):
        if not value:
            return
        report = Path(args.smoke_test)
        window.grab().save(str(report.with_suffix('.png')))
        report.write_text(json.dumps({'native_window': True, 'embedded_ui': True,
            'functional_profiles': True, 'platform': sys.platform, 'physical_microphone': 'unrun'}), encoding='utf-8')
        timer.stop(); window.close(); app.quit()

    def poll():
        nonlocal loaded, smoke_pending
        if backend.error:
            timer.stop()
            if args.smoke_test:
                Path(args.smoke_test).write_text(json.dumps({'error': backend.error}), encoding='utf-8')
                app.exit(1)
            else:
                QMessageBox.critical(window, 'Startup failed', backend.error + '\nDiagnostics: ' + str(logs))
                window.close()
        elif backend.server and backend.server.started and not loaded:
            loaded = True
            window.setCentralWidget(browser)
            browser.setUrl(QUrl(backend.url))
        if args.smoke_test:
            if time.monotonic() - started > 60:
                Path(args.smoke_test).write_text(json.dumps({'error': 'Native UI readiness timed out'}), encoding='utf-8')
                app.exit(1)
            elif loaded:
                page.runJavaScript("document.getElementById('profile-count')?.textContent !== '—' && Number(document.getElementById('profile-count')?.textContent) >= 1", smoke_result)
    timer.timeout.connect(poll)
    timer.start(250)
    result = app.exec()
    backend.stop()
    backend.thread.join(timeout=15)
    single.close()
    import shiboken6
    shiboken6.delete(window)
    shiboken6.delete(profile)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
