#!/usr/bin/env python3
"""Builds assets/easypdf.ico and assets/easypdf.png.

There are two possible sources:

1. **Your own drawing**: leave a square image (ideally a 512x512 PNG with a
   transparent background) at ``assets/easypdf-original.png`` and that is used.
2. **The icon drawn in code** in ``easypdf.ui.icons`` (the default when the
   file above is not there).

Either way the window, the executable and the installer end up sharing exactly
the same image.

Usage:  python tools/make_icon.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

#: The same sizes the application window uses.
SIZES = (16, 24, 32, 48, 64, 128, 256)

#: Optional image of your own, which takes precedence over the drawn icon.
SOURCE_NAME = "easypdf-original.png"


def _squared(image):
    """Centre the image on a transparent square canvas."""
    from PIL import Image

    if image.width == image.height:
        return image
    side = max(image.width, image.height)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    return canvas


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
