"""Prepare private hosted mode and verified models, then serve the browser UI."""
import os
from pathlib import Path
from .models import download, verify


def main():
    root=Path(os.getenv('STUDIO2_DATA_DIR','/data/studio2'))
    root.mkdir(parents=True,exist_ok=True)
    os.environ['STUDIO2_DATA_DIR']=str(root)
    os.environ.setdefault('HF_HOME',str(root/'model-cache'))
    os.environ.setdefault('NUMBA_CACHE_DIR',str(root/'numba-cache'))
    os.environ.setdefault('XDG_CACHE_HOME',str(root/'cache'))
    os.environ.setdefault('PORT','7860')
    if not os.getenv('STUDIO2_PUBLIC_ORIGIN') and os.getenv('SPACE_HOST'):
        os.environ['STUDIO2_PUBLIC_ORIGIN']='https://'+os.environ['SPACE_HOST']
    if not os.getenv('STUDIO2_PUBLIC_ORIGIN') or len(os.getenv('STUDIO2_PASSWORD',''))<16:
        raise RuntimeError('Configure the HTTPS studio origin and an access password of at least 16 characters before hosting.')
    for name in ['expressive','turbo']:
        try:verify(root/'shared-models',name)
        except (OSError,ValueError,KeyError,RuntimeError):download(root/'shared-models',name)
    import uvicorn
    from .app import create_app
    uvicorn.run(create_app(root),host='0.0.0.0',port=int(os.environ['PORT']))


if __name__=='__main__':main()
