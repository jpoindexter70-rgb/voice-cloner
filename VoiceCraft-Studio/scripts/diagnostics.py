"""Read-only local Studio diagnostics. Never prints credentials or audio contents."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.app import default_root
from studio.system import report
from studio.engine import VoiceEngine


def main():
    import os
    root=default_root()
    if not root.exists():
        print('Studio data folder does not exist yet:',root)
        print('Run Open Studio 2.0.cmd once to prepare the separate application.')
        return
    model_root=Path(os.getenv('STUDIO2_MODEL_DIR',str(root/'shared-models')))
    print(json.dumps(report(root,model_root),indent=2))
    print(json.dumps(VoiceEngine(model_root).status(),indent=2))
    print('Data and model files were not modified. Credentials and recordings are not included.')


if __name__=='__main__':main()
