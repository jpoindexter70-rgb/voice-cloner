from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from pathlib import Path

root = Path(SPECPATH).parent
datas = [(str(root / 'studio/static'), 'studio/static'), (str(root / 'docs/THIRD-PARTY-NOTICES.md'), 'licenses')]
binaries = []
hiddenimports = ['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on', 'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineCore', 'PySide6.QtNetwork', 'chatterbox.tts', 'chatterbox.tts_turbo',
    'backports', 'backports.tarfile']
for package in ['perth', 'chatterbox', 'imageio_ffmpeg', 's3tokenizer', 'librosa', 'diffusers']:
    data, binary, imports = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += imports
datas += collect_data_files('transformers')
datas += collect_data_files('tokenizers')
hiddenimports += collect_submodules('transformers.models.llama')
hiddenimports += collect_submodules('transformers.models.gpt2')

a = Analysis([str(root / 'scripts/desktop_entry.py')], pathex=[str(root)], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports,
    excludes=['gradio', 'gradio_client', 'matplotlib', 'tkinter', 'IPython', 'pytest'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FamilyVoiceCloner',
    console=False, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FamilyVoiceCloner')
