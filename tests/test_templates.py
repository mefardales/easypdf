"""Pruebas de las plantillas reutilizables."""

import json

import pytest

from easypdf.model import Align, Annotation, Font, Kind
from easypdf.templates import (
    EXTENSION,
    TemplateError,
    annotation_from_dict,
    annotation_to_dict,
    delete_template,
    list_templates,
    load_template,
    safe_filename,
    save_template,
    shift_to_page,
)


@pytest.fixture()
def anotaciones(sample_image_bytes):
    return [
        Annotation(
            kind=Kind.TABLE, page=0, rect=(20, 20, 300, 120), rows=2, cols=2,
            cells=["Concepto", "Importe", "Gorras", "64"], bold=True,
            font=Font.SERIF, align=Align.CENTER, font_size=11,
        ),
        Annotation(kind=Kind.INK, page=0, strokes=[[(10, 10), (40, 40), (70, 20)]]),
        Annotation(
            kind=Kind.IMAGE, page=1, rect=(30, 30, 230, 150),
            image_data=sample_image_bytes, image_name="logo.png",
        ),
        Annotation(kind=Kind.ARROW, page=1, p1=(10, 10), p2=(90, 60), width=2.0),
    ]


def test_ida_y_vuelta_de_cada_tipo(anotaciones):
    for original in anotaciones:
        copia = annotation_from_dict(annotation_to_dict(original))
        assert copia.kind is original.kind
        assert copia.page == original.page
        assert copia.rect == pytest.approx(original.rect)
        assert copia.strokes == original.strokes
        assert copia.cells == original.cells
        assert copia.image_data == original.image_data
        assert copia.bold == original.bold and copia.align == original.align


def test_guardar_y_cargar(tmp_path, anotaciones):
    ruta = save_template(str(tmp_path), "Factura mensual", anotaciones, [(595, 842), (595, 842)])
    assert ruta.endswith(EXTENSION)
    nombre, paginas, cargadas = load_template(ruta)
    assert nombre == "Factura mensual"
    assert paginas == [(595.0, 842.0), (595.0, 842.0)]
    assert [a.kind for a in cargadas] == [a.kind for a in anotaciones]
    imagen = [a for a in cargadas if a.kind is Kind.IMAGE][0]
    assert imagen.image_data == anotaciones[2].image_data


def test_listar_y_borrar(tmp_path, anotaciones):
    save_template(str(tmp_path), "Uno", anotaciones[:1])
    save_template(str(tmp_path), "Dos", anotaciones)
    listadas = list_templates(str(tmp_path))
    assert [t.name for t in listadas] == ["Dos", "Uno"]
    assert listadas[0].annotations == len(anotaciones)
    delete_template(listadas[0].path)
    assert [t.name for t in list_templates(str(tmp_path))] == ["Uno"]


def test_las_anotaciones_vacias_no_se_guardan(tmp_path):
    ruta = save_template(str(tmp_path), "Casi vacia", [
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)),   # diminuta
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90)),   # valida
    ])
    assert len(json.loads(open(ruta, encoding="utf-8").read())["annotations"]) == 1


def test_un_archivo_roto_no_rompe_la_lista(tmp_path, anotaciones):
    save_template(str(tmp_path), "Buena", anotaciones)
    (tmp_path / ("rota" + EXTENSION)).write_text("{esto no es json", encoding="utf-8")
    assert [t.name for t in list_templates(str(tmp_path))] == ["Buena"]
    with pytest.raises(TemplateError):
        load_template(str(tmp_path / ("rota" + EXTENSION)))


def test_nombre_de_archivo_seguro():
    assert safe_filename("Factura / ACME: 2026") == "Factura ACME 2026"
    assert safe_filename("   ") == "plantilla"


def test_aplicar_desde_una_pagina_concreta(anotaciones):
    movidas = shift_to_page(anotaciones, first_page=2, page_count=5)
    assert [a.page for a in movidas] == [2, 2, 3, 3]
    # no se sale del documento
    assert [a.page for a in shift_to_page(anotaciones, 4, 5)] == [4, 4, 4, 4]
    # y son copias: la plantilla original no se toca
    assert anotaciones[0].page == 0
    assert movidas[0].id != anotaciones[0].id


def test_sin_nombre_no_se_guarda(tmp_path, anotaciones):
    with pytest.raises(TemplateError):
        save_template(str(tmp_path), "   ", anotaciones)


def test_lista_vacia_si_no_hay_carpeta(tmp_path):
    assert list_templates(str(tmp_path / "no-existe")) == []
