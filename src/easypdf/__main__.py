"""Lets the application run with ``python -m easypdf``.

The import is absolute on purpose: PyInstaller runs this file as a loose
script (with no parent package), and a relative import would fail when the
executable starts.
"""

from easypdf.app import main

if __name__ == "__main__":
    raise SystemExit(main())
