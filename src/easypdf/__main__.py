"""Permite ejecutar la aplicacion con ``python -m easypdf``.

Se usa un import absoluto a proposito: PyInstaller ejecuta este archivo como
guion suelto (sin paquete padre), y un import relativo fallaria al arrancar el
ejecutable.
"""

from easypdf.app import main

if __name__ == "__main__":
    raise SystemExit(main())
