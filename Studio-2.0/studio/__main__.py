import argparse
import os
import threading
import time
import webbrowser
import json
import http.cookiejar
import urllib.request
import uvicorn
from .app import create_app, default_root


def prepare_local_storage():
    root = default_root()
    root.mkdir(parents=True, exist_ok=True)
    for variable, folder in [('HF_HOME', 'model-cache'), ('NUMBA_CACHE_DIR', 'numba-cache'),
                             ('PIP_CACHE_DIR', 'pip-cache'), ('TMP', 'temporary'), ('TEMP', 'temporary'),
                             ('TMPDIR', 'temporary')]:
        location = root / folder
        location.mkdir(exist_ok=True)
        os.environ[variable] = str(location.resolve())
    import tempfile
    tempfile.tempdir = str((root / 'temporary').resolve())


def studio_already_running(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    try:
        opener.open('http://127.0.0.1:' + str(port) + '/', timeout=2).close()
        with opener.open('http://127.0.0.1:' + str(port) + '/api/health', timeout=2) as response:
            return json.load(response).get('application') == 'ai-voice-cloning-studio-2'
    except (OSError, ValueError):
        return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    hosted=bool(os.getenv('STUDIO2_PUBLIC_ORIGIN'));port=int(os.getenv('PORT','8770'))
    if not hosted:
        prepare_local_storage()
        if studio_already_running(port):
            print('Studio 2.0 is already running. Opening the existing local session.')
            if not args.no_browser:webbrowser.open('http://127.0.0.1:' + str(port))
            return
    server=uvicorn.Server(uvicorn.Config(create_app(),host='0.0.0.0' if hosted else '127.0.0.1',port=port))
    if os.name=='nt' and not args.no_browser and not hosted:
        def open_when_ready():
            for _ in range(300):
                if server.started:webbrowser.open('http://127.0.0.1:'+str(port));return
                if server.should_exit:return
                time.sleep(.1)
        threading.Thread(target=open_when_ready,daemon=True).start()
    server.run()


if __name__=='__main__':main()
