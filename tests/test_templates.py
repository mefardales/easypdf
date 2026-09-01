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
def annotations(sample_image_bytes):
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


def test_ida_y_vuelta_de_cada_tipo(annotations):
    for original in annotations:
        copia = annotation_from_dict(annotation_to_dict(original))
        assert copia.kind is original.kind
        assert copia.page == original.page
        assert copia.rect == pytest.approx(original.rect)
        assert copia.strokes == original.strokes
        assert copia.cells == original.cells
        assert copia.image_data == original.image_data
        assert copia.bold == original.bold and copia.align == original.align


def test_guardar_y_cargar(tmp_path, annotations):
    path = save_template(str(tmp_path), "Factura mensual", annotations, [(595, 842), (595, 842)])
    assert path.endswith(EXTENSION)
    name, page_items, cargadas = load_template(path)
    assert name == "Factura mensual"
    assert page_items == [(595.0, 842.0), (595.0, 842.0)]
    assert [a.kind for a in cargadas] == [a.kind for a in annotations]
    image = [a for a in cargadas if a.kind is Kind.IMAGE][0]
    assert image.image_data == annotations[2].image_data


def test_listar_y_borrar(tmp_path, annotations):
    save_template(str(tmp_path), "Uno", annotations[:1])
    save_template(str(tmp_path), "Dos", annotations)
    listadas = list_templates(str(tmp_path))
    assert [t.name for t in listadas] == ["Dos", "Uno"]
    assert listadas[0].annotations == len(annotations)
    delete_template(listadas[0].path)
    assert [t.name for t in list_templates(str(tmp_path))] == ["Uno"]


def test_las_anotaciones_vacias_no_se_guardan(tmp_path):
    path = save_template(str(tmp_path), "Casi vacia", [
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)),   # diminuta
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90)),   # valida
    ])
    assert len(json.loads(open(path, encoding="utf-8").read())["annotations"]) == 1


def test_un_archivo_roto_no_rompe_la_lista(tmp_path, annotations):
    save_template(str(tmp_path), "Buena", annotations)
    (tmp_path / ("rota" + EXTENSION)).write_text("{esto no es json", encoding="utf-8")
    assert [t.name for t in list_templates(str(tmp_path))] == ["Buena"]
    with pytest.raises(TemplateError):
        load_template(str(tmp_path / ("rota" + EXTENSION)))


def test_nombre_de_archivo_seguro():
    assert safe_filename("Factura / ACME: 2026") == "Factura ACME 2026"
    assert safe_filename("   ") == "plantilla"


def test_aplicar_desde_una_pagina_concreta(annotations):
    movidas = shift_to_page(annotations, first_page=2, page_count=5)
    assert [a.page for a in movidas] == [2, 2, 3, 3]
    # no se sale del documento
    assert [a.page for a in shift_to_page(annotations, 4, 5)] == [4, 4, 4, 4]
    # y son copias: la plantilla original no se toca
    assert annotations[0].page == 0
    assert movidas[0].id != annotations[0].id


def test_sin_nombre_no_se_guarda(tmp_path, annotations):
    with pytest.raises(TemplateError):
        save_template(str(tmp_path), "   ", annotations)


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

    path = tmp_path / ("Antigua" + EXTENSION)
    path.write_text(json.dumps({
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
    name, page_items, annotations = load_builtin(informe.name)
    assert name == informe.name
    assert page_items == [(595.0, 842.0)]
    assert any(a.kind is Kind.TEXT for a in annotations)


def test_cargar_una_de_serie_da_copias_independientes():
    """Usarla dos veces no puede compartir las mismas anotaciones."""
    from easypdf.templates import builtin_infos, load_builtin

    alguna = builtin_infos()[1].name
    _n1, _p1, unas = load_builtin(alguna)
    _n2, _p2, others = load_builtin(alguna)
    unas[0].text = "cambiado"
    assert others[0].text != "cambiado"


def test_pedir_una_de_serie_que_no_existe_avisa():
    from easypdf.templates import TemplateError, load_builtin

    with pytest.raises(TemplateError):
        load_builtin("no existe")


# -- portapapeles ---------------------------------------------------------
def test_lo_copiado_va_y_vuelve_igual():
    from easypdf.ui.clipboard import decode, encode

    originales = [
        Annotation(kind=Kind.RECT, page=1, rect=(10.0, 20.0, 30.0, 40.0), width=3.0),
        Annotation(kind=Kind.TABLE, page=0, rows=2, cols=2,
                   cells=["a", "b", "c", "d"], font_size=9.0),
    ]
    vueltas = decode(encode(originales))
    assert [a.kind for a in vueltas] == [Kind.RECT, Kind.TABLE]
    assert vueltas[0].rect == (10.0, 20.0, 30.0, 40.0)
    assert vueltas[0].width == 3.0
    assert vueltas[1].cells == ["a", "b", "c", "d"]


def test_un_texto_de_otro_programa_no_se_lee_como_anotaciones():
    from easypdf.ui.clipboard import decode

    assert decode("una nota cualquiera") == []
    assert decode("") == []
    assert decode('{"otra": "cosa"}') == []
    assert decode('[1, 2, 3]') == []


def test_una_anotacion_rota_no_tira_las_demas():
    """Si una entrada esta mal, se salta y se pegan las que si valen."""
    import json

    from easypdf.ui.clipboard import decode, encode

    data = json.loads(encode([Annotation(kind=Kind.RECT, page=0)]))
    data["annotations"].insert(0, {"kind": "esto-no-existe"})
    read_ones = decode(json.dumps(data))
    assert len(read_ones) == 1
    assert read_ones[0].kind is Kind.RECT


def test_copiar_no_deja_el_programa_reventando_al_cerrarse(tmp_path):
    """Un QMimeData creado en Python se lo quedan Qt y Python a la vez.

    Los dos lo borran, y el programa se caia con un fallo de segmentacion al
    cerrarse en cuanto se hubiera copiado algo. No se puede comprobar dentro
    de este proceso: hay que abrir uno aparte y mirar como termina.
    """
    import os
    import subprocess
    import sys
    import textwrap

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    guion = tmp_path / "copiar.py"
    guion.write_text(textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {os.path.join(root, "src")!r})
        from PySide6.QtWidgets import QApplication
        app = QApplication([])
        from easypdf.model import Annotation, Kind
        from easypdf.ui.clipboard import clipboard_annotations, copy_annotations
        copy_annotations([Annotation(kind=Kind.RECT, page=0, rect=(1.0, 2.0, 3.0, 4.0))])
        assert len(clipboard_annotations()) == 1
    """))
    entorno = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    fin = subprocess.run([sys.executable, str(guion)], env=entorno,
                         capture_output=True, timeout=120)
    assert fin.returncode == 0, (
        f"el proceso termino con {fin.returncode}: {fin.stderr.decode()[-400:]}"
    )
