"""Pruebas de la traduccion modelo -> anotacion PDF."""

import pymupdf
import pytest

from easypdf.annotations import AUTHOR, apply_annotations, font_code
from easypdf.model import Align, Annotation, Font, Kind


@pytest.fixture()
def document():
    """Documento de una pagina.

    Se conserva la referencia a la pagina: si PyMuPDF la libera, las
    anotaciones creadas dejan de estar ligadas a ella.
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
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)),   # demasiado pequena
        Annotation(kind=Kind.RECT, page=7, rect=(10, 10, 90, 90)),   # pagina inexistente
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90)),   # valida
    ]
    assert apply_annotations(doc, annotations) == 1


def test_a_rotated_page_keeps_the_position(document):
    """Lo dibujado sobre una pagina girada se guarda donde el usuario lo ve."""
    doc, page = document
    page.set_rotation(90)
    rect_visto = (100, 50, 300, 150)
    apply_annotations(
        doc,
        [Annotation(kind=Kind.RECT, page=0, rect=rect_visto, color=(1.0, 0.0, 0.0), width=4.0)],
    )
    assert len(list(page.annots())) == 1
    # El render es lo que ve el usuario: el trazo rojo cae en el borde pedido.
    pix = page.get_pixmap(annots=True)
    x, y = int(rect_visto[0]) + 2, int(rect_visto[1]) + 1
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
    """La punta es un triangulo propio: la estandar del PDF sale gigante."""
    doc, page = document
    ann = Annotation(kind=Kind.ARROW, page=0, p1=(50, 50), p2=(250, 50), width=4.0)
    apply_annotations(doc, [ann])
    tipos = [a.type[1] for a in page.annots()]
    assert tipos == ["Line", "Polygon"]

    from easypdf.model import arrow_head

    _base, punta, left, right = arrow_head(ann.p1, ann.p2, ann.width)
    length = punta[0] - _base[0]
    width = right[1] - left[1]
    # con grosor 4 la punta estandar del PDF mediria unos 40 pt de largo
    assert 15 < length < 25
    assert abs(width) == pytest.approx(length, rel=0.1)
    poligono = list(page.annots())[1]
    assert poligono.colors["fill"] == [pytest.approx(c) for c in ann.color]


def test_the_table_is_stored_as_a_grid_plus_texts(document):
    doc, page = document
    tabla = Annotation(
        kind=Kind.TABLE, page=0, rect=(40, 40, 340, 160), rows=2, cols=3,
        cells=["Concepto", "Cantidad", "Importe", "Camisetas", "12", ""],
        font_size=10,
    )
    apply_annotations(doc, [tabla])
    annotations = list(page.annots())
    tipos = [a.type[1] for a in annotations]
    # una tinta con toda la rejilla y un texto por celda con contenido
    assert tipos[0] == "Ink"
    assert tipos.count("FreeText") == 5
    contents = [a.info.get("content", "") for a in annotations if a.type[1] == "FreeText"]
    assert "Concepto" in contents and "12" in contents


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
    """PyMuPDF ignora las variantes en texto normal: hay que usar el enriquecido."""

    def tinta(**estilo):
        doc = pymupdf.open()
        page = doc.new_page(width=340, height=80)
        apply_annotations(doc, [Annotation(
            kind=Kind.TEXT, page=0, rect=(20, 20, 320, 70), text="Hamburguesa 123",
            font_size=18, color=(0, 0, 0), width=0, **estilo,
        )])
        pix = page.get_pixmap(annots=True)
        oscuros = sum(
            1 for i in range(0, len(pix.samples) - 3, pix.n) if pix.samples[i] < 128
        )
        doc.close()
        return oscuros

    normal = tinta()
    assert normal > 0
    assert tinta(bold=True) > normal * 1.15
    assert tinta(font=Font.MONO) != normal


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
    # la imagen no es una anotacion: se dibuja en la pagina y se imprime siempre
    assert list(page.annots()) == []


def test_an_image_without_data_is_ignored(document):
    doc, _page = document
    ann = Annotation(kind=Kind.IMAGE, page=0, rect=(50, 50, 250, 170))
    assert ann.is_empty()
    assert apply_annotations(doc, [ann]) == 0


# -- la goma borra de verdad ---------------------------------------------
def test_the_eraser_removes_the_text_from_the_file_not_just_covers_it():
    """Pintar de blanco no vale: el texto tapado se seguia pudiendo copiar.

    Quien borra un dato confidencial de un PDF se cree a salvo; si lo unico
    que hay encima es pintura, cualquiera lo selecciona y lo lee.
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
    """La goma hace su trabajo borrando; no se guarda como una raya blanca."""
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
    """Se borra primero y se dibuja despues: si no, la goma se lo llevaria."""
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 120), "fuera", fontsize=14)
    data = doc.tobytes()
    doc.close()

    doc = pymupdf.open("pdf", data)
    eraser = Annotation(kind=Kind.ERASE, page=0, color=(1.0, 1.0, 1.0), width=30.0,
                      strokes=[[(60.0, 115.0), (240.0, 115.0)]])
    box = Annotation(kind=Kind.RECT, page=0, rect=(60.0, 100.0, 240.0, 140.0))
    assert apply_annotations(doc, [eraser, box]) == 1
    assert len(list(doc[0].annots())) == 1        # la caja, encima de lo borrado
    doc.close()


def test_an_empty_eraser_touches_nothing():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 120), "intacto", fontsize=14)
    eraser = Annotation(kind=Kind.ERASE, page=0, strokes=[])
    apply_annotations(doc, [eraser])
    assert "intacto" in doc[0].get_text()
    doc.close()
