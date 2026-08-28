"""Pruebas de la traduccion modelo -> anotacion PDF."""

import pymupdf
import pytest

from easypdf.annotations import AUTHOR, apply_annotations
from easypdf.model import Annotation, Kind


@pytest.fixture()
def documento():
    """Documento de una pagina.

    Se conserva la referencia a la pagina: si PyMuPDF la libera, las
    anotaciones creadas dejan de estar ligadas a ella.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    yield doc, page
    doc.close()


@pytest.mark.parametrize(
    "ann, esperado",
    [
        (Annotation(kind=Kind.RECT, page=0, rect=(50, 50, 200, 150)), "Square"),
        (Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(50, 50, 200, 80)), "Highlight"),
        (Annotation(kind=Kind.LINE, page=0, p1=(50, 50), p2=(200, 150)), "Line"),
        (Annotation(kind=Kind.ARROW, page=0, p1=(50, 50), p2=(200, 150)), "Line"),
        (Annotation(kind=Kind.TEXT, page=0, rect=(50, 50, 250, 110), text="hola"), "FreeText"),
        (Annotation(kind=Kind.INK, page=0, strokes=[[(10, 10), (60, 60), (90, 20)]]), "Ink"),
    ],
)
def test_cada_tipo_genera_su_anotacion(documento, ann, esperado):
    doc, page = documento
    assert apply_annotations(doc, [ann]) == 1
    creadas = list(page.annots())
    assert [a.type[1] for a in creadas] == [esperado]
    assert creadas[0].info.get("title") == AUTHOR


def test_la_flecha_lleva_punta(documento):
    doc, page = documento
    apply_annotations(doc, [Annotation(kind=Kind.ARROW, page=0, p1=(50, 50), p2=(200, 150))])
    annot = list(page.annots())[0]
    assert annot.line_ends == (pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_CLOSED_ARROW)


def test_colores_y_opacidad(documento):
    doc, page = documento
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


def test_se_ignoran_las_vacias_y_las_paginas_inexistentes(documento):
    doc, _page = documento
    anotaciones = [
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)),   # demasiado pequena
        Annotation(kind=Kind.RECT, page=7, rect=(10, 10, 90, 90)),   # pagina inexistente
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90)),   # valida
    ]
    assert apply_annotations(doc, anotaciones) == 1


def test_pagina_girada_conserva_la_posicion(documento):
    """Lo dibujado sobre una pagina girada se guarda donde el usuario lo ve."""
    doc, page = documento
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


def test_tipo_desconocido_falla(documento):
    doc, _page = documento
    ann = Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90))
    ann.kind = "inventado"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        apply_annotations(doc, [ann])
