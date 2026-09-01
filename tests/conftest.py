"""Configuracion comun de las pruebas."""

from __future__ import annotations

import os
import sys

import pytest

# Qt debe arrancar sin pantalla en integracion continua.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pymupdf  # noqa: E402


@pytest.fixture()
def sample_pdf_bytes() -> bytes:
    """PDF de tres paginas con texto conocido."""
    doc = pymupdf.open()
    for index in range(3):
        page = doc.new_page()
        page.insert_text((72, 100), f"Pagina {index + 1} con la palabra EasyPDF", fontsize=16)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def sample_pdf(tmp_path, sample_pdf_bytes) -> str:
    path = tmp_path / "muestra.pdf"
    path.write_bytes(sample_pdf_bytes)
    return str(path)


@pytest.fixture(scope="session")
def qapp():
    """QApplication unica para toda la sesion de pruebas."""
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture()
def sample_image_bytes() -> bytes:
    """PNG de 200x120 con un rectangulo azul."""
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=120)
    page.draw_rect(pymupdf.Rect(0, 0, 200, 120), color=(0.2, 0.4, 0.9), fill=(0.2, 0.4, 0.9))
    data = page.get_pixmap().tobytes("png")
    doc.close()
    return data


@pytest.fixture()
def sample_image(tmp_path, sample_image_bytes) -> str:
    path = tmp_path / "logo.png"
    path.write_bytes(sample_image_bytes)
    return str(path)
