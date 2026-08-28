"""Pruebas de la salida de impresion (imprimiendo a un PDF)."""

import pymupdf
import pytest

pytest.importorskip("PySide6.QtPrintSupport")

from PySide6.QtPrintSupport import QPrinter  # noqa: E402

from easypdf.document import PdfDocument  # noqa: E402
from easypdf.model import Annotation, Kind  # noqa: E402
from easypdf.printing import (  # noqa: E402
    MAX_PAGE_PIXELS,
    MAX_PRINT_DPI,
    page_scale,
    pages_for_printer,
    render_to_printer,
)


def _printer(path, dpi: int = 150) -> QPrinter:
    """Impresora a un PDF. Con 150 ppp las pruebas son rapidas en cualquier SO."""
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setResolution(dpi)
    return printer


def test_imprime_todas_las_paginas(qapp, tmp_path, sample_pdf_bytes):
    salida = tmp_path / "impreso.pdf"
    assert render_to_printer(sample_pdf_bytes, _printer(salida))
    assert salida.exists()
    assert pymupdf.open(str(salida)).page_count == 3


def test_imprime_solo_las_paginas_pedidas(qapp, tmp_path, sample_pdf_bytes):
    salida = tmp_path / "una.pdf"
    assert render_to_printer(sample_pdf_bytes, _printer(salida), pages=[1])
    assert pymupdf.open(str(salida)).page_count == 1


def test_la_impresion_incluye_las_anotaciones(qapp, tmp_path, sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    datos = doc.export_bytes(
        [Annotation(kind=Kind.RECT, page=0, rect=(60, 60, 400, 300),
                    color=(1.0, 0.0, 0.0), width=6.0)]
    )
    doc.close()
    salida = tmp_path / "con-anotacion.pdf"
    assert render_to_printer(datos, _printer(salida), pages=[0])
    pix = pymupdf.open(str(salida))[0].get_pixmap()
    # Debe haber pixeles claramente rojos en la hoja impresa.
    rojos = 0
    for offset in range(0, len(pix.samples) - 3, pix.n):
        r, g, b = pix.samples[offset], pix.samples[offset + 1], pix.samples[offset + 2]
        if r > 170 and g < 100 and b < 100:
            rojos += 1
            if rojos > 50:
                break
    assert rojos > 50


def test_sin_paginas_no_imprime(qapp, tmp_path, sample_pdf_bytes):
    assert not render_to_printer(sample_pdf_bytes, _printer(tmp_path / "vacio.pdf"), pages=[])


def test_page_scale_respeta_los_topes():
    a4 = (595.0, 842.0)
    # Hoja pequena: manda el ajuste a la hoja
    assert page_scale(*a4, 595.0, 842.0) == pytest.approx(1.0)
    # Impresora de 1200 ppp: se limita a MAX_PRINT_DPI
    enorme = (595.0 * 1200 / 72, 842.0 * 1200 / 72)
    assert page_scale(*a4, *enorme) == pytest.approx(MAX_PRINT_DPI / 72.0)
    # Un plano enorme (1x1,5 m) a 300 ppp serian 145 MP: se recorta la escala
    plano = (2835.0, 4252.0)   # puntos PDF
    escala = page_scale(*plano, 2835.0 * 1200 / 72, 4252.0 * 1200 / 72)
    assert escala < MAX_PRINT_DPI / 72.0
    assert (plano[0] * escala) * (plano[1] * escala) == pytest.approx(
        MAX_PAGE_PIXELS, rel=0.01
    )
    assert page_scale(0.0, 0.0, 100.0, 100.0) == 1.0


def test_rango_de_paginas_del_dialogo(qapp, tmp_path, sample_pdf_bytes):
    printer = _printer(tmp_path / "rango.pdf")
    printer.setPrintRange(QPrinter.PageRange)
    printer.setFromTo(2, 3)
    assert pages_for_printer(printer, 3) == [1, 2]
    printer.setPrintRange(QPrinter.AllPages)
    assert pages_for_printer(printer, 3) == [0, 1, 2]
    printer.setPrintRange(QPrinter.CurrentPage)
    assert pages_for_printer(printer, 3) == []
