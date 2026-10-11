import argparse
import os
import threading
import time
import webbrowser
import uvicorn
from .app import create_app


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    hosted=bool(os.getenv('STUDIO2_PUBLIC_ORIGIN'));port=int(os.getenv('PORT','8770'))
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
