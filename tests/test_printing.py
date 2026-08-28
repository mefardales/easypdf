"""Pruebas de la salida de impresion (imprimiendo a un PDF)."""

import pymupdf
import pytest

pytest.importorskip("PySide6.QtPrintSupport")

from PySide6.QtPrintSupport import QPrinter  # noqa: E402

from easypdf.document import PdfDocument  # noqa: E402
from easypdf.model import Annotation, Kind  # noqa: E402
from easypdf.printing import pages_for_printer, render_to_printer  # noqa: E402


def _printer(path) -> QPrinter:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(path))
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


def test_rango_de_paginas_del_dialogo(qapp, tmp_path, sample_pdf_bytes):
    printer = _printer(tmp_path / "rango.pdf")
    printer.setPrintRange(QPrinter.PageRange)
    printer.setFromTo(2, 3)
    assert pages_for_printer(printer, 3) == [1, 2]
    printer.setPrintRange(QPrinter.AllPages)
    assert pages_for_printer(printer, 3) == [0, 1, 2]
    printer.setPrintRange(QPrinter.CurrentPage)
    assert pages_for_printer(printer, 3) == []
