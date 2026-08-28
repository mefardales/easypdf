"""Pruebas de la capa de documento."""

import pymupdf
import pytest

from easypdf.document import PasswordRequired, PdfDocument, PdfError
from easypdf.model import Annotation, Kind


def test_abrir_y_metadatos(sample_pdf):
    doc = PdfDocument.open(sample_pdf)
    assert doc.page_count == 3
    assert doc.name == "muestra.pdf"
    width, height = doc.page_size(0)
    assert round(width) == 595 and round(height) == 842
    assert doc.can_print
    doc.close()


def test_render_devuelve_pixeles(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    page = doc.render_page(0, 2.0)
    assert page.width == 1190 and page.height == 1684
    assert len(page.samples) == page.stride * page.height
    doc.close()


def test_busqueda_encuentra_todas_las_paginas(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    hits = doc.search("EasyPDF")
    assert len(hits) == 3
    assert [h.page for h in hits] == [0, 1, 2]
    assert doc.search("   ") == []
    doc.close()


def test_texto_de_pagina(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    assert "Pagina 2" in doc.page_text(1)
    doc.close()


def test_exportar_incluye_las_anotaciones(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    anns = [
        Annotation(kind=Kind.RECT, page=0, rect=(50, 50, 200, 150)),
        Annotation(kind=Kind.TEXT, page=1, rect=(50, 50, 250, 100), text="hola"),
    ]
    salida = pymupdf.open(stream=doc.export_bytes(anns), filetype="pdf")
    assert [a.type[1] for a in salida[0].annots()] == ["Square"]
    assert [a.type[1] for a in salida[1].annots()] == ["FreeText"]
    assert list(salida[2].annots()) == []
    doc.close()


def test_exportar_dos_veces_no_duplica(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    anns = [Annotation(kind=Kind.RECT, page=0, rect=(50, 50, 200, 150))]
    doc.export_bytes(anns)
    salida = pymupdf.open(stream=doc.export_bytes(anns), filetype="pdf")
    assert len(list(salida[0].annots())) == 1
    doc.close()


def test_guardar_como_escribe_el_archivo(tmp_path, sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    destino = tmp_path / "salida.pdf"
    doc.save_as(str(destino), [Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90))])
    assert destino.exists()
    assert doc.path == str(destino)
    assert not list(tmp_path.glob("*.easypdf-tmp"))
    guardado = pymupdf.open(str(destino))
    assert len(list(guardado[0].annots())) == 1
    doc.close()


def test_documento_protegido(tmp_path, sample_pdf_bytes):
    origen = pymupdf.open(stream=sample_pdf_bytes, filetype="pdf")
    protegido = tmp_path / "protegido.pdf"
    origen.save(
        str(protegido),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="duenno",
        user_pw="secreta",
    )
    origen.close()
    with pytest.raises(PasswordRequired):
        PdfDocument.open(str(protegido))
    doc = PdfDocument.open(str(protegido), password="secreta")
    assert doc.page_count == 3
    assert len(list(pymupdf.open(
        stream=doc.export_bytes([Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90))]),
        filetype="pdf",
    )[0].annots())) == 1
    doc.close()


def test_archivo_invalido(tmp_path):
    roto = tmp_path / "roto.pdf"
    roto.write_bytes(b"esto no es un pdf")
    with pytest.raises(PdfError):
        PdfDocument.open(str(roto))
    with pytest.raises(PdfError):
        PdfDocument.open(str(tmp_path / "no-existe.pdf"))
