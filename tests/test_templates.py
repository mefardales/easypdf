"""Tests of the reusable templates."""

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


def test_round_trip_of_every_kind(annotations):
    for original in annotations:
        copia = annotation_from_dict(annotation_to_dict(original))
        assert copia.kind is original.kind
        assert copia.page == original.page
        assert copia.rect == pytest.approx(original.rect)
        assert copia.strokes == original.strokes
        assert copia.cells == original.cells
        assert copia.image_data == original.image_data
        assert copia.bold == original.bold and copia.align == original.align


def test_save_and_load(tmp_path, annotations):
    path = save_template(str(tmp_path), "Factura mensual", annotations, [(595, 842), (595, 842)])
    assert path.endswith(EXTENSION)
    name, page_items, loaded = load_template(path)
    assert name == "Factura mensual"
    assert page_items == [(595.0, 842.0), (595.0, 842.0)]
    assert [a.kind for a in loaded] == [a.kind for a in annotations]
    image = [a for a in loaded if a.kind is Kind.IMAGE][0]
    assert image.image_data == annotations[2].image_data


def test_list_and_delete(tmp_path, annotations):
    save_template(str(tmp_path), "Uno", annotations[:1])
    save_template(str(tmp_path), "Dos", annotations)
    listed = list_templates(str(tmp_path))
    assert [t.name for t in listed] == ["Dos", "Uno"]
    assert listed[0].annotations == len(annotations)
    delete_template(listed[0].path)
    assert [t.name for t in list_templates(str(tmp_path))] == ["Uno"]


def test_empty_annotations_are_not_saved(tmp_path):
    path = save_template(str(tmp_path), "Casi vacia", [
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)),   # diminuta
        Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 90, 90)),   # valida
    ])
    assert len(json.loads(open(path, encoding="utf-8").read())["annotations"]) == 1


def test_a_broken_file_does_not_break_the_listing(tmp_path, annotations):
    save_template(str(tmp_path), "Good", annotations)
    (tmp_path / ("broken" + EXTENSION)).write_text("{this is not json", encoding="utf-8")
    assert [t.name for t in list_templates(str(tmp_path))] == ["Good"]
    with pytest.raises(TemplateError):
        load_template(str(tmp_path / ("broken" + EXTENSION)))


def test_safe_file_name():
    assert safe_filename("Factura / ACME: 2026") == "Factura ACME 2026"
    assert safe_filename("   ") == "template"


def test_apply_starting_at_a_given_page(annotations):
    moved = shift_to_page(annotations, first_page=2, page_count=5)
    assert [a.page for a in moved] == [2, 2, 3, 3]
    # it never runs off the end of the document
    assert [a.page for a in shift_to_page(annotations, 4, 5)] == [4, 4, 4, 4]
    # and they are copies: the original template is untouched
    assert annotations[0].page == 0
    assert moved[0].id != annotations[0].id


def test_without_a_name_it_is_not_saved(tmp_path, annotations):
    with pytest.raises(TemplateError):
        save_template(str(tmp_path), "   ", annotations)


def test_empty_list_when_there_is_no_folder(tmp_path):
    assert list_templates(str(tmp_path / "no-such-folder")) == []


# --------------------------------------------------------------------------
# Tipos y plantillas de serie
# --------------------------------------------------------------------------

def test_a_template_stores_its_category(tmp_path):
    from easypdf.templates import list_templates, save_template

    ann = Annotation(kind=Kind.RECT, page=0, rect=(0.0, 0.0, 50.0, 50.0), width=1)
    save_template(str(tmp_path), "Membrete", [ann], [(595.0, 842.0)],
                  category="letterhead")

    saved_ones = list_templates(str(tmp_path))
    assert len(saved_ones) == 1
    assert saved_ones[0].category == "letterhead"
    assert saved_ones[0].builtin is False


def test_an_unknown_category_falls_into_other(tmp_path):
    from easypdf.templates import DEFAULT_CATEGORY, list_templates, save_template

    ann = Annotation(kind=Kind.RECT, page=0, rect=(0.0, 0.0, 50.0, 50.0), width=1)
    save_template(str(tmp_path), "Rara", [ann], [(595.0, 842.0)], category="inventado")
    assert list_templates(str(tmp_path))[0].category == DEFAULT_CATEGORY


def test_an_old_template_without_a_category_is_still_read(tmp_path):
    """Files saved before the categories existed still work."""
    import json

    from easypdf.templates import EXTENSION, list_templates

    path = tmp_path / ("Antigua" + EXTENSION)
    path.write_text(json.dumps({
        "version": 1, "name": "Antigua",
        "pages": [{"width": 595.0, "height": 842.0}],
        "annotations": [],
    }), encoding="utf-8")

    saved_ones = list_templates(str(tmp_path))
    assert len(saved_ones) == 1
    assert saved_ones[0].category == "other"


def test_the_builtin_templates_are_complete():
    from easypdf.templates import CATEGORIES, builtin_infos

    incluidas = builtin_infos()
    assert len(incluidas) >= 4
    for info in incluidas:
        assert info.builtin is True
        assert info.category in CATEGORIES
        assert info.pages >= 1
        assert info.annotations >= 1
        assert info.path.startswith("builtin:")


def test_a_builtin_template_can_be_loaded():
    """It is looked up by category, not by name: the name follows the language."""
    from easypdf.templates import builtin_infos, load_builtin

    report = next(i for i in builtin_infos() if i.category == "report")
    name, page_items, annotations = load_builtin(report.name)
    assert name == report.name
    assert page_items == [(595.0, 842.0)]
    assert any(a.kind is Kind.TEXT for a in annotations)


def test_loading_a_builtin_gives_independent_copies():
    """Using one twice must not share the same annotations."""
    from easypdf.templates import builtin_infos, load_builtin

    some_name = builtin_infos()[1].name
    _n1, _p1, ones = load_builtin(some_name)
    _n2, _p2, others = load_builtin(some_name)
    ones[0].text = "cambiado"
    assert others[0].text != "cambiado"


def test_asking_for_a_missing_builtin_complains():
    from easypdf.templates import TemplateError, load_builtin

    with pytest.raises(TemplateError):
        load_builtin("no such template")


# -- the clipboard --------------------------------------------------------
def test_what_is_copied_comes_back_unchanged():
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


def test_another_programs_text_is_not_read_as_annotations():
    from easypdf.ui.clipboard import decode

    assert decode("just some note") == []
    assert decode("") == []
    assert decode('{"something": "else"}') == []
    assert decode('[1, 2, 3]') == []


def test_one_broken_annotation_does_not_sink_the_rest():
    """If one entry is bad, it is skipped and the good ones are still pasted."""
    import json

    from easypdf.ui.clipboard import decode, encode

    data = json.loads(encode([Annotation(kind=Kind.RECT, page=0)]))
    data["annotations"].insert(0, {"kind": "no-such-kind"})
    read_back = decode(json.dumps(data))
    assert len(read_back) == 1
    assert read_back[0].kind is Kind.RECT


def test_copying_does_not_leave_the_program_crashing_on_exit(tmp_path):
    """A QMimeData built in Python is owned by Qt and by Python at once.

    Both free it, and the program crashed with a segmentation fault on exit as
    soon as anything had been copied. It cannot be checked inside this
    process: a separate one has to be started and its exit watched.
    """
    import os
    import subprocess
    import sys
    import textwrap

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = tmp_path / "copy_check.py"
    script.write_text(textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {os.path.join(root, "src")!r})
        from PySide6.QtWidgets import QApplication
        app = QApplication([])
        from easypdf.model import Annotation, Kind
        from easypdf.ui.clipboard import clipboard_annotations, copy_annotations
        copy_annotations([Annotation(kind=Kind.RECT, page=0, rect=(1.0, 2.0, 3.0, 4.0))])
        assert len(clipboard_annotations()) == 1
    """))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, str(script)], env=env,
                            capture_output=True, timeout=120)
    assert result.returncode == 0, (
        f"the process exited with {result.returncode}: {result.stderr.decode()[-400:]}"
    )
