"""Frozen executable entry point; Python and dependencies are bundled."""
from studio.desktop import main

if __name__ == '__main__':
    raise SystemExit(main())
