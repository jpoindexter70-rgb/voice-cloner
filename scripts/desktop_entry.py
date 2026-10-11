"""Frozen executable entry point; Python and dependencies are bundled."""
import sys
import traceback
from studio.desktop import main

if __name__ == '__main__':
    try:
        result = main()
    except Exception:
        from studio.storage import data_directory
        root = data_directory() / 'logs'
        root.mkdir(parents=True, exist_ok=True)
        message = traceback.format_exc()
        (root / 'startup-error.log').write_text(message, encoding='utf-8')
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message + '\nDiagnostics: ' + str(root),
                'Family AI Voice Cloner Pro could not start', 0x10)
        result = 1
    raise SystemExit(result)
