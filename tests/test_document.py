"""Pruebas de la capa de documento."""

import pymupdf
import pytest

from easypdf.document import PasswordRequired, PdfDocument, PdfError
from easypdf.i18n import tr
from easypdf.model import Annotation, Kind


def test_open_and_metadata(sample_pdf):
    doc = PdfDocument.open(sample_pdf)
    assert doc.page_count == 3
    assert doc.name == "muestra.pdf"
    width, height = doc.page_size(0)
    assert round(width) == 595 and round(height) == 842
    assert doc.can_print
    doc.close()


def test_render_returns_pixels(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    page = doc.render_page(0, 2.0)
    assert page.width == 1190 and page.height == 1684
    assert len(page.samples) == page.stride * page.height
    doc.close()


def test_search_finds_every_page(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    hits = doc.search("EasyPDF")
    assert len(hits) == 3
    assert [h.page for h in hits] == [0, 1, 2]
    assert doc.search("   ") == []
    doc.close()


def test_page_text(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    assert "Pagina 2" in doc.page_text(1)
    doc.close()


def test_export_includes_the_annotations(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    anns = [
        Annotation(kind=Kind.RECT, page=0, rect=(50, 50, 200, 150)),
        Annotation(kind=Kind.TEXT, page=1, rect=(50, 50, 250, 100), text="hola"),
    ]
    output = pymupdf.open(stream=doc.export_bytes(anns), filetype="pdf")
    assert [a.type[1] for a in output[0].annots()] == ["Square"]
    assert [a.type[1] for a in output[1].annots()] == ["FreeText"]
    assert list(output[2].annots()) == []
    doc.close()


def test_exporting_twice_does_not_duplicate(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    anns = [Annotation(kind=Kind.RECT, page=0, rect=(50, 50, 200, 150))]
    doc.export_bytes(anns)
    output = pymupdf.open(stream=doc.export_bytes(anns), filetype="pdf")
    assert len(list(output[0].annots())) == 1
    doc.close()


def test_save_as_writes_the_file(tmp_path, sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    target = tmp_path / "salida.pdf"
    doc.save_as(str(target), [Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90))])
    assert target.exists()
    assert doc.path == str(target)
    assert not list(tmp_path.glob("*.easypdf-tmp"))
    stored = pymupdf.open(str(target))
    assert len(list(stored[0].annots())) == 1
    doc.close()


def test_protected_document(tmp_path, sample_pdf_bytes):
    source = pymupdf.open(stream=sample_pdf_bytes, filetype="pdf")
    protected = tmp_path / "protegido.pdf"
    source.save(
        str(protected),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="duenno",
        user_pw="secreta",
    )
    source.close()
    with pytest.raises(PasswordRequired):
        PdfDocument.open(str(protected))
    doc = PdfDocument.open(str(protected), password="secreta")
    assert doc.page_count == 3
    assert len(list(pymupdf.open(
        stream=doc.export_bytes([Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90))]),
        filetype="pdf",
    )[0].annots())) == 1
    doc.close()


def test_invalid_file(tmp_path):
    roto = tmp_path / "roto.pdf"
    roto.write_bytes(b"esto no es un pdf")
    with pytest.raises(PdfError):
        PdfDocument.open(str(roto))
    with pytest.raises(PdfError):
        PdfDocument.open(str(tmp_path / "no-existe.pdf"))


def test_blank_document():
    doc = PdfDocument.blank(3, "Letter")
    assert doc.page_count == 3
    assert [round(v) for v in doc.page_size(0)] == [612, 792]
    assert doc.name == tr("untitled_document")
    assert doc.path is None
    doc.close()


def test_add_duplicate_and_delete_pages(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    assert doc.page_count == 3
    assert doc.add_blank_page(1) == 1
    assert doc.page_count == 4
    assert "Pagina" not in doc.page_text(1)          # la nueva esta en blanco
    assert doc.duplicate_page(0) == 1
    assert doc.page_count == 5
    assert doc.page_text(0) == doc.page_text(1)
    doc.delete_page(1)
    assert doc.page_count == 4
    doc.close()


def test_the_last_page_cannot_be_deleted():
    doc = PdfDocument.blank(1)
    with pytest.raises(PdfError):
        doc.delete_page(0)
    doc.close()


def test_extract_and_put_back_a_page(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    data = doc.extract_page(1)
    doc.delete_page(1)
    assert doc.page_count == 2
    assert "Pagina 2" not in doc.page_text(1)
    doc.insert_page_bytes(data, 1)
    assert doc.page_count == 3
    assert "Pagina 2" in doc.page_text(1)
    doc.close()


def test_move_a_page(sample_pdf_bytes):
    doc = PdfDocument(sample_pdf_bytes)
    doc.move_page(0, 2)
    assert "Pagina 1" in doc.page_text(2)
    doc.move_page(2, 0)
    assert "Pagina 1" in doc.page_text(0)
    doc.close()


def test_new_pages_are_saved(tmp_path):
    doc = PdfDocument.blank(1)
    doc.add_blank_page()
    target = tmp_path / "nuevo.pdf"
    doc.save_as(str(target), [Annotation(kind=Kind.RECT, page=1, rect=(50, 50, 200, 150))])
    stored = pymupdf.open(str(target))
    assert stored.page_count == 2
    assert len(list(stored[1].annots())) == 1
    doc.close()


def test_rotating_a_page_changes_its_orientation():
    document = PdfDocument.blank(pages=1, size="A4")
    width, height = document.page_size(0)
    assert document.page_rotation(0) == 0

    document.set_page_rotation(0, 90)
    assert document.page_rotation(0) == 90
    assert document.page_size(0) == (height, width)

    document.set_page_rotation(0, 180)
    assert document.page_size(0) == (width, height)   # 180 no cambia el tamano

    document.set_page_rotation(0, 0)
    assert document.page_rotation(0) == 0
    assert document.page_size(0) == (width, height)
    document.close()


def test_rotation_is_normalised_and_stored_in_the_pdf(tmp_path):
    document = PdfDocument.blank(pages=1, size="A4")
    document.set_page_rotation(0, 450)             # 450 = 90
    assert document.page_rotation(0) == 90

    target = tmp_path / "girado.pdf"
    document.save_as(str(target))
    document.close()

    stored = PdfDocument.open(str(target))
    assert stored.page_rotation(0) == 90
    stored.close()


def test_bookmarks_survive_saving(tmp_path):
    document = PdfDocument.blank(pages=3, size="A4")
    assert document.bookmarks() == []

    document.set_bookmarks([("Resumen", 0), ("Anexo", 2)])
    assert document.bookmarks() == [("Resumen", 0), ("Anexo", 2)]

    target = tmp_path / "marcadores.pdf"
    document.save_as(str(target))
    document.close()

    stored = PdfDocument.open(str(target))
    assert stored.bookmarks() == [("Resumen", 0), ("Anexo", 2)]
    stored.close()

    # y cualquier lector los ve, porque son el indice estandar del PDF
    crudo = pymupdf.open(str(target))
    assert len(crudo.get_toc()) == 2
    crudo.close()


def test_a_bookmark_to_a_missing_page_is_not_saved():
    document = PdfDocument.blank(pages=2, size="A4")
    document.set_bookmarks([("Bueno", 0), ("Imposible", 99)])
    assert document.bookmarks() == [("Bueno", 0)]
    document.close()


def test_take_notes_removes_the_notes_only_once(tmp_path):
    from easypdf.annotations import apply_annotations
    from easypdf.model import Annotation, Kind

    crudo = pymupdf.open()
    crudo.new_page()
    apply_annotations(crudo, [
        Annotation(kind=Kind.NOTE, page=0, rect=(100, 100, 120, 120), text="Ojo aqui"),
    ])
    source = tmp_path / "con_nota.pdf"
    crudo.save(str(source))
    crudo.close()

    document = PdfDocument.open(str(source))
    notes = document.take_notes()
    assert len(notes) == 1
    page_item, x, y, text = notes[0]
    assert (page_item, text) == (0, "Ojo aqui")
    assert (round(x), round(y)) == (100, 100)

    # ya no quedan en el documento: las lleva EasyPDF, y si no se duplicarian
    assert document.take_notes() == []
    document.close()
