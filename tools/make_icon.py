#!/usr/bin/env python3
"""Genera assets/easypdf.ico y assets/easypdf.png.

Hay dos fuentes posibles:

1. **Tu propio dibujo**: deja una imagen cuadrada (idealmente 512x512 PNG con
   fondo transparente) en ``assets/easypdf-original.png`` y se usara esa.
2. **El icono dibujado por codigo** en ``easypdf.ui.icons`` (opcion por
   defecto si no existe el archivo anterior).

En ambos casos la ventana, el ejecutable y el instalador acaban compartiendo
exactamente la misma imagen.

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

#: Imagen propia opcional que tiene prioridad sobre el dibujo por codigo.
SOURCE_NAME = "easypdf-original.png"


def _squared(image):
    """Centra la imagen en un lienzo cuadrado transparente."""
    from PIL import Image

    if image.width == image.height:
        return image
    side = max(image.width, image.height)
    lienzo = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    lienzo.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    return lienzo


def main() -> int:
    from PIL import Image
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from easypdf.ui import icons

    assets = os.path.join(ROOT, "assets")
    os.makedirs(assets, exist_ok=True)

    source = os.path.join(assets, SOURCE_NAME)
    frames = []
    if os.path.exists(source):
        print(f"Usando la imagen {source}")
        with Image.open(source) as original:
            base = _squared(original.convert("RGBA"))
            frames = [base.resize((size, size), Image.LANCZOS) for size in SIZES]
    else:
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
