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


# --------------------------------------------------------------------------
# Tipos y plantillas de serie
# --------------------------------------------------------------------------

def test_una_plantilla_guarda_su_tipo(tmp_path):
    from easypdf.templates import list_templates, save_template

    ann = Annotation(kind=Kind.RECT, page=0, rect=(0.0, 0.0, 50.0, 50.0), width=1)
    save_template(str(tmp_path), "Membrete", [ann], [(595.0, 842.0)],
                  category="letterhead")

    guardadas = list_templates(str(tmp_path))
    assert len(guardadas) == 1
    assert guardadas[0].category == "letterhead"
    assert guardadas[0].builtin is False


def test_un_tipo_desconocido_cae_en_otras(tmp_path):
    from easypdf.templates import DEFAULT_CATEGORY, list_templates, save_template

    ann = Annotation(kind=Kind.RECT, page=0, rect=(0.0, 0.0, 50.0, 50.0), width=1)
    save_template(str(tmp_path), "Rara", [ann], [(595.0, 842.0)], category="inventado")
    assert list_templates(str(tmp_path))[0].category == DEFAULT_CATEGORY


def test_una_plantilla_vieja_sin_tipo_se_sigue_leyendo(tmp_path):
    """Los archivos guardados antes de que existieran los tipos valen igual."""
    import json

    from easypdf.templates import EXTENSION, list_templates

    ruta = tmp_path / ("Antigua" + EXTENSION)
    ruta.write_text(json.dumps({
        "version": 1, "name": "Antigua",
        "pages": [{"width": 595.0, "height": 842.0}],
        "annotations": [],
    }), encoding="utf-8")

    guardadas = list_templates(str(tmp_path))
    assert len(guardadas) == 1
    assert guardadas[0].category == "other"


def test_las_plantillas_de_serie_estan_completas():
    from easypdf.templates import CATEGORIES, builtin_infos

    incluidas = builtin_infos()
    assert len(incluidas) >= 4
    for info in incluidas:
        assert info.builtin is True
        assert info.category in CATEGORIES
        assert info.pages >= 1
        assert info.annotations >= 1
        assert info.path.startswith("builtin:")


def test_se_puede_cargar_una_plantilla_de_serie():
    """Se busca por tipo, no por nombre: el nombre cambia con el idioma."""
    from easypdf.templates import builtin_infos, load_builtin

    informe = next(i for i in builtin_infos() if i.category == "report")
    nombre, paginas, anotaciones = load_builtin(informe.name)
    assert nombre == informe.name
    assert paginas == [(595.0, 842.0)]
    assert any(a.kind is Kind.TEXT for a in anotaciones)


def test_cargar_una_de_serie_da_copias_independientes():
    """Usarla dos veces no puede compartir las mismas anotaciones."""
    from easypdf.templates import load_builtin

    from easypdf.templates import builtin_infos

    alguna = builtin_infos()[1].name
    _n1, _p1, unas = load_builtin(alguna)
    _n2, _p2, otras = load_builtin(alguna)
    unas[0].text = "cambiado"
    assert otras[0].text != "cambiado"


def test_pedir_una_de_serie_que_no_existe_avisa():
    from easypdf.templates import TemplateError, load_builtin

    with pytest.raises(TemplateError):
        load_builtin("no existe")
