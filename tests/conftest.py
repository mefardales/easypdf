"""Settings shared by all the tests."""

from __future__ import annotations

import os
import sys

import pytest

# Qt has to start without a screen on continuous integration.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pymupdf  # noqa: E402


@pytest.fixture()
def sample_pdf_bytes() -> bytes:
    """A three page PDF with known text."""
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
    """A single QApplication for the whole test session."""
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture()
def sample_image_bytes() -> bytes:
    """A 200x120 PNG with a blue rectangle."""
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
