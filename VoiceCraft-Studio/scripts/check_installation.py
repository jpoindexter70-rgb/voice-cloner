"""Fast local readiness check for the one-click launcher; never downloads or prints secrets."""
import importlib.metadata
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.models import SPECS
from studio.seed_assets import ASSETS

def ready():
    source=Path(__file__).resolve().parents[1]
    data=Path(os.environ['STUDIO2_DATA_DIR']) if os.getenv('STUDIO2_DATA_DIR') else Path('D:/AI-Voice-Cloning-Studio') if os.name=='nt' else source/'.runtime'
    root=Path(os.environ.get('STUDIO2_MODEL_DIR',str(data/'shared-models')))
    try:
        for name,version in [('fastapi','0.115.12'),('chatterbox-tts','0.1.7'),('munch','4.0.0'),('wsproto','1.3.2'),('torch','2.6.0')]:
            if importlib.metadata.version(name).split('+')[0]!=version:return False
        for name,spec in SPECS.items():
            manifest=json.loads((root/name/'manifest.json').read_text())
            if manifest['repository']!=spec['repository'] or spec.get('revision',manifest['revision'])!=manifest['revision']:return False
            for filename in spec['files']:
                if (root/name/filename).stat().st_size!=manifest['files'][filename]['size']:return False
        return True
    except (OSError,ValueError,KeyError,importlib.metadata.PackageNotFoundError):return False

if __name__=='__main__':sys.exit(0 if ready() else 1)
