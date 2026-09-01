"""Pruebas de la interfaz (se ejecutan con la plataforma Qt 'offscreen')."""

import pymupdf
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from easypdf import __app_name__  # noqa: E402
from easypdf.i18n import set_language, tr  # noqa: E402
from easypdf.model import (
    Align,  # noqa: E402
    Annotation,  # noqa: E402
    Kind,  # noqa: E402
)
from easypdf.ui.items import RectItem, TextItem, create_item, qcolor, to_rgb  # noqa: E402
from easypdf.ui.main_window import MainWindow  # noqa: E402
from easypdf.ui.page_view import Tool  # noqa: E402


@pytest.fixture()
def window(qapp, sample_pdf):
    set_language("en")          # las pruebas no dependen del idioma del sistema
    window = MainWindow()
    window.resize(1100, 820)
    window.show()
    QTest.qWaitForWindowExposed(window)
    assert window.open_path(sample_pdf)
    qapp.processEvents()
    yield window
    window._modified = False
    window.view.undo_stack.setClean()
    window.close()


def _arrastrar(window, desde, hasta, modificador=Qt.NoModifier):
    viewport = window.view.viewport()
    QTest.mousePress(viewport, Qt.LeftButton, modificador, QPoint(*desde))
    QTest.mouseMove(viewport, QPoint(*hasta))
    QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, modificador, QPoint(*hasta))
    QApplication.processEvents()


def test_opening_a_document_sets_up_the_window(window):
    assert window.view.page_count == 3
    assert window.page_label.text() == tr("status_of", total=3)
    assert "muestra.pdf" in window.windowTitle()
    assert window.act_print.isEnabled()


def test_draw_with_every_tool(window):
    window.select_tool(Tool.RECT)
    _arrastrar(window, (150, 150), (400, 260))
    window.select_tool(Tool.LINE)
    _arrastrar(window, (150, 300), (420, 380))
    window.select_tool(Tool.ARROW)
    _arrastrar(window, (150, 420), (420, 500))
    window.select_tool(Tool.HIGHLIGHT)
    _arrastrar(window, (150, 120), (430, 145))
    tipos = [a.kind for a in window.view.annotations()]
    assert tipos == [Kind.RECT, Kind.LINE, Kind.ARROW, Kind.HIGHLIGHT]
    assert window.view.tool is Tool.SELECT  # vuelve a seleccionar al terminar


def test_freehand_accumulates_points(window):
    window.select_tool(Tool.INK)
    viewport = window.view.viewport()
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(200, 500))
    for x in range(210, 340, 10):
        QTest.mouseMove(viewport, QPoint(x, 520))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(340, 520))
    QApplication.processEvents()
    annotations = list(window.view.annotations())
    assert len(annotations) == 1
    assert len(annotations[0].strokes[0]) > 5


def test_a_text_box_keeps_what_was_typed(window, tmp_path):
    window.select_tool(Tool.TEXT)
    _arrastrar(window, (150, 600), (420, 650))
    selection = window.view.selected_items()
    assert selection and isinstance(selection[0], TextItem)
    selection[0].setPlainText("Nota de prueba")
    selection[0].stop_editing()
    QApplication.processEvents()
    target = tmp_path / "anotado.pdf"
    window.view.document.save_as(str(target), window.view.annotations())
    output = pymupdf.open(str(target))
    page_item = output[0]
    contents = [a.info.get("content", "") for a in page_item.annots()]
    assert "Nota de prueba" in contents


def test_a_click_without_dragging_makes_a_usable_text_box(window):
    window.select_tool(Tool.TEXT)
    _arrastrar(window, (200, 300), (203, 302))
    annotations = list(window.view.annotations())
    assert len(annotations) == 1
    x0, y0, x1, y1 = annotations[0].normalized_rect()
    assert x1 - x0 > 100 and y1 - y0 > 10


def test_undo_and_redo(window):
    window.select_tool(Tool.RECT)
    _arrastrar(window, (150, 150), (400, 260))
    assert window.view.annotation_count() == 1
    window.view.undo_stack.undo()
    assert window.view.annotation_count() == 0
    window.view.undo_stack.redo()
    assert window.view.annotation_count() == 1


def test_delete_selection(window):
    window.select_tool(Tool.RECT)
    _arrastrar(window, (150, 150), (400, 260))
    window.view.select_all_annotations()
    QApplication.processEvents()
    assert window.view.delete_selected()
    assert window.view.annotation_count() == 0
    window.view.undo_stack.undo()
    assert window.view.annotation_count() == 1


def test_move_and_undo_restores_the_position(window):
    window.select_tool(Tool.RECT)
    _arrastrar(window, (150, 150), (400, 260))
    item = window.view.selected_items()[0]
    inicial = item.ann.rect
    window.view._scene.begin_edit(item)
    item.moveBy(12, 20)
    item.sync_model()
    window.view._scene.end_edit(item)
    assert item.ann.rect != inicial
    window.view.undo_stack.undo()
    assert item.ann.rect == pytest.approx(inicial)


def test_change_the_style_of_the_selection(window):
    window.select_tool(Tool.RECT)
    _arrastrar(window, (150, 150), (400, 260))
    item = window.view.selected_items()[0]
    assert window.view.apply_style_to_selection(color=(0.0, 0.0, 1.0), width=4.0)
    assert item.ann.color == (0.0, 0.0, 1.0)
    assert item.ann.width == 4.0
    window.view.undo_stack.undo()
    assert item.ann.width != 4.0


def test_search_text(window):
    window.search_edit.setText("EasyPDF")
    window.run_search()
    assert window.view.hit_count == 3
    assert tr("search_of", current=1, total=3).strip() in window.search_label.text()
    window.view.next_hit()
    assert window.view.hit_index == 1
    window.view.previous_hit()
    assert window.view.hit_index == 0
    window.search_edit.setText("palabra-que-no-existe")
    window.run_search()
    assert window.view.hit_count == 0


def test_navigating_between_pages(window):
    window.view.go_to_page(2)
    QApplication.processEvents()
    assert window.view.current_page == 2
    window.view.previous_page()
    QApplication.processEvents()
    assert window.view.current_page == 1


def test_zoom(window):
    window.view.set_zoom(1.0)
    window.view.zoom_in()
    assert window.view.zoom > 1.0
    window.view.zoom_out()
    assert window.view.zoom == pytest.approx(1.0)
    window.view.fit_width()
    assert window.view.zoom > 0


def test_thumbnails(window, qapp):
    QTest.qWait(400)
    qapp.processEvents()
    assert window.thumb_list.count() == 3


def test_close_document(window):
    assert window.close_document()
    assert not window.view.has_document()
    assert window.windowTitle() == __app_name__


def test_colour_round_trip():
    from PySide6.QtGui import QColor

    color = QColor("#1565c0")
    assert to_rgb(color) == pytest.approx((0.0824, 0.396, 0.753), abs=0.01)
    assert qcolor(to_rgb(color)).name() == "#1565c0"


def test_a_box_item_syncs_the_model(qapp):
    from PySide6.QtWidgets import QGraphicsScene

    scene = QGraphicsScene()
    ann = Annotation(kind=Kind.RECT, page=0, rect=(10, 20, 110, 70))
    item = create_item(ann)
    scene.addItem(item)
    assert isinstance(item, RectItem)
    assert item.pos().x() == 10 and item.rect().width() == 100
    item.moveBy(5, 5)
    item.sync_model()
    assert ann.rect == (15, 25, 115, 75)


def test_creating_the_item_does_not_alter_the_model(qapp):
    """Regresion: setPos() disparaba itemChange y machacaba la geometria."""
    from PySide6.QtWidgets import QGraphicsScene

    scene = QGraphicsScene()
    for ann in (
        Annotation(kind=Kind.RECT, page=0, rect=(66, 320, 460, 400)),
        Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(70, 152, 470, 172)),
        Annotation(kind=Kind.TEXT, page=0, rect=(300, 240, 520, 285), text="hola"),
        Annotation(kind=Kind.LINE, page=0, p1=(10, 20), p2=(200, 240)),
        Annotation(kind=Kind.INK, page=0, strokes=[[(10, 10), (40, 60), (80, 20)]]),
    ):
        expected = ann.copy()
        item = create_item(ann)
        scene.addItem(item)
        item.apply_model()          # volver a aplicarlo tampoco puede cambiarlo
        assert ann.rect == pytest.approx(expected.rect)
        assert ann.p1 == expected.p1 and ann.p2 == expected.p2
        assert ann.strokes == expected.strokes


def test_add_annotation_is_undoable(window):
    ann = Annotation(kind=Kind.RECT, page=1, rect=(50, 60, 300, 200))
    item = window.view.add_annotation(ann)
    assert item in window.view._annotation_items()
    assert window.view.annotation_count() == 1
    window.view.undo_stack.undo()
    assert window.view.annotation_count() == 0
    assert item not in window.view._annotation_items()
    with pytest.raises(IndexError):
        window.view.add_annotation(Annotation(kind=Kind.RECT, page=99, rect=(1, 1, 50, 50)))


def test_typing_text_frees_del_and_ctrl_a(window):
    """Mientras se escribe, los atajos globales no pueden robar las teclas."""
    window.select_tool(Tool.TEXT)
    _arrastrar(window, (150, 600), (420, 650))
    item = window.view.selected_items()[0]
    assert window.view.is_editing_text
    assert not window.act_delete.isEnabled()
    assert not window.act_select_all.isEnabled()
    item.stop_editing()
    QApplication.processEvents()
    assert not window.view.is_editing_text
    assert window.act_delete.isEnabled()
    assert window.act_select_all.isEnabled()


def test_dragging_a_drawing_does_not_fling_it_off_screen(window):
    """Regresion: mover la posicion dentro de itemChange disparaba el dibujo."""
    window.select_tool(Tool.INK)
    viewport = window.view.viewport()
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(200, 300))
    for x in range(210, 360, 10):
        QTest.mouseMove(viewport, QPoint(x, 300 + (20 if (x // 10) % 2 else -20)))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(360, 300))
    QApplication.processEvents()

    item = window.view._annotation_items()[0]
    antes = item.ann.bounds()
    width = antes[2] - antes[0]

    window.select_tool(Tool.SELECT)
    item.setSelected(True)
    centro = window.view.mapFromScene(item.sceneBoundingRect().center())
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, centro)
    for step in range(1, 5):
        QTest.mouseMove(viewport, centro + QPoint(10 * step, 5 * step))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, centro + QPoint(40, 20))
    QApplication.processEvents()

    despues = item.ann.bounds()
    escala = window.view.zoom * (window.view.logicalDpiX() / 72.0)
    assert despues[0] - antes[0] == pytest.approx(40 / escala, abs=3)
    assert despues[1] - antes[1] == pytest.approx(20 / escala, abs=3)
    assert (despues[2] - despues[0]) == pytest.approx(width, abs=0.5)
    assert item.scene() is not None and item.isVisible()


def test_the_arrow_head_is_the_same_on_screen_and_in_the_pdf(qapp):
    """La punta que se dibuja y la que se guarda tienen que medir lo mismo."""
    from easypdf.model import arrow_head

    ann = Annotation(kind=Kind.ARROW, page=0, p1=(20, 20), p2=(200, 100), width=3.0)
    item = create_item(ann)
    poligono, fin = item._arrow_points()
    _base, punta, left, right = arrow_head(ann.p1, ann.p2, ann.width)
    assert (poligono[0].x(), poligono[0].y()) == pytest.approx(punta)
    assert (poligono[1].x(), poligono[1].y()) == pytest.approx(left)
    assert (poligono[2].x(), poligono[2].y()) == pytest.approx(right)
    # el trazo termina dentro de la punta, no en el vertice
    assert fin.x() < punta[0] and fin.y() < punta[1]


def test_create_a_table_and_type_in_its_cells(window, tmp_path):
    window.rows_spin.setValue(2)
    window.cols_spin.setValue(3)
    window.select_tool(Tool.TABLE)
    _arrastrar(window, (150, 200), (600, 320))

    tabla = window.view.selected_items()[0]
    assert tabla.ann.kind is Kind.TABLE
    assert tabla.ann.rows == 2 and tabla.ann.cols == 3
    assert len(tabla.local_cell_rects()) == 6
    assert tabla.is_editing  # entra directo a escribir en la primera celda

    for index, text in enumerate(["Concepto", "Cantidad", "Importe", "Gorras", "8", "64"]):
        tabla.edit_cell(index)
        tabla._editor.setPlainText(text)
    tabla.finish_editing()
    assert tabla.ann.cells[0] == "Concepto" and tabla.ann.cells[5] == "64"

    target = tmp_path / "con-tabla.pdf"
    window.view.document.save_as(str(target), window.view.annotations())
    page_item = pymupdf.open(str(target))[0]
    tipos = [a.type[1] for a in page_item.annots()]
    assert tipos.count("Ink") == 1 and tipos.count("FreeText") == 6


def test_a_tiny_table_gets_a_usable_size(window):
    window.select_tool(Tool.TABLE)
    _arrastrar(window, (200, 300), (204, 303))
    tabla = window.view.selected_items()[0]
    x0, y0, x1, y1 = tabla.ann.normalized_rect()
    assert (x1 - x0) > 100 and (y1 - y0) > 40


def test_text_styles_apply_to_the_selection(window):
    from easypdf.model import Align, Font

    window.select_tool(Tool.TEXT)
    _arrastrar(window, (150, 600), (420, 650))
    item = window.view.selected_items()[0]
    item.stop_editing()
    item.setSelected(True)

    window.font_combo.setCurrentIndex(window.font_combo.findData(Font.SERIF.value))
    window._set_bold(True)
    window._set_italic(True)
    window._set_align(Align.CENTER)

    assert item.ann.font is Font.SERIF
    assert item.ann.bold and item.ann.italic
    assert item.ann.align is Align.CENTER
    # y quedan guardados como preferencia para la siguiente anotacion
    assert window.view.style_defaults["bold"] is True


def test_closing_the_search_clears_the_highlight(window):
    window.search_edit.setText("EasyPDF")
    window.run_search()
    assert window.view.hit_count == 3
    assert window.view._search_items

    window.close_search()
    assert window.view.hit_count == 0
    assert window.view._search_items == []
    assert not window.toolbar_search.isVisible()

    # y tambien al vaciar el cuadro de busqueda
    window.search_edit.setText("EasyPDF")
    window.run_search()
    assert window.view.hit_count == 3
    window.search_edit.setText("")
    assert window.view.hit_count == 0


def test_placing_an_image_by_dropping_it_on_the_document(window, sample_image, tmp_path):
    assert window.insert_image_from_file(sample_image)
    image = window.view._annotation_items()[0]
    assert image.ann.kind is Kind.IMAGE
    assert image.ann.image_name == "logo.png"
    x0, y0, x1, y1 = image.ann.normalized_rect()
    assert (x1 - x0) / (y1 - y0) == pytest.approx(200 / 120, rel=0.02)

    target = tmp_path / "con-imagen.pdf"
    window.view.document.save_as(str(target), window.view.annotations())
    assert len(pymupdf.open(str(target))[0].get_images()) == 1


def test_the_image_keeps_its_aspect_when_placed(window, sample_image_bytes):
    window.view.style_defaults["image"] = ("logo.png", sample_image_bytes)
    window.view.set_tool(Tool.IMAGE)
    _arrastrar(window, (200, 300), (500, 600))
    ann = window.view.annotations()[0]
    x0, y0, x1, y1 = ann.normalized_rect()
    assert (x1 - x0) / (y1 - y0) == pytest.approx(200 / 120, rel=0.02)


def test_resizing_an_image_by_the_corner_keeps_the_aspect(
    window, sample_image
):
    window.insert_image_from_file(sample_image)
    image = window.view._annotation_items()[0]
    image.setSelected(True)
    from PySide6.QtCore import QPointF

    image.resize_to("br", QPointF(300, 500))
    assert image.rect().width() / image.rect().height() == pytest.approx(
        200 / 120, rel=0.02
    )


def test_create_a_blank_document_and_add_pages(window, tmp_path):
    window._modified = False
    window.view.undo_stack.setClean()
    window.new_document()
    assert window.view.page_count == 1
    assert tr("untitled_document").split(".")[0] in window.windowTitle()

    window.view.add_annotation(
        Annotation(kind=Kind.TEXT, page=0, rect=(60, 60, 400, 110), text="Hola"),
        undoable=False,
    )
    window.add_page_end()
    window.add_page_end()
    assert window.view.page_count == 3

    window.duplicate_current_page()
    assert window.view.page_count == 4

    target = tmp_path / "nuevo.pdf"
    window.view.document.save_as(str(target), window.view.annotations())
    stored = pymupdf.open(str(target))
    assert stored.page_count == 4
    assert len(list(stored[0].annots())) == 1


def test_deleting_a_page_can_be_undone(window):
    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=1, rect=(50, 50, 200, 150)), undoable=False
    )
    assert window.view.page_count == 3
    window.view.delete_page(1)
    assert window.view.page_count == 2
    assert window.view.annotation_count() == 0     # se va con su pagina

    window.view.undo_stack.undo()
    assert window.view.page_count == 3
    assert window.view.annotation_count() == 1
    assert window.view.annotations()[0].page == 1


def test_inserting_a_page_shifts_the_annotations(window):
    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=2, rect=(50, 50, 200, 150)), undoable=False
    )
    window.view.add_page(0)
    assert window.view.annotations()[0].page == 3
    window.view.undo_stack.undo()
    assert window.view.annotations()[0].page == 2


def test_save_and_reuse_a_template(window, tmp_path, sample_image_bytes):
    folder = tmp_path / "plantillas"
    window.templates_dir = lambda: str(folder)

    window.view.add_annotation(
        Annotation(kind=Kind.TEXT, page=0, rect=(50, 40, 500, 80), text="ACME", bold=True),
        undoable=False,
    )
    window.view.add_annotation(
        Annotation(
            kind=Kind.IMAGE, page=0, rect=(400, 300, 520, 380),
            image_data=sample_image_bytes, image_name="logo.png",
        ),
        undoable=False,
    )
    from easypdf.templates import list_templates, save_template

    path = save_template(
        str(folder), "Membrete", window.view.annotations(),
        window.view.document.page_sizes(),
    )
    assert [t.name for t in list_templates(str(folder))] == ["Membrete"]

    # aplicarla sobre el documento abierto, desde la pagina actual
    window.view.go_to_page(1)
    assert window.apply_template(path)
    assert window.view.annotation_count() == 4
    assert sorted({a.page for a in window.view.annotations()}) == [0, 1]
    # y un solo Ctrl+Z deshace toda la plantilla
    window.view.undo_stack.undo()
    assert window.view.annotation_count() == 2


def test_new_document_from_a_template(window, tmp_path):
    folder = tmp_path / "plantillas"
    window.templates_dir = lambda: str(folder)
    from easypdf.templates import save_template

    path = save_template(
        str(folder),
        "Dos paginas",
        [Annotation(kind=Kind.TEXT, page=1, rect=(50, 50, 400, 90), text="Anexo")],
        [(595, 842), (842, 595)],
    )
    window._modified = False
    window.view.undo_stack.setClean()
    assert window.new_from_template(path)
    assert window.view.page_count == 2
    assert [round(v) for v in window.view.document.page_size(1)] == [842, 595]
    assert window.view.annotation_count() == 1
    assert window.view.annotations()[0].page == 1


def test_changing_the_interface_language(window):
    """La ventana se retraduce entera sin reiniciar."""
    set_language("en")
    window.retranslate()
    assert window.act_save.text() == "&Save"
    assert [a.text() for a in window.menuBar().actions()][:2] == ["&File", "&Edit"]

    window.set_language("es")
    assert window.act_save.text() == "&Guardar"
    assert [a.text() for a in window.menuBar().actions()][:2] == ["&Archivo", "&Editar"]
    assert window.tool_actions[Tool.TABLE].text() == "Ta&bla"
    assert window.language_actions["es"].isChecked()
    assert window.settings.language() == "es"

    window.set_language("en")
    assert window.act_save.text() == "&Save"
    assert window.tool_actions[Tool.TABLE].text() == "Ta&ble"


# --------------------------------------------------------------------------
# Repintado: un item que dibuja fuera de su boundingRect() deja rastro en
# pantalla al arrastrarlo, porque Qt solo repinta el area que el item declara.
# --------------------------------------------------------------------------

ANNOTATIONS_TO_REPAINT = {
    "texto": Annotation(kind=Kind.TEXT, page=0, rect=(0, 0, 180, 40), text="sdfsdfs", width=0),
    "texto_con_borde": Annotation(kind=Kind.TEXT, page=0, rect=(0, 0, 180, 40), text="hola", width=2),
    "cuadro": Annotation(kind=Kind.RECT, page=0, rect=(0, 0, 120, 80), width=3),
    "resaltado": Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(0, 0, 120, 30)),
    "linea": Annotation(kind=Kind.LINE, page=0, p1=(0, 0), p2=(120, 60), width=3),
    "flecha": Annotation(kind=Kind.ARROW, page=0, p1=(0, 0), p2=(120, 60), width=3),
    "dibujo": Annotation(kind=Kind.INK, page=0, strokes=[[(0, 0), (40, 50), (90, 10)]], width=3),
    "tabla": Annotation(
        kind=Kind.TABLE, page=0, rect=(0, 0, 180, 90), rows=2, cols=3,
        cells=["a", "b", "c", "d", "e", "f"],
    ),
}


@pytest.mark.parametrize("name", sorted(ANNOTATIONS_TO_REPAINT))
def test_the_item_paints_nothing_outside_its_bounding_rect(qapp, name):
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem

    background = qcolor((1.0, 1.0, 1.0))
    margin = 40                       # cuanto se mira alrededor del boundingRect

    scene = QGraphicsScene()
    item = create_item(ANNOTATIONS_TO_REPAINT[name].copy())
    scene.addItem(item)
    item.setSelected(True)            # peor caso: borde de seleccion y tiradores

    limits = item.boundingRect()
    zona = limits.adjusted(-margin, -margin, margin, margin)
    image = QImage(int(zona.width()), int(zona.height()), QImage.Format_RGB888)
    image.fill(background)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.translate(-zona.left(), -zona.top())
    item.paint(painter, QStyleOptionGraphicsItem(), None)
    painter.end()

    x0 = limits.left() - zona.left()
    y0 = limits.top() - zona.top()
    x1, y1 = x0 + limits.width(), y0 + limits.height()
    outside = sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if not ((x0 - 1) <= x <= (x1 + 1) and (y0 - 1) <= y <= (y1 + 1))
        and image.pixelColor(x, y) != background
    )
    assert outside == 0, f"{name} pinta {outside} pixeles fuera de su boundingRect()"


# --------------------------------------------------------------------------
# Panel de miniaturas: reordenar arrastrando y menu contextual
# --------------------------------------------------------------------------

def _primera_linea(window, page_item):
    """Primera linea de texto de una pagina ('' si esta en blanco)."""
    lines = window.view.document.page_text(page_item).strip().splitlines()
    return lines[0] if lines else ""


def test_dragging_a_thumbnail_reorders_the_document(window, qapp):
    assert window.view.page_count >= 3   # el PDF de prueba ya trae varias
    antes = [_primera_linea(window, i) for i in range(window.view.page_count)]

    window._on_thumbnail_dropped(0, 2)
    qapp.processEvents()
    despues = [_primera_linea(window, i) for i in range(window.view.page_count)]

    assert despues[2] == antes[0]
    assert sorted(despues) == sorted(antes)          # no se pierde ninguna
    assert window.view.current_page == 2

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert [_primera_linea(window, i) for i in range(window.view.page_count)] == antes


def test_a_thumbnails_menu_offers_every_operation(window):
    _menu, actions = window.build_page_menu(0)
    valores = set(actions.values())
    # las de insertar llevan el tamano detras ("insert_after:A4"), asi que se
    # comparan por el prefijo
    familias = {v.split(":", 1)[0] for v in valores}
    assert familias == {
        "insert_before", "insert_after", "duplicate",
        "rotate_left", "rotate_right", "rotate_180",
        "up", "down", "delete",
    }


def test_insert_and_duplicate_from_the_thumbnail_menu(window, qapp):
    total = window.view.page_count

    window.run_page_action("insert_after", 0)
    qapp.processEvents()
    assert window.view.page_count == total + 1
    window.view.undo_stack.undo()
    qapp.processEvents()
    assert window.view.page_count == total

    window.run_page_action("duplicate", 0)
    qapp.processEvents()
    assert window.view.page_count == total + 1
    assert _primera_linea(window, 1) == _primera_linea(window, 0)
    window.view.undo_stack.undo()
    qapp.processEvents()
    assert window.view.page_count == total


def test_rotating_the_page_carries_the_annotations_along(window, qapp):
    width, height = window.view.document.page_size(0)
    ann = Annotation(kind=Kind.RECT, page=0, rect=(50.0, 100.0, 150.0, 200.0), width=2)
    window.view.add_annotation(ann)
    qapp.processEvents()

    window.run_page_action("rotate_right", 0)
    qapp.processEvents()
    assert window.view.document.page_rotation(0) == 90
    assert window.view.document.page_size(0) == (height, width)
    # la anotacion se ha movido, y sigue dentro de la pagina ya girada
    assert ann.rect != (50.0, 100.0, 150.0, 200.0)
    assert 0 <= ann.rect[0] and ann.rect[2] <= height
    assert 0 <= ann.rect[1] and ann.rect[3] <= width

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert window.view.document.page_rotation(0) == 0
    assert window.view.document.page_size(0) == (width, height)
    assert ann.rect == (50.0, 100.0, 150.0, 200.0)


def test_rotating_180_keeps_the_page_size(window, qapp):
    size = window.view.document.page_size(0)
    window.run_page_action("rotate_180", 0)
    qapp.processEvents()
    assert window.view.document.page_rotation(0) == 180
    assert window.view.document.page_size(0) == size


def test_inserting_a_page_lets_you_choose_the_size(window, qapp):
    _menu, actions = window.build_page_menu(0)
    options = {v for v in actions.values() if v.startswith("insert_")}
    # "igual que esta pagina" mas cada tamano, por delante y por detras
    assert "insert_after:" in options
    assert "insert_after:A4" in options
    assert "insert_before:Letter" in options

    total = window.view.page_count
    window.run_page_action("insert_after:Letter", 0)
    qapp.processEvents()
    assert window.view.page_count == total + 1
    assert window.view.document.page_size(1) == (612.0, 792.0)

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert window.view.page_count == total


def test_inserting_without_a_size_copies_the_neighbouring_page(window, qapp):
    window.run_page_action("insert_before:", 0)
    qapp.processEvents()
    assert window.view.document.page_size(0) == window.view.document.page_size(1)


def test_page_sizes_are_translated(window):
    from easypdf.i18n import page_size_label

    set_language("en")
    assert page_size_label("Letter") == "Letter"
    assert page_size_label("Legal") == "Legal"
    set_language("es")
    assert page_size_label("Letter") == "Carta"
    assert page_size_label("Legal") == "Oficio"
    # un nombre desconocido se deja tal cual
    assert page_size_label("Cuartilla") == "Cuartilla"
    set_language("en")


def test_dropping_where_qt_sees_no_thumbnail_does_not_send_the_page_to_the_end(window, qapp):
    """El fallo original: si indexAt() no devolvia nada, drop_row daba la
    ultima posicion y la pagina se iba al final de todas.

    No se usan las medidas de los elementos, que cambian de un sistema a
    otro: se toma un punto claramente por encima de la primera miniatura,
    donde ninguna plataforma ve nada.
    """
    from PySide6.QtCore import QPoint

    items = window.thumb_list
    assert items.count() >= 3
    last_tick = items.count() - 1

    r0 = items.visualRect(items.model().index(0, 0))
    encima = QPoint(r0.center().x(), max(0, r0.top() - 40))
    assert not items.indexAt(encima).isValid()     # aqui no hay ninguna

    target = items.drop_row(encima)
    assert target == 0, f"por encima de la primera deberia dar 0, dio {target}"
    assert target != last_tick


def test_the_nearest_thumbnail_is_found_by_geometry(window):
    """La parte que arregla el fallo, sin depender de donde caiga el raton."""
    from PySide6.QtCore import QPoint

    items = window.thumb_list
    r0 = items.visualRect(items.model().index(0, 0))
    r1 = items.visualRect(items.model().index(1, 0))

    assert items.nearest_row(QPoint(r0.center().x(), r0.top() - 50)) == 0
    assert items.nearest_row(r0.center()) == 0
    assert items.nearest_row(r1.center()) == 1


def test_the_drop_target_never_goes_backwards_as_the_mouse_descends(window):
    """Bajar el raton solo puede dar una posicion igual o mayor."""
    from PySide6.QtCore import QPoint

    items = window.thumb_list
    r0 = items.visualRect(items.model().index(0, 0))
    r1 = items.visualRect(items.model().index(1, 0))
    x = r0.center().x()

    previous = None
    for y in range(max(0, r0.top() - 4), r1.bottom() + 1, 3):
        target = items.drop_row(QPoint(x, y))
        if previous is not None:
            assert target >= previous, f"en y={y} bajo de {previous} a {target}"
        previous = target


def test_dropping_on_a_thumbnail_gives_its_slot_or_the_next(window):
    items = window.thumb_list
    for row in range(min(3, items.count())):
        centro = items.visualRect(items.model().index(row, 0)).center()
        assert items.drop_row(centro) in (row, row + 1)


# --------------------------------------------------------------------------
# Goma
# --------------------------------------------------------------------------

def test_ctrl_plus_and_minus_resize_the_eraser_when_active(window):
    from easypdf.model import ERASER_SIZES

    window.select_tool(Tool.ERASER)
    inicial = window.view.eraser_size
    zoom = window.view.zoom

    window.zoom_or_eraser(1)
    assert window.view.eraser_size > inicial
    assert window.view.zoom == zoom          # el zoom no se toca

    window.zoom_or_eraser(-1)
    assert window.view.eraser_size == inicial

    for _ in range(20):
        window.zoom_or_eraser(1)
    assert window.view.eraser_size == ERASER_SIZES[-1]
    for _ in range(20):
        window.zoom_or_eraser(-1)
    assert window.view.eraser_size == ERASER_SIZES[0]


def test_with_another_tool_ctrl_plus_is_zoom_again(window):
    window.select_tool(Tool.SELECT)
    zoom, eraser = window.view.zoom, window.view.eraser_size
    window.zoom_or_eraser(1)
    assert window.view.zoom > zoom
    assert window.view.eraser_size == eraser


def _pasar_la_goma(window, points, page_item=0):
    """Simula una pasada de goma completa, con su paso de deshacer."""
    from PySide6.QtCore import QPointF

    from easypdf.ui.items import create_item

    view = window.view
    ann = Annotation(
        kind=Kind.ERASE, page=page_item, color=tuple(view.eraser_color),
        width=view.eraser_size, opacity=1.0,
    )
    view._erase_item = create_item(ann, view._page_items[page_item])
    view._erasing = True
    for x, y in points:
        view.erase_at(page_item, QPointF(x, y))
    view._finish_erase()
    return ann


def test_the_eraser_takes_away_what_is_underneath(window, qapp):
    """Borra de verdad: lo que pisa desaparece, lo de al lado se queda."""
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0), width=2)
    far = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 500.0, 200.0, 560.0), width=2)
    window.view.add_annotation(box)
    window.view.add_annotation(far)
    qapp.processEvents()

    window.select_tool(Tool.ERASER)
    stroke = _pasar_la_goma(window, [(120, 120), (140, 130), (160, 140)])
    qapp.processEvents()

    assert box not in list(window.view.store)
    assert far in list(window.view.store)
    assert stroke.kind is Kind.ERASE


def test_a_whole_eraser_pass_undoes_at_once(window, qapp):
    """La pasada y lo que se llevo por delante son un solo paso de deshacer."""
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0), width=2)
    window.view.add_annotation(box)
    qapp.processEvents()

    window.select_tool(Tool.ERASER)
    _pasar_la_goma(window, [(120, 120), (160, 140)])
    qapp.processEvents()
    assert box not in list(window.view.store)

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert box in list(window.view.store)
    assert not [a for a in window.view.annotations() if a.kind is Kind.ERASE]


def test_the_eraser_covers_in_white_by_default(window, qapp):
    window.select_tool(Tool.ERASER)
    assert window.view.eraser_color == (1.0, 1.0, 1.0)
    stroke = _pasar_la_goma(window, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert stroke.color == (1.0, 1.0, 1.0)


def test_the_eraser_colour_can_be_chosen(window, qapp):
    window.select_tool(Tool.ERASER)
    window.view.set_eraser_color((0.2, 0.4, 0.9))
    stroke = _pasar_la_goma(window, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert stroke.color == (0.2, 0.4, 0.9)


def test_the_eraser_stroke_uses_the_chosen_size(window, qapp):
    window.select_tool(Tool.ERASER)
    window.view.set_eraser_size(36)
    stroke = _pasar_la_goma(window, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert stroke.width == 36


def test_what_the_eraser_paints_undoes_in_one_step(window, qapp):
    window.select_tool(Tool.ERASER)
    total = len(window.view.store)
    _pasar_la_goma(window, [(100, 100), (120, 110), (140, 120), (160, 130)])
    qapp.processEvents()
    assert len(window.view.store) == total + 1

    window.view.undo_stack.undo()          # un solo Ctrl+Z para toda la pasada
    qapp.processEvents()
    assert len(window.view.store) == total


def test_a_single_eraser_tap_leaves_nothing(window, qapp):
    window.select_tool(Tool.ERASER)
    total = len(window.view.store)
    steps = window.view.undo_stack.count()
    _pasar_la_goma(window, [(100, 100)])   # un unico punto: no se dibuja
    qapp.processEvents()
    assert len(window.view.store) == total
    assert window.view.undo_stack.count() == steps


def test_the_rulers_measure_from_the_corner_of_the_sheet(window, qapp):
    from PySide6.QtCore import QPointF

    from easypdf.ui.rulers import PT_PER_MM

    page_item = window.view.current_page_item()
    assert page_item is not None

    # el cero cae en la esquina superior izquierda de la pagina
    esquina = window.view.mapFromScene(page_item.scenePos())
    assert abs(window.ruler_h.value_at(esquina.x())) < 0.5
    assert abs(window.ruler_v.value_at(esquina.y())) < 0.5

    # y 100 x 50 mm dentro de la pagina se leen como 100 x 50
    point = window.view.mapFromScene(
        page_item.mapToScene(QPointF(100 * PT_PER_MM, 50 * PT_PER_MM))
    )
    assert abs(window.ruler_h.value_at(point.x()) - 100) < 0.6
    assert abs(window.ruler_v.value_at(point.y()) - 50) < 0.6


def test_the_rulers_change_unit(window):
    from PySide6.QtCore import QPointF

    from easypdf.ui.rulers import PT_PER_MM

    page_item = window.view.current_page_item()
    point = window.view.mapFromScene(page_item.mapToScene(QPointF(100 * PT_PER_MM, 0)))

    window.set_ruler_unit("cm")
    assert abs(window.ruler_h.value_at(point.x()) - 10) < 0.1
    window.set_ruler_unit("in")
    assert abs(window.ruler_h.value_at(point.x()) - 100 / 25.4) < 0.05
    window.set_ruler_unit("pt")
    assert abs(window.ruler_h.value_at(point.x()) - 100 * PT_PER_MM) < 1.0
    window.set_ruler_unit("mm")


def test_dragging_snaps_to_another_annotation(window, qapp):
    reference = Annotation(kind=Kind.RECT, page=0, rect=(200.0, 200.0, 240.0, 260.0), width=2)
    window.view.add_annotation(reference)
    movida = Annotation(kind=Kind.RECT, page=0, rect=(200.0, 400.0, 280.0, 450.0), width=2)
    window.view.add_annotation(movida)
    qapp.processEvents()

    item = window.view._items[movida.id]
    assert window.view.snap_enabled

    # se propone soltarla 3 pt pasado el borde izquierdo de la otra
    from PySide6.QtCore import QPointF

    proposed = QPointF(item.pos().x() + 3.0, item.pos().y())
    adjusted = item.compute_snap(proposed)
    item.setPos(adjusted)
    qapp.processEvents()
    assert abs(movida.bounds()[0] - 200.0) < 0.01


def test_dragging_snaps_to_the_centre_of_the_sheet(window, qapp):
    width, _alto = window.view.document.page_size(0)
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 400.0, 180.0, 450.0), width=2)
    window.view.add_annotation(box)
    qapp.processEvents()

    from PySide6.QtCore import QPointF

    item = window.view._items[box.id]
    middle = width / 2.0
    goal = middle - (box.bounds()[2] - box.bounds()[0]) / 2.0
    proposed = QPointF(item.pos().x() + (goal - box.bounds()[0]) + 2.0, item.pos().y())
    item.setPos(item.compute_snap(proposed))
    qapp.processEvents()

    centro = (box.bounds()[0] + box.bounds()[2]) / 2.0
    assert abs(centro - middle) < 0.01


def test_with_snapping_off_nothing_snaps(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 400.0, 180.0, 450.0), width=2)
    window.view.add_annotation(box)
    qapp.processEvents()

    window.view.set_snap(False)
    try:
        from PySide6.QtCore import QPointF

        item = window.view._items[box.id]
        antes = box.bounds()[0]
        item.setPos(item.compute_snap(QPointF(item.pos().x() + 3.0, item.pos().y())))
        qapp.processEvents()
        assert abs(box.bounds()[0] - (antes + 3.0)) < 0.01
    finally:
        window.view.set_snap(True)


def test_the_rulers_can_be_hidden(window):
    window.toggle_rulers(False)
    assert not window.ruler_h.isVisible()
    assert not window.ruler_v.isVisible()
    window.toggle_rulers(True)
    assert window.ruler_h.isVisible()


def test_placing_an_annotation_leaves_no_snap_lines_painted(window, qapp):
    """El iman solo actua al arrastrar con el raton.

    Si actuara tambien al crear o cargar anotaciones, quedarian guias rosas
    dibujadas en la pagina sin que nadie este moviendo nada.
    """
    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0), width=2)
    )
    qapp.processEvents()
    assert window.view._guides == (None, None, None)

    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(103.0, 400.0, 180.0, 450.0), width=2)
    )
    qapp.processEvents()
    assert window.view._guides == (None, None, None)


# --------------------------------------------------------------------------
# Tablas
# --------------------------------------------------------------------------

def _tabla(window, qapp, alignment=Align.CENTER):
    ann = Annotation(
        kind=Kind.TABLE, page=0, rect=(80.0, 150.0, 460.0, 290.0), rows=3, cols=3,
        cells=["Nombre", "Cantidad", "Precio", "Tornillo", "120", "3,50",
               "Tuerca", "80", "1,20"],
        align=alignment, width=1,
    )
    window.view.add_annotation(ann)
    qapp.processEvents()
    return ann, window.view._items[ann.id]


def test_the_cell_editor_uses_the_tables_alignment(window, qapp):
    """Si no, el texto se ve a la izquierda al escribir y salta al terminar."""
    from PySide6.QtCore import Qt

    ann, item = _tabla(window, qapp, Align.CENTER)
    item.edit_cell(4)
    qapp.processEvents()
    try:
        alignment = item._editor.document().defaultTextOption().alignment()
        assert alignment == Qt.AlignHCenter
    finally:
        item.finish_editing()
        qapp.processEvents()

    ann.align = Align.RIGHT
    item.edit_cell(4)
    qapp.processEvents()
    try:
        assert item._editor.document().defaultTextOption().alignment() == Qt.AlignRight
    finally:
        item.finish_editing()
        qapp.processEvents()


def test_the_cell_editor_sits_exactly_where_the_painted_text_does(window, qapp):
    from easypdf.ui.items import CELL_PADDING

    _ann, item = _tabla(window, qapp)
    cell = item.local_cell_rects()[4]
    item.edit_cell(4)
    qapp.processEvents()
    try:
        editor = item._editor
        assert abs(editor.pos().x() - (cell.left() + CELL_PADDING)) < 0.01
        assert abs(editor.pos().y() - (cell.top() + CELL_PADDING)) < 0.01
        assert abs(editor.textWidth() - (cell.width() - 2 * CELL_PADDING)) < 0.01
    finally:
        item.finish_editing()
        qapp.processEvents()


def test_a_table_can_be_deleted_with_del_after_editing_it(window, qapp):
    """Tras editar una celda y pulsar Escape, DEL tiene que borrar la tabla.

    El editor de la celda se quedaba vivo con el foco y se comia la tecla.
    """
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    _ann, item = _tabla(window, qapp)
    total = len(window.view.store)

    item.edit_cell(1)
    qapp.processEvents()
    window.view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    qapp.processEvents()
    assert not window.view._text_editing

    item.setSelected(True)
    window.view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
    qapp.processEvents()
    assert len(window.view.store) == total - 1

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert len(window.view.store) == total


def test_the_table_is_cached_so_dragging_does_not_repaint_it(window, qapp):
    from PySide6.QtWidgets import QGraphicsItem

    _ann, item = _tabla(window, qapp)
    assert item.cacheMode() == QGraphicsItem.DeviceCoordinateCache


def test_cell_rects_are_cached_and_rebuilt_on_change(window, qapp):
    ann, item = _tabla(window, qapp)
    primeros = item.local_cell_rects()
    assert item.local_cell_rects() is primeros        # memorizados

    ann.cols = 4
    item.apply_model()
    nuevos = item.local_cell_rects()
    assert nuevos is not primeros                     # rehechos al cambiar
    assert len(nuevos) == ann.rows * 4


# --------------------------------------------------------------------------
# Aviso de version nueva
# --------------------------------------------------------------------------

#: Lo que responderia la web: version nueva y sus paquetes.
NOVEDAD = {
    "version": "9.9.9",
    "url": "https://easypdf.surf",
    "setup": "https://easypdf.surf/EasyPDF-9.9.9-Setup.exe",
    "linux": "https://easypdf.surf/EasyPDF-9.9.9-linux-x64.tar.xz",
}


def test_the_version_notice_offers_download_wait_or_skip(window, monkeypatch):
    from PySide6.QtWidgets import QPushButton

    from easypdf import __version__
    from easypdf.i18n import tr
    from easypdf.ui.update_download import UpdateDialog

    visto = {}

    def falso_exec(self):
        visto["texto"] = self.text.text()
        visto["botones"] = [b.text() for b in self.findChildren(QPushButton)]
        return 0

    monkeypatch.setattr(UpdateDialog, "exec", falso_exec)
    window.settings.set_value("updates/skip", "")
    window._update_manual = False
    window._on_update_result(dict(NOVEDAD))

    assert "9.9.9" in visto["texto"]
    assert __version__ in visto["texto"]
    # Lo que se pidio: bajarla desde aqui, sin tener que ir a la web a mano.
    assert tr("update_download") in visto["botones"]
    assert tr("update_go") in visto["botones"]
    assert tr("update_later") in visto["botones"]
    assert tr("update_skip") in visto["botones"]


def test_skipping_the_version_from_the_notice_is_remembered(window, monkeypatch):
    from easypdf.ui.update_download import UpdateDialog

    def falso_exec(self):
        self.skipped = True               # como pulsar "Saltar esta version"
        return 0

    monkeypatch.setattr(UpdateDialog, "exec", falso_exec)
    window.settings.set_value("updates/skip", "")
    window._update_manual = True
    window._on_update_result(dict(NOVEDAD))
    assert window.settings.value("updates/skip", "") == "9.9.9"
    window.settings.set_value("updates/skip", "")


def test_a_skipped_version_is_not_announced_twice(window, monkeypatch):
    from easypdf.ui.update_download import UpdateDialog

    visto = {}
    monkeypatch.setattr(UpdateDialog, "exec",
                        lambda self: visto.setdefault("texto", self.text.text()) or 0)

    window.settings.set_value("updates/skip", "9.9.9")
    window._update_manual = False
    window._on_update_result(dict(NOVEDAD))
    assert "texto" not in visto           # en el arranque no molesta

    window._update_manual = True         # pero si la busca a mano, si
    window._on_update_result(dict(NOVEDAD))
    assert "9.9.9" in visto.get("texto", "")
    window.settings.set_value("updates/skip", "")


def test_installing_closes_the_program_and_starts_the_installer(window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from easypdf import updates
    from easypdf.ui.main_window import MainWindow

    arrancados = []
    monkeypatch.setattr(updates, "launch_installer", arrancados.append)
    monkeypatch.setattr(MainWindow, "close", lambda self: True)
    monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: None))

    assert window.install_update("C:/tmp/EasyPDF-9.9.9-Setup.exe")
    assert arrancados == ["C:/tmp/EasyPDF-9.9.9-Setup.exe"]


def test_if_it_cannot_close_nothing_is_installed(window, monkeypatch):
    """Con cambios sin guardar el usuario puede cancelar: entonces no se toca nada."""
    from easypdf import updates
    from easypdf.ui.main_window import MainWindow

    arrancados = []
    monkeypatch.setattr(updates, "launch_installer", arrancados.append)
    monkeypatch.setattr(MainWindow, "close", lambda self: False)

    assert not window.install_update("C:/tmp/EasyPDF-9.9.9-Setup.exe")
    assert arrancados == []


def test_with_no_news_it_only_speaks_if_asked(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    calls = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: calls.append(a)))

    window._update_manual = False
    window._on_update_result(None)
    assert not calls                    # al arrancar, en silencio

    window._update_manual = True
    window._on_update_result(None)
    assert calls                        # buscando a mano, contesta


def test_the_start_up_check_can_be_switched_off(window):
    window.act_update_auto.setChecked(False)
    assert window.settings.value("updates/auto", True, type_=bool) is False
    window.act_update_auto.setChecked(True)
    assert window.settings.value("updates/auto", True, type_=bool) is True


# --------------------------------------------------------------------------
# Guias sacadas de las reglas
# --------------------------------------------------------------------------

def test_dragging_from_the_ruler_drops_a_guide(window):
    view = window.view
    view.start_guide("h", 200.0)
    view.move_guide(250.0)
    view.drop_guide(250.0)
    assert view.page_guides(0)["h"] == [250.0]

    view.start_guide("v", 100.0)
    view.drop_guide(150.0)
    assert view.page_guides(0)["v"] == [150.0]


def test_dropping_a_guide_off_the_page_does_not_create_it(window):
    view = window.view
    _ancho, height = view.document.page_size(0)

    view.start_guide("h", 100.0)
    view.drop_guide(height + 50)
    assert view.page_guides(0)["h"] == []

    view.start_guide("h", 100.0)
    view.drop_guide(-25.0)
    assert view.page_guides(0)["h"] == []


def test_a_guide_moves_and_dragging_it_off_deletes_it(window):
    view = window.view
    view.start_guide("h", 300.0)
    view.drop_guide(300.0)

    view.grab_guide("h", 0, 0, 300.0)
    view.drop_guide(420.0)
    assert view.page_guides(0)["h"] == [420.0]

    view.grab_guide("h", 0, 0, 420.0)
    view.drop_guide(-30.0)              # fuera del margen: se borra
    assert view.page_guides(0)["h"] == []


def test_the_guide_under_the_mouse_is_found(window):
    from PySide6.QtCore import QPointF

    view = window.view
    view.start_guide("h", 300.0)
    view.drop_guide(300.0)
    page_item = view._page_items[0]

    encima = page_item.mapToScene(QPointF(100.0, 300.0))
    found_one = view.guide_at(encima)
    assert found_one is not None
    assert found_one[0] == "h" and found_one[3] == 300.0

    assert view.guide_at(page_item.mapToScene(QPointF(100.0, 520.0))) is None


def test_annotations_snap_to_the_guides(window, qapp):
    from PySide6.QtCore import QPointF

    view = window.view
    view.start_guide("v", 150.0)
    view.drop_guide(150.0)

    box = Annotation(kind=Kind.RECT, page=0, rect=(300.0, 400.0, 380.0, 450.0), width=2)
    view.add_annotation(box)
    qapp.processEvents()

    item = view._items[box.id]
    desfase = 150.0 - box.bounds()[0] + 2.5      # casi encima de la guia
    item.setPos(item.compute_snap(QPointF(item.pos().x() + desfase, item.pos().y())))
    qapp.processEvents()
    assert abs(box.bounds()[0] - 150.0) < 0.01


def test_every_guide_can_be_cleared(window):
    view = window.view
    view.start_guide("h", 200.0)
    view.drop_guide(200.0)
    view.start_guide("v", 200.0)
    view.drop_guide(200.0)
    assert view.page_guides(0)["h"] and view.page_guides(0)["v"]

    window._clear_guides()
    assert view.page_guides(0)["h"] == []
    assert view.page_guides(0)["v"] == []


# --------------------------------------------------------------------------
# Panel de plantillas
# --------------------------------------------------------------------------

def _hojas_de_plantilla(window):
    """Las plantillas del arbol, sin los titulos de grupo."""
    output = []
    arbol = window.tpl_tree
    for i in range(arbol.topLevelItemCount()):
        group = arbol.topLevelItem(i)
        for j in range(group.childCount()):
            rama = group.child(j)
            for k in range(rama.childCount()):
                output.append((group.text(0), rama.text(0), rama.child(k)))
    return output


def test_the_panel_lists_the_builtin_templates_by_category(window):
    hojas = _hojas_de_plantilla(window)
    assert len(hojas) >= 4
    assert len({rama for _g, rama, _i in hojas}) >= 3   # varios tipos


def test_a_builtin_template_applies_over_the_document(window, qapp):
    hojas = _hojas_de_plantilla(window)
    from easypdf.templates import builtin_infos

    # se busca por su rama, no por el nombre: cambia con el idioma
    first_tick = builtin_infos()[0].name
    membrete = next(i for _g, _r, i in hojas if first_tick in i.text(0))
    window.tpl_tree.setCurrentItem(membrete)
    assert window.btn_tpl_use.isEnabled()

    antes = len(window.view.store)
    assert window.use_selected_template()
    qapp.processEvents()
    assert len(window.view.store) > antes


def test_builtin_templates_cannot_be_deleted(window):
    hojas = _hojas_de_plantilla(window)
    window.tpl_tree.setCurrentItem(hojas[0][2])
    assert not window.btn_tpl_del.isEnabled()
    assert window.delete_selected_template() is False


def test_new_document_from_a_builtin_template(window, qapp):
    hojas = _hojas_de_plantilla(window)
    from easypdf.templates import builtin_infos

    con_tabla = next(i.name for i in builtin_infos() if i.category == "table"
                     and i.annotations > 5)
    acta = next(i for _g, _r, i in hojas if con_tabla in i.text(0))
    window.tpl_tree.setCurrentItem(acta)

    window._modified = False
    window.view.undo_stack.setClean()
    assert window.new_from_selected_template()
    qapp.processEvents()

    tipos = {a.kind for a in window.view.store}
    assert Kind.TABLE in tipos and Kind.TEXT in tipos


def test_save_and_delete_your_own_template_from_the_panel(window, qapp, tmp_path,
                                                              monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    monkeypatch.setattr(window, "templates_dir", lambda: str(tmp_path))
    monkeypatch.setattr(window, "_ensure_templates_dir", lambda: str(tmp_path))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Mi informe", True)))
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: (a[3][0], True)))

    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(10.0, 10.0, 90.0, 60.0), width=2)
    )
    qapp.processEvents()
    assert window.save_as_template()

    window.refresh_templates()
    mias = [i for _g, _r, i in _hojas_de_plantilla(window) if "Mi informe" in i.text(0)]
    assert len(mias) == 1

    window.tpl_tree.setCurrentItem(mias[0])
    assert window.btn_tpl_del.isEnabled()     # la propia si se borra
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    assert window.delete_selected_template()
    assert not [i for _g, _r, i in _hojas_de_plantilla(window)
                if "Mi informe" in i.text(0)]


def test_the_ruler_shows_where_the_guides_are(window, qapp):
    """Una guia horizontal se mide en la regla vertical, y al reves."""
    view = window.view
    view.start_guide("v", 150.0)      # linea vertical: va en la regla de arriba
    view.drop_guide(150.0)
    qapp.processEvents()

    source = view.current_page_item().scenePos()
    expected = window.ruler_h._guide_pixel(150.0, source.x())
    real = window.ruler_h.value_at(expected)
    assert real is not None
    from easypdf.ui.rulers import PT_PER_MM
    assert abs(real - 150.0 / PT_PER_MM) < 0.6


def test_moving_a_guide_shows_its_measurement(window, qapp):
    view = window.view
    view.start_guide("h", 200.0)
    view.drop_guide(200.0)
    qapp.processEvents()

    view.grab_guide("h", 0, 0, 200.0)
    view.move_guide(300.0)
    qapp.processEvents()

    message = window.statusBar().currentMessage()
    assert message, "no se dijo donde esta la guia"
    # 300 pt son unos 105,8 mm
    assert "105" in message or "106" in message, message
    view.drop_guide(300.0)


def test_the_rulers_repaint_when_the_guides_change(window, qapp):
    """Sin este aviso, la marca de la regla no se movia con la guia."""
    avisos = []
    window.view.guidesChanged.connect(lambda: avisos.append(1))

    window.view.start_guide("h", 100.0)
    window.view.move_guide(150.0)
    window.view.drop_guide(150.0)
    assert len(avisos) >= 3


# -- copiar y pegar -------------------------------------------------------
def _vaciar_portapapeles():
    from PySide6.QtGui import QGuiApplication

    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.clear()


def _seleccionar(window, *annotations):
    view = window.view
    for item in view.selected_items():
        item.setSelected(False)
    for ann in annotations:
        view._items[ann.id].setSelected(True)


def test_copy_and_paste_duplicates_the_selection(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _seleccionar(window, box)

    assert window.view.copy_selected() == 1
    assert window.view.paste_clipboard() == 1
    qapp.processEvents()

    copias = [a for a in window.view.annotations() if a.id != box.id]
    assert len(copias) == 1
    copia = copias[0]
    assert copia.id != box.id                 # es otra anotacion, no la misma
    assert copia.kind is Kind.RECT
    salto = window.view.PASTE_OFFSET
    assert copia.rect == (100 + salto, 100 + salto, 200 + salto, 160 + salto)
    # y queda seleccionada, lista para moverla
    assert [i.ann for i in window.view.selected_items()] == [copia]


def test_pasting_carries_everything_that_defines_the_annotation(window, qapp):
    """Una linea no vive en su rectangulo: hay que mover tambien sus extremos."""
    line = Annotation(kind=Kind.LINE, page=0, p1=(50.0, 300.0), p2=(250.0, 380.0))
    stroke = Annotation(kind=Kind.INK, page=0, strokes=[[(10.0, 20.0), (30.0, 40.0)]])
    window.view.add_annotation(line)
    window.view.add_annotation(stroke)
    qapp.processEvents()
    _seleccionar(window, line, stroke)
    assert window.view.copy_selected() == 2
    assert window.view.paste_clipboard() == 2
    qapp.processEvents()

    salto = window.view.PASTE_OFFSET
    new_ones = [a for a in window.view.annotations() if a.id not in (line.id, stroke.id)]
    copia_linea = next(a for a in new_ones if a.kind is Kind.LINE)
    copia_trazo = next(a for a in new_ones if a.kind is Kind.INK)
    assert copia_linea.p1 == (50 + salto, 300 + salto)
    assert copia_linea.p2 == (250 + salto, 380 + salto)
    assert copia_trazo.strokes == [[(10 + salto, 20 + salto), (30 + salto, 40 + salto)]]


def test_pasting_a_table_keeps_its_content(window, qapp):
    tabla = Annotation(kind=Kind.TABLE, page=0, rect=(60.0, 60.0, 400.0, 200.0),
                       rows=2, cols=2, cells=["a", "b", "c", "d"], font_size=9.0)
    window.view.add_annotation(tabla)
    qapp.processEvents()
    _seleccionar(window, tabla)
    window.view.copy_selected()
    window.view.paste_clipboard()
    qapp.processEvents()

    copia = next(a for a in window.view.annotations() if a.id != tabla.id)
    assert (copia.rows, copia.cols) == (2, 2)
    assert copia.cells == ["a", "b", "c", "d"]
    assert copia.font_size == 9.0


def test_pasting_twice_does_not_stack_the_copies(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _seleccionar(window, box)
    window.view.copy_selected()
    window.view.paste_clipboard()
    window.view.paste_clipboard()
    qapp.processEvents()

    esquinas = sorted(a.rect[0] for a in window.view.annotations() if a.kind is Kind.RECT)
    salto = window.view.PASTE_OFFSET
    assert esquinas == [100.0, 100 + salto, 100 + 2 * salto]


def test_a_whole_paste_undoes_in_one_step(window, qapp):
    """Pegar tres cosas es un solo paso de deshacer, no tres."""
    originales = [
        Annotation(kind=Kind.RECT, page=0, rect=(10.0, 10.0, 60.0, 60.0)),
        Annotation(kind=Kind.RECT, page=0, rect=(80.0, 10.0, 130.0, 60.0)),
        Annotation(kind=Kind.RECT, page=0, rect=(150.0, 10.0, 200.0, 60.0)),
    ]
    for ann in originales:
        window.view.add_annotation(ann)
    qapp.processEvents()
    _seleccionar(window, *originales)
    window.view.copy_selected()
    assert window.view.paste_clipboard() == 3
    qapp.processEvents()
    assert window.view.annotation_count() == 6

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert window.view.annotation_count() == 3


def test_cut_copies_and_removes_the_selection(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _seleccionar(window, box)

    assert window.view.cut_selected() == 1
    qapp.processEvents()
    assert window.view.annotation_count() == 0

    assert window.view.paste_clipboard() == 1     # seguia en el portapapeles
    qapp.processEvents()
    assert window.view.annotation_count() == 1


def test_with_nothing_copied_paste_does_nothing(window, qapp):
    _vaciar_portapapeles()
    antes = window.view.annotation_count()
    assert window.view.paste_clipboard() == 0
    assert window.view.annotation_count() == antes


def test_it_pastes_on_the_page_being_viewed(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _seleccionar(window, box)
    window.view.copy_selected()

    assert window.view.paste_clipboard(page=2) == 1
    qapp.processEvents()
    copia = next(a for a in window.view.annotations() if a.id != box.id)
    assert copia.page == 2


def test_copy_and_paste_do_not_steal_the_shortcut_while_typing(window, qapp):
    """Dentro de un texto, Ctrl+C y Ctrl+V son los del editor, no los nuestros."""
    text = Annotation(kind=Kind.TEXT, page=0, rect=(80.0, 80.0, 300.0, 130.0),
                       text="hola")
    item = window.view.add_annotation(text)
    qapp.processEvents()
    _seleccionar(window, text)
    window._update_actions()
    assert window.act_copy.isEnabled()
    assert window.act_paste.isEnabled()

    item.start_editing()
    qapp.processEvents()
    window._update_actions()
    assert not window.act_copy.isEnabled()
    assert not window.act_cut.isEnabled()
    assert not window.act_paste.isEnabled()
    window.view.finish_all_editing()
    qapp.processEvents()


def test_the_keyboard_shortcuts_copy_and_paste(window, qapp):
    """Lo que se pidio: Ctrl+C y Ctrl+V, no solo el menu."""
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _seleccionar(window, box)
    window._update_actions()

    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == 2

    _seleccionar(window, box)
    window._update_actions()
    QTest.keyClick(window, Qt.Key_X, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == 1


def test_what_another_program_copied_is_not_pasted(window, qapp):
    """Un texto cualquiera del portapapeles no puede convertirse en anotaciones."""
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText("una nota que copie de otro sitio")
    antes = window.view.annotation_count()
    assert window.view.paste_clipboard() == 0
    assert window.view.annotation_count() == antes


# -- la goma se queda dentro de la hoja -----------------------------------
def _claros_fuera_de_la_pagina(window, page_item: int = 0, margin: int = 40) -> int:
    """Cuenta los pixeles claros pintados en el borde de fuera del papel.

    Se pinta una franja alrededor de la hoja y se miran solo esos pixeles: es
    donde se veria lo que se sale. El documento tiene mas paginas, asi que las
    que caigan dentro de la franja se descuentan; son papel tambien.
    """
    from PySide6.QtCore import QRect, QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    view = window.view
    paper = view._page_items[page_item].mapRectToScene(
        view._page_items[page_item].boundingRect()
    )
    zona = paper.adjusted(-margin, -margin, margin, margin)
    image = QImage(int(zona.width()), int(zona.height()), QImage.Format_RGB32)
    image.fill(QColor("#404040"))
    pintor = QPainter(image)
    view.scene().render(pintor, QRectF(image.rect()), zona)
    pintor.end()

    # El borde de la propia hoja va suavizado: dos pixeles de respeto.
    inside = paper.translated(-zona.x(), -zona.y()).adjusted(-2, -2, 2, 2)
    others = [
        item.mapRectToScene(item.boundingRect())
        .translated(-zona.x(), -zona.y())
        .adjusted(-2, -2, 2, 2)
        for i, item in enumerate(view._page_items) if i != page_item
    ]
    width, height = image.width(), image.height()
    bands = [
        QRect(0, 0, width, margin),                       # arriba
        QRect(0, height - margin, width, margin),           # abajo
        QRect(0, 0, margin, height),                        # izquierda
        QRect(width - margin, 0, margin, height),           # derecha
    ]
    seen, light_pixels = set(), 0
    for band in bands:
        for y in range(band.top(), band.bottom() + 1):
            for x in range(band.left(), band.right() + 1):
                if (x, y) in seen or not image.rect().contains(x, y):
                    continue
                seen.add((x, y))
                if inside.contains(x, y) or any(r.contains(x, y) for r in others):
                    continue
                if QColor(image.pixel(x, y)).lightness() > 200:
                    light_pixels += 1
    return light_pixels


def test_the_eraser_paints_nothing_outside_the_sheet(window, qapp):
    """Sacando la goma de la pagina se comia el fondo gris de alrededor."""
    window.select_tool(Tool.ERASER)
    window.view.set_eraser_size(24)
    _pasar_la_goma(window, [(200, 200), (50, 100), (-150, -80), (-200, 300)])
    qapp.processEvents()
    assert _claros_fuera_de_la_pagina(window) == 0


def test_an_annotation_is_not_painted_outside_the_sheet_either(window, qapp):
    """Lo que sale del papel no se imprime, asi que tampoco se ve en pantalla."""
    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(-200.0, 100.0, 300.0, 200.0),
                   color=(1.0, 1.0, 1.0), fill=(1.0, 1.0, 1.0), width=3)
    )
    qapp.processEvents()
    assert _claros_fuera_de_la_pagina(window) == 0


# -- DEL y el aviso de que no hay nada seleccionado -----------------------
def test_del_says_something_instead_of_doing_nothing_with_another_tool(window, qapp):
    """Con la goma activa no se puede seleccionar, y DEL se quedaba mudo."""
    window.select_tool(Tool.ERASER)
    _pasar_la_goma(window, [(120, 150), (200, 150)])
    qapp.processEvents()
    window._update_actions()

    # La accion tiene que seguir activa: si se desactiva, el atajo ni se
    # dispara y el usuario no se entera de nada.
    assert window.act_delete.isEnabled()
    window.statusBar().clearMessage()
    window.delete_selection()
    assert window.statusBar().currentMessage() == tr("status_pick_select")


def test_with_the_select_tool_the_usual_message_shows(window, qapp):
    window.select_tool(Tool.SELECT)
    window.view.scene().clearSelection()
    qapp.processEvents()
    window.statusBar().clearMessage()
    window.delete_selection()
    assert window.statusBar().currentMessage() == tr("status_no_selection")


def test_after_the_eraser_you_can_select_and_delete_again(window, qapp):
    """El camino completo del que se quejaba el usuario, de punta a punta."""
    from PySide6.QtCore import QPointF

    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 300.0, 200.0))
    window.view.add_annotation(box)
    window.select_tool(Tool.ERASER)
    _pasar_la_goma(window, [(120, 150), (280, 150)])
    qapp.processEvents()
    # la goma se llevo la caja y dejo su propia pasada
    assert window.view.annotation_count() == 1

    QTest.keyClick(window.view.viewport(), Qt.Key_Escape)
    qapp.processEvents()
    assert window.view.tool is Tool.SELECT

    page_item = window.view._page_items[0]
    point = window.view.mapFromScene(page_item.mapToScene(QPointF(200.0, 150.0)))
    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier, point)
    qapp.processEvents()
    assert window.view.selected_items()
    window._update_actions()
    QTest.keyClick(window, Qt.Key_Delete)
    qapp.processEvents()
    assert window.view.annotation_count() == 0


# -- el acerca de y las licencias ----------------------------------------
def test_the_about_box_has_no_library_small_print():
    """Se pidio quitarla de ahi; sigue estando, pero en su propia ventana."""
    text = tr("about_html", url="https://easypdf.surf")
    assert "PySide6" not in text
    assert "PyMuPDF" not in text
    assert "warranty" not in text.lower()


def test_the_licences_are_still_one_click_away(window, qapp):
    """PySide6 es LGPL: hay que avisar de que se usa y bajo que licencia."""
    from easypdf.ui.main_window import AboutDialog, LicencesDialog

    licencias = tr("licences_html")
    assert "PySide6" in licencias and "LGPL" in licencias
    assert "PyMuPDF" in licencias and "AGPL" in licencias

    dialogo = AboutDialog(window)
    try:
        from PySide6.QtWidgets import QPushButton

        buttons = [b.text() for b in dialogo.findChildren(QPushButton)]
        assert tr("about_licences") in buttons
    finally:
        dialogo.deleteLater()

    ventana_licencias = LicencesDialog(window)
    try:
        assert ventana_licencias.windowTitle() == tr("licences_title")
    finally:
        ventana_licencias.deleteLater()


# -- el panel de plantillas ----------------------------------------------
def test_the_side_panel_has_room_for_the_templates_tree(window, qapp):
    """Con 190 px el arbol ensenaba tres filas y el boton de guardar no se veia."""
    qapp.processEvents()
    assert window.side_tabs.minimumHeight() >= 300
    assert window.bookmark_dock.height() >= 300


def test_the_templates_panel_has_its_save_button(window, qapp):
    window.side_tabs.setCurrentIndex(2)
    qapp.processEvents()
    window._update_template_buttons()
    assert window.btn_tpl_save.text() == tr("tpl_save")
    assert window.btn_tpl_save.isEnabled()      # hay documento abierto


def test_a_new_template_is_saved_in_the_templates_folder(window, tmp_path, monkeypatch):
    """Lo guardado tiene que acabar en Templates, no en cualquier sitio."""
    import os

    from easypdf.templates import list_templates

    monkeypatch.setattr(type(window), "templates_dir",
                        lambda self: str(tmp_path / "AppData" / "Templates"))
    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(60.0, 60.0, 500.0, 120.0))
    )
    monkeypatch.setattr("easypdf.ui.main_window.QInputDialog.getText",
                        staticmethod(lambda *a, **k: ("Mi membrete", True)))
    monkeypatch.setattr("easypdf.ui.main_window.QInputDialog.getItem",
                        staticmethod(lambda *a, **k: (tr("cat_letterhead"), True)))

    assert window.save_as_template()
    folder = window.templates_dir()
    assert os.path.basename(folder) == "Templates"
    files = os.listdir(folder)
    assert files == ["Mi membrete.easypdf-template.json"]
    saved_ones = list_templates(folder)
    assert [(i.name, i.category) for i in saved_ones] == [("Mi membrete", "letterhead")]


def test_undoing_the_eraser_says_it_was_the_eraser(window, qapp):
    """En el menu de deshacer ponia 'Anadir dibujo': por dentro es tinta,
    pero lo que hizo el usuario fue borrar."""
    window.select_tool(Tool.ERASER)
    _pasar_la_goma(window, [(120, 150), (200, 150)])
    qapp.processEvents()
    assert window.view.undo_stack.undoText() == tr("cmd_erase")


# -- piezas de formulario -------------------------------------------------
def _elegir_elemento(window, key):
    """Selecciona una pieza del arbol por su clave."""
    for i in range(window.el_tree.topLevelItemCount()):
        root = window.el_tree.topLevelItem(i)
        for j in range(root.childCount()):
            if root.child(j).data(0, Qt.UserRole) == key:
                window.el_tree.setCurrentItem(root.child(j))
                return root.child(j)
    raise AssertionError(f"no esta la pieza {key}")


def test_the_panel_has_an_elements_tab(window, qapp):
    """Lo que se pidio: una lista de piezas para montar formularios."""
    from easypdf.elements import ELEMENTS

    titulos = [window.side_tabs.tabText(i) for i in range(window.side_tabs.count())]
    assert tr("elements_tab") in titulos

    claves = set()
    for i in range(window.el_tree.topLevelItemCount()):
        root = window.el_tree.topLevelItem(i)
        for j in range(root.childCount()):
            claves.add(root.child(j).data(0, Qt.UserRole))
    assert claves == set(ELEMENTS)


def test_inserting_a_piece_puts_it_on_the_visible_page(window, qapp):
    window.view.go_to_page(1)
    qapp.processEvents()
    _elegir_elemento(window, "checklist")
    window._update_element_buttons()
    assert window.btn_el_insert.isEnabled()

    antes = window.view.annotation_count()
    assert window.insert_selected_element()
    qapp.processEvents()
    new_ones = list(window.view.annotations())[antes:]
    assert len(new_ones) == 8                       # 4 casillas con su etiqueta
    assert {a.page for a in new_ones} == {1}        # en la pagina que se esta viendo
    assert len(window.view.selected_items()) == 8


def test_the_piece_lands_inside_the_paper(window, qapp):
    _elegir_elemento(window, "table")
    antes = window.view.annotation_count()
    window.insert_selected_element()
    qapp.processEvents()
    sheet = window.view._page_items[window.view.current_page].boundingRect()
    for ann in list(window.view.annotations())[antes:]:
        x0, y0, x1, y1 = ann.bounds()
        assert x0 >= 0 and y0 >= 0
        assert x1 <= sheet.width() and y1 <= sheet.height()


def test_a_whole_piece_undoes_in_one_step(window, qapp):
    _elegir_elemento(window, "checklist")
    antes = window.view.annotation_count()
    window.insert_selected_element()
    qapp.processEvents()
    assert window.view.annotation_count() == antes + 8

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert window.view.annotation_count() == antes


def test_with_no_document_nothing_can_be_inserted(window, qapp):
    window.close_document()
    qapp.processEvents()
    _elegir_elemento(window, "checkbox")
    window._update_element_buttons()
    assert not window.btn_el_insert.isEnabled()
    assert not window.insert_selected_element()


def test_the_panel_tabs_do_not_get_mixed_up_when_the_language_changes(window, qapp):
    """Se nombraban por indice, y al meter Elementos en medio se cruzaban."""
    from easypdf.i18n import set_language

    try:
        set_language("es")
        window.retranslate()
        qapp.processEvents()
        titulos = [window.side_tabs.tabText(i) for i in range(window.side_tabs.count())]
        assert titulos[window.side_tabs.indexOf(window.el_tree.parentWidget())] \
            == tr("elements_tab")
        assert titulos[window.side_tabs.indexOf(window.tpl_tree.parentWidget())] \
            == tr("templates_tab")
    finally:
        set_language("en")
        window.retranslate()
        qapp.processEvents()


# -- la tabla dejaba el programa bloqueado --------------------------------
def _dibujar_tabla(window, qapp, desde=(80.0, 120.0), hasta=(420.0, 300.0)):
    """Inserta una tabla arrastrando, como hace el usuario con la herramienta."""
    from PySide6.QtCore import QPointF

    view = window.view
    page_item = view._page_items[view.current_page]

    def point(x, y):
        return view.mapFromScene(page_item.mapToScene(QPointF(x, y)))

    window.select_tool(Tool.TABLE)
    qapp.processEvents()
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*desde))
    QTest.mouseMove(view.viewport(), point(*hasta))
    qapp.processEvents()
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*hasta))
    qapp.processEvents()
    return point


def test_clicking_outside_ends_the_cell_edit(window, qapp):
    """El editor es hijo de la tabla: al perder el foco, ella no se enteraba.

    Se quedaba en modo edicion para siempre, y en ese modo se le ceden los
    atajos al editor de texto: DEL, Ctrl+C y Ctrl+V dejaban de funcionar en
    todo el documento hasta que alguien pulsaba Esc.
    """
    point = _dibujar_tabla(window, qapp)
    assert window.view.is_editing_text          # la tabla abre su primera celda

    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(500.0, 620.0))
    qapp.processEvents()
    assert not window.view.is_editing_text


def test_a_table_can_be_deleted_with_del(window, qapp):
    point = _dibujar_tabla(window, qapp)
    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(500.0, 620.0))
    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(200.0, 200.0))
    qapp.processEvents()
    window._update_actions()
    assert window.act_delete.isEnabled()
    assert len(window.view.selected_items()) == 1

    QTest.keyClick(window, Qt.Key_Delete)
    qapp.processEvents()
    assert window.view.annotation_count() == 0


def test_a_table_can_be_copied_and_pasted(window, qapp):
    point = _dibujar_tabla(window, qapp)
    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(500.0, 620.0))
    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(200.0, 200.0))
    qapp.processEvents()
    window._update_actions()

    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    tablas = [a for a in window.view.annotations() if a.kind is Kind.TABLE]
    assert len(tablas) == 2
    assert tablas[0].id != tablas[1].id


def test_tab_moves_to_the_next_cell_and_shift_tab_back(window, qapp):
    """La ayuda lo prometia desde siempre y no ocurria: el tabulador se lo
    quedaba el widget para mover el foco antes de llegar a la tabla."""
    tabla = Annotation(kind=Kind.TABLE, page=0, rect=(80.0, 120.0, 420.0, 300.0),
                       rows=2, cols=2)
    item = window.view.add_annotation(tabla)
    qapp.processEvents()
    item.edit_cell(0)
    qapp.processEvents()

    view = window.view.viewport()
    QTest.keyClicks(view, "uno")
    QTest.keyClick(view, Qt.Key_Tab)
    qapp.processEvents()
    assert item._editing_cell == 1

    QTest.keyClicks(view, "dos")
    QTest.keyClick(view, Qt.Key_Backtab, Qt.ShiftModifier)
    qapp.processEvents()
    assert item._editing_cell == 0

    QTest.keyClick(view, Qt.Key_Escape)
    qapp.processEvents()
    assert not window.view.is_editing_text
    assert tabla.cells[:2] == ["uno", "dos"]


def test_while_typing_in_a_cell_del_does_not_delete_the_table(window, qapp):
    """Lo contrario tambien tiene que seguir siendo cierto."""
    tabla = Annotation(kind=Kind.TABLE, page=0, rect=(80.0, 120.0, 420.0, 300.0),
                       rows=2, cols=2)
    item = window.view.add_annotation(tabla)
    qapp.processEvents()
    item.edit_cell(0)
    qapp.processEvents()
    window._update_actions()
    assert not window.act_delete.isEnabled()
    assert not window.act_copy.isEnabled()

    QTest.keyClick(window.view.viewport(), Qt.Key_Escape)
    qapp.processEvents()


def test_the_eraser_warns_the_erasure_is_permanent(window, qapp):
    """Al guardar desaparece del archivo: el usuario tiene que saberlo."""
    window.select_tool(Tool.ERASER)
    window.statusBar().clearMessage()
    _pasar_la_goma(window, [(120, 150), (200, 150)])
    qapp.processEvents()
    assert window.statusBar().currentMessage() == tr("status_erased")


# -- ensenar y esconder el panel lateral ----------------------------------
def test_the_view_menu_shows_and_hides_the_side_panel(window, qapp):
    """Se podia cerrar con el aspa y luego no habia forma de recuperarlo."""
    assert window.act_side_panel.isCheckable()
    assert window.bookmark_dock.isVisible()
    assert window.act_side_panel.isChecked()

    window.act_side_panel.trigger()
    qapp.processEvents()
    assert not window.bookmark_dock.isVisible()

    window.act_side_panel.trigger()
    qapp.processEvents()
    assert window.bookmark_dock.isVisible()


def test_closing_the_panel_unchecks_the_menu_option(window, qapp):
    window.bookmark_dock.close()
    qapp.processEvents()
    assert not window.act_side_panel.isChecked()
    window.act_side_panel.trigger()      # y se recupera desde el menu
    qapp.processEvents()
    assert window.bookmark_dock.isVisible()


def test_one_guide_serves_every_page(window, qapp):
    """Se ponen para alinear lo mismo en todas las hojas, no en una sola."""
    view = window.view
    view.clear_all_guides()
    view.start_guide("h", 250.0)
    view.drop_guide(250.0)
    qapp.processEvents()

    assert view.rulers_guides["h"] == [250.0]
    # da igual por que pagina se pregunte: la guia es del documento
    assert view.page_guides(0)["h"] == [250.0]
    assert view.page_guides(2)["h"] == [250.0]
    assert view.page_guides(0) is view.page_guides(2)


def test_an_annotation_on_another_page_snaps_to_the_guide(window, qapp):
    """De poco sirve verla en todas las paginas si solo tira en la suya."""
    view = window.view
    view.clear_all_guides()
    view.snap_enabled = True
    view.start_guide("h", 250.0)
    view.drop_guide(250.0)
    qapp.processEvents()

    from PySide6.QtCore import QPointF

    box = Annotation(kind=Kind.RECT, page=2, rect=(100.0, 100.0, 200.0, 150.0))
    item = view.add_annotation(box)
    qapp.processEvents()

    # se propone soltarla con el borde de arriba tres puntos pasada la guia
    proposed = QPointF(item.pos().x(), item.pos().y() + (250.0 - 100.0) + 3.0)
    item.setPos(item.compute_snap(proposed))
    qapp.processEvents()
    assert abs(box.bounds()[1] - 250.0) < 0.01


def test_clearing_guides_clears_the_whole_document(window, qapp):
    view = window.view
    view.start_guide("h", 100.0)
    view.drop_guide(100.0)
    view.start_guide("v", 200.0)
    view.drop_guide(200.0)
    qapp.processEvents()
    assert view.rulers_guides["h"] and view.rulers_guides["v"]

    view.clear_all_guides()
    qapp.processEvents()
    assert view.rulers_guides == {"h": [], "v": []}


# -- salir de un elemento y poder copiarlo --------------------------------
def _dibujar(window, qapp, tool, desde, hasta):
    """Dibuja una anotacion arrastrando, como hace el usuario."""
    from PySide6.QtCore import QPointF

    view = window.view
    page_item = view._page_items[view.current_page]

    def point(x, y):
        return view.mapFromScene(page_item.mapToScene(QPointF(x, y)))

    window.select_tool(tool)
    qapp.processEvents()
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*desde))
    QTest.mouseMove(view.viewport(), point(*hasta))
    qapp.processEvents()
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*hasta))
    qapp.processEvents()
    return point


@pytest.mark.parametrize("tool", [Tool.TEXT, Tool.RECT, Tool.TABLE, Tool.ARROW])
def test_esc_leaves_the_element_ready_to_copy(window, qapp, tool):
    """Esc soltaba tambien la seleccion, y Ctrl+C se quedaba sin nada que copiar."""
    _vaciar_portapapeles()
    _dibujar(window, qapp, tool, (80.0, 100.0), (350.0, 160.0))
    QTest.keyClick(window.view.viewport(), Qt.Key_Escape)
    qapp.processEvents()

    assert window.view.tool is Tool.SELECT
    assert not window.view.is_editing_text
    assert len(window.view.selected_items()) == 1

    antes = window.view.annotation_count()
    window._update_actions()
    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == antes + 1


@pytest.mark.parametrize("tool", [Tool.TEXT, Tool.TABLE])
def test_the_first_click_outside_leaves_the_box_still_selected(window, qapp, tool):
    """Salir de un texto o una celda no puede dejarte sin nada seleccionado."""
    _vaciar_portapapeles()
    point = _dibujar(window, qapp, tool, (80.0, 100.0), (350.0, 160.0))
    assert window.view.is_editing_text

    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(480.0, 700.0))
    qapp.processEvents()
    assert not window.view.is_editing_text
    assert len(window.view.selected_items()) == 1

    antes = window.view.annotation_count()
    window._update_actions()
    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == antes + 1


def test_the_second_click_on_empty_space_does_clear_the_selection(window, qapp):
    """Se sigue pudiendo deseleccionar, que si no no habria forma."""
    point = _dibujar(window, qapp, Tool.TEXT, (80.0, 100.0), (350.0, 160.0))
    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(480.0, 700.0))
    qapp.processEvents()
    assert window.view.selected_items()

    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(480.0, 700.0))
    qapp.processEvents()
    assert not window.view.selected_items()


def test_esc_still_cancels_what_is_being_drawn(window, qapp):
    """Lo que Esc si tiene que tirar: el trazo a medias."""
    from PySide6.QtCore import QPointF

    view = window.view
    page_item = view._page_items[0]

    def point(x, y):
        return view.mapFromScene(page_item.mapToScene(QPointF(x, y)))

    antes = view.annotation_count()
    window.select_tool(Tool.RECT)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(80.0, 100.0))
    QTest.mouseMove(view.viewport(), point(300.0, 200.0))
    qapp.processEvents()
    QTest.keyClick(view.viewport(), Qt.Key_Escape)
    qapp.processEvents()
    assert view.annotation_count() == antes
    assert view.tool is Tool.SELECT
