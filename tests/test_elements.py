"""Piezas para montar formularios.

Nada de esto necesita interfaz: son anotaciones normales colocadas unas
respecto a otras.
"""

from __future__ import annotations

import pytest

from easypdf.elements import CATEGORIES, ELEMENTS, build, element_infos, size_of
from easypdf.i18n import language, set_language
from easypdf.model import Kind


@pytest.fixture(autouse=True)
def known_language():
    """Las pruebas no dependen del idioma del sistema."""
    previous = language()
    set_language("en")
    yield
    set_language(previous)


def test_every_piece_builds():
    for key in ELEMENTS:
        pieces = build(key, 100.0, 200.0)
        assert pieces, f"{key} no ha creado nada"
        for ann in pieces:
            assert isinstance(ann.kind, Kind)
            assert not ann.is_empty(), f"{key} ha creado una anotacion vacia"


def test_every_piece_starts_where_it_is_told():
    """Se insertan en el sitio que elija el usuario, no en una esquina fija."""
    for key in ELEMENTS:
        pieces = build(key, 100.0, 200.0)
        x0 = min(min(a.bounds()[0], a.bounds()[2]) for a in pieces)
        y0 = min(min(a.bounds()[1], a.bounds()[3]) for a in pieces)
        assert x0 == pytest.approx(100.0), key
        assert y0 == pytest.approx(200.0), key


def test_an_unknown_piece_complains():
    with pytest.raises(KeyError):
        build("no-existe", 0.0, 0.0)


def test_the_catalogue_is_grouped_and_translated():
    infos = element_infos()
    assert len(infos) == len(ELEMENTS)
    assert {i.category for i in infos} <= set(CATEGORIES)
    for info in infos:
        assert info.name and not info.name.startswith("el_"), info.key


def test_the_names_change_with_the_language():
    en = {i.key: i.name for i in element_infos()}
    set_language("es")
    es = {i.key: i.name for i in element_infos()}
    assert en["checkbox"] != es["checkbox"]
    assert es["signature"] == "Linea de firma"


def test_the_content_follows_the_active_language_too():
    """Lo que se escribe en el documento, no solo el nombre de la pieza."""
    textos_en = [a.text for a in build("place_date", 0, 0) if a.kind is Kind.TEXT]
    set_language("es")
    textos_es = [a.text for a in build("place_date", 0, 0) if a.kind is Kind.TEXT]
    assert "Place:" in textos_en and "Date:" in textos_en
    assert "Lugar:" in textos_es or "Fecha:" in textos_es


def test_the_tick_box_is_a_square_with_its_label():
    pieces = build("checkbox", 0.0, 0.0)
    box = next(a for a in pieces if a.kind is Kind.RECT)
    x0, y0, x1, y1 = box.rect
    assert (x1 - x0) == pytest.approx(y1 - y0), "la casilla tiene que ser cuadrada"
    assert any(a.kind is Kind.TEXT and a.text for a in pieces)


def test_the_tick_box_list_has_four():
    pieces = build("checklist", 0.0, 0.0)
    assert sum(1 for a in pieces if a.kind is Kind.RECT) == 4
    labels = [a.text for a in pieces if a.kind is Kind.TEXT]
    assert len(labels) == 4 and len(set(labels)) == 4   # numeradas, no repetidas


def test_the_table_comes_with_headers_and_empty_rows():
    tabla = build("table", 0.0, 0.0)[0]
    assert tabla.kind is Kind.TABLE
    assert (tabla.rows, tabla.cols) == (4, 3)
    assert all(tabla.cells[:3]), "la primera fila son las cabeceras"
    assert not any(tabla.cells[3:]), "el resto se rellena a mano"


def test_the_requested_width_is_honoured():
    estrecha = build("text_field", 0.0, 0.0, width=120.0)
    ancha = build("text_field", 0.0, 0.0, width=400.0)
    assert size_of("text_field")[0] > 0
    assert max(a.bounds()[2] for a in estrecha) == pytest.approx(120.0)
    assert max(a.bounds()[2] for a in ancha) == pytest.approx(400.0)


def test_a_ridiculous_width_does_not_break_the_piece():
    pieces = build("yes_no", 0.0, 0.0, width=1.0)
    assert pieces
    assert all(a.bounds()[2] >= a.bounds()[0] for a in pieces)
