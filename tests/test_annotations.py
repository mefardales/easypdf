"""Tests of the model -> PDF annotation translation."""

import pymupdf
import pytest

from easypdf.annotations import AUTHOR, apply_annotations, font_code
from easypdf.model import Align, Annotation, Font, Kind


@pytest.fixture()
def document():
    """A one page document.

    The reference to the page is kept: if PyMuPDF frees it, the annotations
    created stop being tied to it.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    yield doc, page
    doc.close()


@pytest.mark.parametrize(
    "ann, expected",
    [
        (Annotation(kind=Kind.RECT, page=0, rect=(50, 50, 200, 150)), "Square"),
        (Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(50, 50, 200, 80)), "Highlight"),
        (Annotation(kind=Kind.LINE, page=0, p1=(50, 50), p2=(200, 150)), "Line"),
        (Annotation(kind=Kind.TEXT, page=0, rect=(50, 50, 250, 110), text="hola"), "FreeText"),
        (Annotation(kind=Kind.INK, page=0, strokes=[[(10, 10), (60, 60), (90, 20)]]), "Ink"),
    ],
)
def test_every_kind_produces_its_annotation(document, ann, expected):
    doc, page = document
    assert apply_annotations(doc, [ann]) == 1
    created = list(page.annots())
    assert [a.type[1] for a in created] == [expected]
    assert created[0].info.get("title") == AUTHOR


def test_colours_and_opacity(document):
    doc, page = document
    ann = Annotation(
        kind=Kind.RECT, page=0, rect=(50, 50, 200, 150),
        color=(1.0, 0.0, 0.0), fill=(0.0, 0.0, 1.0), opacity=0.5, width=3.0,
    )
    apply_annotations(doc, [ann])
    annot = list(page.annots())[0]
    assert annot.colors["stroke"] == [1.0, 0.0, 0.0]
    assert annot.colors["fill"] == [0.0, 0.0, 1.0]
    assert annot.opacity == pytest.approx(0.5, abs=0.01)
    assert annot.border["width"] == pytest.approx(3.0)


def test_empty_ones_and_missing_pages_are_ignored(document):
    doc, _page = document
    annotations = [
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)),   # too small
        Annotation(kind=Kind.RECT, page=7, rect=(10, 10, 90, 90)),   # no such page
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90)),   # valid
    ]
    assert apply_annotations(doc, annotations) == 1


def test_a_rotated_page_keeps_the_position(document):
    """What is drawn on a rotated page is stored where the user sees it."""
    doc, page = document
    page.set_rotation(90)
    seen_rect = (100, 50, 300, 150)
    apply_annotations(
        doc,
        [Annotation(kind=Kind.RECT, page=0, rect=seen_rect, color=(1.0, 0.0, 0.0), width=4.0)],
    )
    assert len(list(page.annots())) == 1
    # The render is what the user sees: the red stroke lands on the edge asked for.
    pix = page.get_pixmap(annots=True)
    x, y = int(seen_rect[0]) + 2, int(seen_rect[1]) + 1
    offset = y * pix.stride + x * pix.n
    rojo, verde, azul = pix.samples[offset], pix.samples[offset + 1], pix.samples[offset + 2]
    assert rojo > 180 and verde < 90 and azul < 90


def test_an_unknown_kind_fails(document):
    doc, _page = document
    ann = Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90))
    ann.kind = "inventado"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        apply_annotations(doc, [ann])


def test_the_arrow_carries_its_own_head(document):
    """The head is a triangle of our own: the PDF standard one comes out huge."""
    doc, page = document
    ann = Annotation(kind=Kind.ARROW, page=0, p1=(50, 50), p2=(250, 50), width=4.0)
    apply_annotations(doc, [ann])
    tipos = [a.type[1] for a in page.annots()]
    assert tipos == ["Line", "Polygon"]

    from easypdf.model import arrow_head

    _base, tip, left, right = arrow_head(ann.p1, ann.p2, ann.width)
    length = tip[0] - _base[0]
    width = right[1] - left[1]
    # at width 4 the PDF's standard head would be some 40 pt long
    assert 15 < length < 25
    assert abs(width) == pytest.approx(length, rel=0.1)
    polygon = list(page.annots())[1]
    assert polygon.colors["fill"] == [pytest.approx(c) for c in ann.color]


def test_the_table_is_stored_as_a_grid_plus_texts(document):
    doc, page = document
    table = Annotation(
        kind=Kind.TABLE, page=0, rect=(40, 40, 340, 160), rows=2, cols=3,
        cells=["Item", "Quantity", "Amount", "Shirts", "12", ""],
        font_size=10,
    )
    apply_annotations(doc, [table])
    annotations = list(page.annots())
    kinds = [a.type[1] for a in annotations]
    # one ink with the whole grid, and one text per cell that has content
    assert kinds[0] == "Ink"
    assert kinds.count("FreeText") == 5
    contents = [a.info.get("content", "") for a in annotations if a.type[1] == "FreeText"]
    assert "Item" in contents and "12" in contents


def test_a_filled_table_gets_a_background(document):
    doc, page = document
    apply_annotations(doc, [Annotation(
        kind=Kind.TABLE, page=0, rect=(40, 40, 200, 100), rows=1, cols=1,
        fill=(0.9, 0.9, 1.0),
    )])
    assert [a.type[1] for a in page.annots()] == ["Square", "Ink"]


@pytest.mark.parametrize(
    "family, bold_flag, italic_flag, expected",
    [
        (Font.SANS, False, False, "helv"),
        (Font.SANS, True, False, "hebo"),
        (Font.SERIF, False, True, "tiit"),
        (Font.MONO, True, True, "cobi"),
    ],
)
def test_font_code(family, bold_flag, italic_flag, expected):
    ann = Annotation(kind=Kind.TEXT, page=0, font=family, bold=bold_flag, italic=italic_flag)
    assert font_code(ann) == expected


def test_bold_and_italic_reach_the_pdf():
    """PyMuPDF ignores the variants in plain text: rich text has to be used."""

    def ink(**style):
        doc = pymupdf.open()
        page = doc.new_page(width=340, height=80)
        apply_annotations(doc, [Annotation(
            kind=Kind.TEXT, page=0, rect=(20, 20, 320, 70), text="Hamburguesa 123",
            font_size=18, color=(0, 0, 0), width=0, **style,
        )])
        pix = page.get_pixmap(annots=True)
        oscuros = sum(
            1 for i in range(0, len(pix.samples) - 3, pix.n) if pix.samples[i] < 128
        )
        doc.close()
        return oscuros

    normal = ink()
    assert normal > 0
    assert ink(bold=True) > normal * 1.15
    assert ink(font=Font.MONO) != normal


def test_alignment_is_stored(document):
    doc, page = document
    apply_annotations(doc, [Annotation(
        kind=Kind.TEXT, page=0, rect=(20, 20, 300, 60), text="hola",
        align=Align.RIGHT, font_size=12,
    )])
    annot = list(page.annots())[0]
    assert annot.info.get("content") == "hola"


def test_the_image_is_embedded_in_the_page(document, sample_image_bytes):
    doc, page = document
    assert not page.get_images()
    apply_annotations(doc, [Annotation(
        kind=Kind.IMAGE, page=0, rect=(50, 50, 250, 170),
        image_data=sample_image_bytes, image_name="logo.png",
    )])
    images = page.get_images()
    assert len(images) == 1
    # the image is not an annotation: it is drawn on the page and always prints
    assert list(page.annots()) == []


def test_an_image_without_data_is_ignored(document):
    doc, _page = document
    ann = Annotation(kind=Kind.IMAGE, page=0, rect=(50, 50, 250, 170))
    assert ann.is_empty()
    assert apply_annotations(doc, [ann]) == 0


# -- the eraser really erases --------------------------------------------
def test_the_eraser_removes_the_text_from_the_file_not_just_covers_it():
    """Painting white is not enough: covered text could still be copied.

    Anyone rubbing a confidential figure out of a PDF believes it is gone; if
    all that sits on top is paint, anybody can select it and read it.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 120), "SALARIO: 45.000 EUR", fontsize=18)
    page.insert_text((72, 300), "Esto se queda", fontsize=18)
    data = doc.tobytes()
    doc.close()

    doc = pymupdf.open("pdf", data)
    eraser = Annotation(kind=Kind.ERASE, page=0, color=(1.0, 1.0, 1.0), width=30.0,
                      strokes=[[(60.0, 112.0), (330.0, 112.0)]])
    apply_annotations(doc, [eraser])
    output = doc.tobytes(garbage=3, deflate=True)
    doc.close()

    read_flag = pymupdf.open("pdf", output)
    text = read_flag[0].get_text()
    read_flag.close()
    assert "SALARIO" not in text
    assert "Esto se queda" in text


def test_the_eraser_stroke_is_not_written_as_a_drawing():
    """The eraser does its job by removing; it is not stored as a white line."""
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 120), "algo", fontsize=14)
    data = doc.tobytes()
    doc.close()

    doc = pymupdf.open("pdf", data)
    eraser = Annotation(kind=Kind.ERASE, page=0, color=(1.0, 1.0, 1.0), width=20.0,
                      strokes=[[(60.0, 115.0), (200.0, 115.0)]])
    escritas = apply_annotations(doc, [eraser])
    assert escritas == 0
    assert not list(doc[0].annots())
    doc.close()


def test_what_is_drawn_after_erasing_survives():
    """Erasing comes first and drawing after: otherwise the eraser would take it."""
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 120), "fuera", fontsize=14)
    data = doc.tobytes()
    doc.close()

    doc = pymupdf.open("pdf", data)
    eraser = Annotation(kind=Kind.ERASE, page=0, color=(1.0, 1.0, 1.0), width=30.0,
                      strokes=[[(60.0, 115.0), (240.0, 115.0)]])
    box = Annotation(kind=Kind.RECT, page=0, rect=(60.0, 100.0, 240.0, 140.0))
    assert apply_annotations(doc, [eraser, box]) == 1
    assert len(list(doc[0].annots())) == 1        # the box, on top of what was erased
    doc.close()


def test_an_empty_eraser_touches_nothing():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 120), "intacto", fontsize=14)
    eraser = Annotation(kind=Kind.ERASE, page=0, strokes=[])
    apply_annotations(doc, [eraser])
    assert "intacto" in doc[0].get_text()
    doc.close()
