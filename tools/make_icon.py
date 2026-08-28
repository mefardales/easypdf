#!/usr/bin/env python3
"""Genera assets/easypdf.ico y assets/easypdf.png a partir del icono de la app.

El dibujo vive en ``easypdf.ui.icons`` (se pinta con Qt), asi que la ventana,
el ejecutable y el instalador comparten exactamente la misma imagen.

Uso:  python tools/make_icon.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

#: Se toman los mismos tamanos que usa la ventana de la aplicacion.
SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> int:
    from PIL import Image
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from easypdf.ui import icons

    assets = os.path.join(ROOT, "assets")
    os.makedirs(assets, exist_ok=True)

    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for size in SIZES:
            frame_path = os.path.join(tmp, f"icon-{size}.png")
            if not icons.render("app", size).save(frame_path, "PNG"):
                raise RuntimeError(f"no se pudo generar el icono de {size} px")
            with Image.open(frame_path) as image:
                frames.append(image.convert("RGBA"))

    png_path = os.path.join(assets, "easypdf.png")
    ico_path = os.path.join(assets, "easypdf.ico")
    frames[-1].save(png_path)
    frames[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Escrito {png_path}")
    print(f"Escrito {ico_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
