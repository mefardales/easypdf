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
def idioma_conocido():
    """Las pruebas no dependen del idioma del sistema."""
    previous = language()
    set_language("en")
    yield
    set_language(previous)


def test_todas_las_piezas_se_construyen():
    for key in ELEMENTS:
        pieces = build(key, 100.0, 200.0)
        assert pieces, f"{key} no ha creado nada"
        for ann in pieces:
            assert isinstance(ann.kind, Kind)
            assert not ann.is_empty(), f"{key} ha creado una anotacion vacia"


def test_cada_pieza_nace_donde_se_le_dice():
    """Se insertan en el sitio que elija el usuario, no en una esquina fija."""
    for key in ELEMENTS:
        pieces = build(key, 100.0, 200.0)
        x0 = min(min(a.bounds()[0], a.bounds()[2]) for a in pieces)
        y0 = min(min(a.bounds()[1], a.bounds()[3]) for a in pieces)
        assert x0 == pytest.approx(100.0), key
        assert y0 == pytest.approx(200.0), key


def test_una_pieza_desconocida_se_queja():
    with pytest.raises(KeyError):
        build("no-existe", 0.0, 0.0)


def test_el_catalogo_esta_agrupado_y_traducido():
    infos = element_infos()
    assert len(infos) == len(ELEMENTS)
    assert {i.category for i in infos} <= set(CATEGORIES)
    for info in infos:
        assert info.name and not info.name.startswith("el_"), info.key


def test_los_nombres_cambian_con_el_idioma():
    en = {i.key: i.name for i in element_infos()}
    set_language("es")
    es = {i.key: i.name for i in element_infos()}
    assert en["checkbox"] != es["checkbox"]
    assert es["signature"] == "Linea de firma"


def test_el_contenido_tambien_va_en_el_idioma_activo():
    """Lo que se escribe en el documento, no solo el nombre de la pieza."""
    textos_en = [a.text for a in build("place_date", 0, 0) if a.kind is Kind.TEXT]
    set_language("es")
    textos_es = [a.text for a in build("place_date", 0, 0) if a.kind is Kind.TEXT]
    assert "Place:" in textos_en and "Date:" in textos_en
    assert "Lugar:" in textos_es or "Fecha:" in textos_es


def test_la_casilla_es_un_cuadrado_con_su_etiqueta():
    pieces = build("checkbox", 0.0, 0.0)
    cuadro = next(a for a in pieces if a.kind is Kind.RECT)
    x0, y0, x1, y1 = cuadro.rect
    assert (x1 - x0) == pytest.approx(y1 - y0), "la casilla tiene que ser cuadrada"
    assert any(a.kind is Kind.TEXT and a.text for a in pieces)


def test_la_lista_de_casillas_lleva_cuatro():
    pieces = build("checklist", 0.0, 0.0)
    assert sum(1 for a in pieces if a.kind is Kind.RECT) == 4
    labels = [a.text for a in pieces if a.kind is Kind.TEXT]
    assert len(labels) == 4 and len(set(labels)) == 4   # numeradas, no repetidas


def test_la_tabla_trae_cabeceras_y_filas_vacias():
    tabla = build("table", 0.0, 0.0)[0]
    assert tabla.kind is Kind.TABLE
    assert (tabla.rows, tabla.cols) == (4, 3)
    assert all(tabla.cells[:3]), "la primera fila son las cabeceras"
    assert not any(tabla.cells[3:]), "el resto se rellena a mano"


def test_el_ancho_pedido_se_respeta():
    estrecha = build("text_field", 0.0, 0.0, width=120.0)
    ancha = build("text_field", 0.0, 0.0, width=400.0)
    assert size_of("text_field")[0] > 0
    assert max(a.bounds()[2] for a in estrecha) == pytest.approx(120.0)
    assert max(a.bounds()[2] for a in ancha) == pytest.approx(400.0)


def test_un_ancho_ridiculo_no_rompe_la_pieza():
    pieces = build("yes_no", 0.0, 0.0, width=1.0)
    assert pieces
    assert all(a.bounds()[2] >= a.bounds()[0] for a in pieces)
