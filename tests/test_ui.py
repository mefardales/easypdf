"""Interface tests (they run with the Qt 'offscreen' platform)."""

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
    set_language("en")          # the tests do not depend on the system's language
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


def _drag(window, start, end_at, modificador=Qt.NoModifier):
    viewport = window.view.viewport()
    QTest.mousePress(viewport, Qt.LeftButton, modificador, QPoint(*start))
    QTest.mouseMove(viewport, QPoint(*end_at))
    QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, modificador, QPoint(*end_at))
    QApplication.processEvents()


def test_opening_a_document_sets_up_the_window(window):
    assert window.view.page_count == 3
    assert window.page_label.text() == tr("status_of", total=3)
    assert "muestra.pdf" in window.windowTitle()
    assert window.act_print.isEnabled()


def test_draw_with_every_tool(window):
    window.select_tool(Tool.RECT)
    _drag(window, (150, 150), (400, 260))
    window.select_tool(Tool.LINE)
    _drag(window, (150, 300), (420, 380))
    window.select_tool(Tool.ARROW)
    _drag(window, (150, 420), (420, 500))
    window.select_tool(Tool.HIGHLIGHT)
    _drag(window, (150, 120), (430, 145))
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
    _drag(window, (150, 600), (420, 650))
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
    _drag(window, (200, 300), (203, 302))
    annotations = list(window.view.annotations())
    assert len(annotations) == 1
    x0, y0, x1, y1 = annotations[0].normalized_rect()
    assert x1 - x0 > 100 and y1 - y0 > 10


def test_undo_and_redo(window):
    window.select_tool(Tool.RECT)
    _drag(window, (150, 150), (400, 260))
    assert window.view.annotation_count() == 1
    window.view.undo_stack.undo()
    assert window.view.annotation_count() == 0
    window.view.undo_stack.redo()
    assert window.view.annotation_count() == 1


def test_delete_selection(window):
    window.select_tool(Tool.RECT)
    _drag(window, (150, 150), (400, 260))
    window.view.select_all_annotations()
    QApplication.processEvents()
    assert window.view.delete_selected()
    assert window.view.annotation_count() == 0
    window.view.undo_stack.undo()
    assert window.view.annotation_count() == 1


def test_move_and_undo_restores_the_position(window):
    window.select_tool(Tool.RECT)
    _drag(window, (150, 150), (400, 260))
    item = window.view.selected_items()[0]
    initial = item.ann.rect
    window.view._scene.begin_edit(item)
    item.moveBy(12, 20)
    item.sync_model()
    window.view._scene.end_edit(item)
    assert item.ann.rect != initial
    window.view.undo_stack.undo()
    assert item.ann.rect == pytest.approx(initial)


def test_change_the_style_of_the_selection(window):
    window.select_tool(Tool.RECT)
    _drag(window, (150, 150), (400, 260))
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
    """While typing, the global shortcuts must not steal the keys."""
    window.select_tool(Tool.TEXT)
    _drag(window, (150, 600), (420, 650))
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
    """Regression: moving the position inside itemChange sent the drawing flying."""
    window.select_tool(Tool.INK)
    viewport = window.view.viewport()
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(200, 300))
    for x in range(210, 360, 10):
        QTest.mouseMove(viewport, QPoint(x, 300 + (20 if (x // 10) % 2 else -20)))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(360, 300))
    QApplication.processEvents()

    item = window.view._annotation_items()[0]
    before = item.ann.bounds()
    width = before[2] - before[0]

    window.select_tool(Tool.SELECT)
    item.setSelected(True)
    centro = window.view.mapFromScene(item.sceneBoundingRect().center())
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, centro)
    for step in range(1, 5):
        QTest.mouseMove(viewport, centro + QPoint(10 * step, 5 * step))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, centro + QPoint(40, 20))
    QApplication.processEvents()

    after = item.ann.bounds()
    escala = window.view.zoom * (window.view.logicalDpiX() / 72.0)
    assert after[0] - before[0] == pytest.approx(40 / escala, abs=3)
    assert after[1] - before[1] == pytest.approx(20 / escala, abs=3)
    assert (after[2] - after[0]) == pytest.approx(width, abs=0.5)
    assert item.scene() is not None and item.isVisible()


def test_the_arrow_head_is_the_same_on_screen_and_in_the_pdf(qapp):
    """The head that is drawn and the one that is stored must be the same size."""
    from easypdf.model import arrow_head

    ann = Annotation(kind=Kind.ARROW, page=0, p1=(20, 20), p2=(200, 100), width=3.0)
    item = create_item(ann)
    polygon, end = item._arrow_points()
    _base, tip, left, right = arrow_head(ann.p1, ann.p2, ann.width)
    assert (polygon[0].x(), polygon[0].y()) == pytest.approx(tip)
    assert (polygon[1].x(), polygon[1].y()) == pytest.approx(left)
    assert (polygon[2].x(), polygon[2].y()) == pytest.approx(right)
    # the stroke ends inside the head, not at the point
    assert end.x() < tip[0] and end.y() < tip[1]


def test_create_a_table_and_type_in_its_cells(window, tmp_path):
    window.rows_spin.setValue(2)
    window.cols_spin.setValue(3)
    window.select_tool(Tool.TABLE)
    _drag(window, (150, 200), (600, 320))

    table = window.view.selected_items()[0]
    assert table.ann.kind is Kind.TABLE
    assert table.ann.rows == 2 and table.ann.cols == 3
    assert len(table.local_cell_rects()) == 6
    assert table.is_editing  # it goes straight into typing in the first cell

    for index, text in enumerate(["Item", "Quantity", "Amount", "Caps", "8", "64"]):
        table.edit_cell(index)
        table._editor.setPlainText(text)
    table.finish_editing()
    assert table.ann.cells[0] == "Item" and table.ann.cells[5] == "64"

    target = tmp_path / "con-tabla.pdf"
    window.view.document.save_as(str(target), window.view.annotations())
    page_item = pymupdf.open(str(target))[0]
    tipos = [a.type[1] for a in page_item.annots()]
    assert tipos.count("Ink") == 1 and tipos.count("FreeText") == 6


def test_a_tiny_table_gets_a_usable_size(window):
    window.select_tool(Tool.TABLE)
    _drag(window, (200, 300), (204, 303))
    table = window.view.selected_items()[0]
    x0, y0, x1, y1 = table.ann.normalized_rect()
    assert (x1 - x0) > 100 and (y1 - y0) > 40


def test_text_styles_apply_to_the_selection(window):
    from easypdf.model import Align, Font

    window.select_tool(Tool.TEXT)
    _drag(window, (150, 600), (420, 650))
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
    # and they are kept as the preference for the next annotation
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

    # and also when the search box is emptied
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
    _drag(window, (200, 300), (500, 600))
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
    assert window.view.annotation_count() == 0     # it goes with its page

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

    # lay it over the open document, starting at the current page
    window.view.go_to_page(1)
    assert window.apply_template(path)
    assert window.view.annotation_count() == 4
    assert sorted({a.page for a in window.view.annotations()}) == [0, 1]
    # and a single Ctrl+Z undoes the whole template
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
    """The whole window retranslates without restarting."""
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
# Repainting: an item that paints outside its boundingRect() leaves a trail on
# screen when dragged, because Qt only repaints the area the item declares.
# --------------------------------------------------------------------------

ANNOTATIONS_TO_REPAINT = {
    "text": Annotation(kind=Kind.TEXT, page=0, rect=(0, 0, 180, 40), text="sdfsdfs", width=0),
    "text_with_border": Annotation(kind=Kind.TEXT, page=0, rect=(0, 0, 180, 40), text="hello", width=2),
    "box": Annotation(kind=Kind.RECT, page=0, rect=(0, 0, 120, 80), width=3),
    "highlight": Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(0, 0, 120, 30)),
    "line": Annotation(kind=Kind.LINE, page=0, p1=(0, 0), p2=(120, 60), width=3),
    "arrow": Annotation(kind=Kind.ARROW, page=0, p1=(0, 0), p2=(120, 60), width=3),
    "ink": Annotation(kind=Kind.INK, page=0, strokes=[[(0, 0), (40, 50), (90, 10)]], width=3),
    "table": Annotation(
        kind=Kind.TABLE, page=0, rect=(0, 0, 180, 90), rows=2, cols=3,
        cells=["a", "b", "c", "d", "e", "f"],
    ),
}


@pytest.mark.parametrize("name", sorted(ANNOTATIONS_TO_REPAINT))
def test_the_item_paints_nothing_outside_its_bounding_rect(qapp, name):
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem

    background = qcolor((1.0, 1.0, 1.0))
    margin = 40                       # how far around the boundingRect to look

    scene = QGraphicsScene()
    item = create_item(ANNOTATIONS_TO_REPAINT[name].copy())
    scene.addItem(item)
    item.setSelected(True)            # worst case: selection border and handles

    limits = item.boundingRect()
    strip = limits.adjusted(-margin, -margin, margin, margin)
    image = QImage(int(strip.width()), int(strip.height()), QImage.Format_RGB888)
    image.fill(background)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.translate(-strip.left(), -strip.top())
    item.paint(painter, QStyleOptionGraphicsItem(), None)
    painter.end()

    x0 = limits.left() - strip.left()
    y0 = limits.top() - strip.top()
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
# Thumbnail panel: reordering by dragging, and the context menu
# --------------------------------------------------------------------------

def _first_line(window, page_item):
    """The first line of text on a page ('' if it is blank)."""
    lines = window.view.document.page_text(page_item).strip().splitlines()
    return lines[0] if lines else ""


def test_dragging_a_thumbnail_reorders_the_document(window, qapp):
    assert window.view.page_count >= 3   # the sample PDF already has several
    before = [_first_line(window, i) for i in range(window.view.page_count)]

    window._on_thumbnail_dropped(0, 2)
    qapp.processEvents()
    after = [_first_line(window, i) for i in range(window.view.page_count)]

    assert after[2] == before[0]
    assert sorted(after) == sorted(before)          # no se pierde ninguna
    assert window.view.current_page == 2

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert [_first_line(window, i) for i in range(window.view.page_count)] == before


def test_a_thumbnails_menu_offers_every_operation(window):
    _menu, actions = window.build_page_menu(0)
    values = set(actions.values())
    # the insert ones carry the size behind them ("insert_after:A4"), so they
    # are compared by their prefix
    families = {v.split(":", 1)[0] for v in values}
    assert families == {
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
    assert _first_line(window, 1) == _first_line(window, 0)
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
    # the annotation has moved, and is still inside the now rotated page
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
    # "same as this page" plus every size, before and after
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
    # an unknown name is left as it is
    assert page_size_label("Quarto") == "Quarto"
    set_language("en")


def test_dropping_where_qt_sees_no_thumbnail_does_not_send_the_page_to_the_end(window, qapp):
    """The original bug: when indexAt() returned nothing, drop_row gave the
    last position and the page went to the very end.

    The widgets' measurements are not used, since they vary from one system to
    another: a point clearly above the first thumbnail is taken, where no
    platform sees anything.
    """
    from PySide6.QtCore import QPoint

    items = window.thumb_list
    assert items.count() >= 3
    last = items.count() - 1

    r0 = items.visualRect(items.model().index(0, 0))
    above = QPoint(r0.center().x(), max(0, r0.top() - 40))
    assert not items.indexAt(above).isValid()     # there is none here

    target = items.drop_row(above)
    assert target == 0, f"above the first one it should give 0, it gave {target}"
    assert target != last


def test_the_nearest_thumbnail_is_found_by_geometry(window):
    """The part that fixes the bug, without depending on where the mouse lands."""
    from PySide6.QtCore import QPoint

    items = window.thumb_list
    r0 = items.visualRect(items.model().index(0, 0))
    r1 = items.visualRect(items.model().index(1, 0))

    assert items.nearest_row(QPoint(r0.center().x(), r0.top() - 50)) == 0
    assert items.nearest_row(r0.center()) == 0
    assert items.nearest_row(r1.center()) == 1


def test_the_drop_target_never_goes_backwards_as_the_mouse_descends(window):
    """Moving the mouse down can only give an equal or larger position."""
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
    initial = window.view.eraser_size
    zoom = window.view.zoom

    window.zoom_or_eraser(1)
    assert window.view.eraser_size > initial
    assert window.view.zoom == zoom          # the zoom is left alone

    window.zoom_or_eraser(-1)
    assert window.view.eraser_size == initial

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


def _run_the_eraser(window, points, page_item=0):
    """Simulate a whole eraser pass, with its undo step."""
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
    """It really erases: what it runs over goes, what is beside it stays."""
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0), width=2)
    far = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 500.0, 200.0, 560.0), width=2)
    window.view.add_annotation(box)
    window.view.add_annotation(far)
    qapp.processEvents()

    window.select_tool(Tool.ERASER)
    stroke = _run_the_eraser(window, [(120, 120), (140, 130), (160, 140)])
    qapp.processEvents()

    assert box not in list(window.view.store)
    assert far in list(window.view.store)
    assert stroke.kind is Kind.ERASE


def test_a_whole_eraser_pass_undoes_at_once(window, qapp):
    """The pass and what it took with it are a single undo step."""
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0), width=2)
    window.view.add_annotation(box)
    qapp.processEvents()

    window.select_tool(Tool.ERASER)
    _run_the_eraser(window, [(120, 120), (160, 140)])
    qapp.processEvents()
    assert box not in list(window.view.store)

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert box in list(window.view.store)
    assert not [a for a in window.view.annotations() if a.kind is Kind.ERASE]


def test_the_eraser_covers_in_white_by_default(window, qapp):
    window.select_tool(Tool.ERASER)
    assert window.view.eraser_color == (1.0, 1.0, 1.0)
    stroke = _run_the_eraser(window, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert stroke.color == (1.0, 1.0, 1.0)


def test_the_eraser_colour_can_be_chosen(window, qapp):
    window.select_tool(Tool.ERASER)
    window.view.set_eraser_color((0.2, 0.4, 0.9))
    stroke = _run_the_eraser(window, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert stroke.color == (0.2, 0.4, 0.9)


def test_the_eraser_stroke_uses_the_chosen_size(window, qapp):
    window.select_tool(Tool.ERASER)
    window.view.set_eraser_size(36)
    stroke = _run_the_eraser(window, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert stroke.width == 36


def test_what_the_eraser_paints_undoes_in_one_step(window, qapp):
    window.select_tool(Tool.ERASER)
    total = len(window.view.store)
    _run_the_eraser(window, [(100, 100), (120, 110), (140, 120), (160, 130)])
    qapp.processEvents()
    assert len(window.view.store) == total + 1

    window.view.undo_stack.undo()          # a single Ctrl+Z for the whole pass
    qapp.processEvents()
    assert len(window.view.store) == total


def test_a_single_eraser_tap_leaves_nothing(window, qapp):
    window.select_tool(Tool.ERASER)
    total = len(window.view.store)
    steps = window.view.undo_stack.count()
    _run_the_eraser(window, [(100, 100)])   # a single point: nothing is drawn
    qapp.processEvents()
    assert len(window.view.store) == total
    assert window.view.undo_stack.count() == steps


def test_the_rulers_measure_from_the_corner_of_the_sheet(window, qapp):
    from PySide6.QtCore import QPointF

    from easypdf.ui.rulers import PT_PER_MM

    page_item = window.view.current_page_item()
    assert page_item is not None

    # zero falls on the top left corner of the page
    corner = window.view.mapFromScene(page_item.scenePos())
    assert abs(window.ruler_h.value_at(corner.x())) < 0.5
    assert abs(window.ruler_v.value_at(corner.y())) < 0.5

    # and 100 x 50 mm into the page read as 100 x 50
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

    # it is proposed to drop 3 pt past the other one's left edge
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
        before = box.bounds()[0]
        item.setPos(item.compute_snap(QPointF(item.pos().x() + 3.0, item.pos().y())))
        qapp.processEvents()
        assert abs(box.bounds()[0] - (before + 3.0)) < 0.01
    finally:
        window.view.set_snap(True)


def test_the_rulers_can_be_hidden(window):
    window.toggle_rulers(False)
    assert not window.ruler_h.isVisible()
    assert not window.ruler_v.isVisible()
    window.toggle_rulers(True)
    assert window.ruler_h.isVisible()


def test_placing_an_annotation_leaves_no_snap_lines_painted(window, qapp):
    """The magnet only acts while dragging with the mouse.

    If it acted when creating or loading annotations too, pink guides would be
    left painted on the page with nobody moving anything.
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

def _table(window, qapp, alignment=Align.CENTER):
    ann = Annotation(
        kind=Kind.TABLE, page=0, rect=(80.0, 150.0, 460.0, 290.0), rows=3, cols=3,
        cells=["Name", "Quantity", "Price", "Screw", "120", "3.50",
               "Nut", "80", "1.20"],
        align=alignment, width=1,
    )
    window.view.add_annotation(ann)
    qapp.processEvents()
    return ann, window.view._items[ann.id]


def test_the_cell_editor_uses_the_tables_alignment(window, qapp):
    """Otherwise the text sits left while typing and jumps when you finish."""
    from PySide6.QtCore import Qt

    ann, item = _table(window, qapp, Align.CENTER)
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

    _ann, item = _table(window, qapp)
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
    """After editing a cell and pressing Escape, DEL has to delete the table.

    The cell editor stayed alive holding the focus and swallowed the key.
    """
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    _ann, item = _table(window, qapp)
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

    _ann, item = _table(window, qapp)
    assert item.cacheMode() == QGraphicsItem.DeviceCoordinateCache


def test_cell_rects_are_cached_and_rebuilt_on_change(window, qapp):
    ann, item = _table(window, qapp)
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

#: What the site would answer: a new version and its packages.
NEW_RELEASE = {
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

    seen = {}

    def fake_exec(self):
        seen["text"] = self.text.text()
        seen["buttons"] = [b.text() for b in self.findChildren(QPushButton)]
        return 0

    monkeypatch.setattr(UpdateDialog, "exec", fake_exec)
    window.settings.set_value("updates/skip", "")
    window._update_manual = False
    window._on_update_result(dict(NEW_RELEASE))

    assert "9.9.9" in seen["text"]
    assert __version__ in seen["text"]
    # What was asked for: fetch it from here, without going to the site by hand.
    assert tr("update_download") in seen["buttons"]
    assert tr("update_go") in seen["buttons"]
    assert tr("update_later") in seen["buttons"]
    assert tr("update_skip") in seen["buttons"]


def test_skipping_the_version_from_the_notice_is_remembered(window, monkeypatch):
    from easypdf.ui.update_download import UpdateDialog

    def fake_exec(self):
        self.skipped = True               # as if "Skip this version" were pressed
        return 0

    monkeypatch.setattr(UpdateDialog, "exec", fake_exec)
    window.settings.set_value("updates/skip", "")
    window._update_manual = True
    window._on_update_result(dict(NEW_RELEASE))
    assert window.settings.value("updates/skip", "") == "9.9.9"
    window.settings.set_value("updates/skip", "")


def test_a_skipped_version_is_not_announced_twice(window, monkeypatch):
    from easypdf.ui.update_download import UpdateDialog

    seen = {}
    monkeypatch.setattr(UpdateDialog, "exec",
                        lambda self: seen.setdefault("text", self.text.text()) or 0)

    window.settings.set_value("updates/skip", "9.9.9")
    window._update_manual = False
    window._on_update_result(dict(NEW_RELEASE))
    assert "text" not in seen           # at start-up it does not bother you

    window._update_manual = True         # but if you look by hand, it does
    window._on_update_result(dict(NEW_RELEASE))
    assert "9.9.9" in seen.get("text", "")
    window.settings.set_value("updates/skip", "")


def test_installing_closes_the_program_and_starts_the_installer(window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from easypdf import updates
    from easypdf.ui.main_window import MainWindow

    started = []
    monkeypatch.setattr(updates, "launch_installer", started.append)
    monkeypatch.setattr(MainWindow, "close", lambda self: True)
    monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: None))

    assert window.install_update("C:/tmp/EasyPDF-9.9.9-Setup.exe")
    assert started == ["C:/tmp/EasyPDF-9.9.9-Setup.exe"]


def test_if_it_cannot_close_nothing_is_installed(window, monkeypatch):
    """With unsaved changes the user can cancel: then nothing is touched."""
    from easypdf import updates
    from easypdf.ui.main_window import MainWindow

    started = []
    monkeypatch.setattr(updates, "launch_installer", started.append)
    monkeypatch.setattr(MainWindow, "close", lambda self: False)

    assert not window.install_update("C:/tmp/EasyPDF-9.9.9-Setup.exe")
    assert started == []


def test_with_no_news_it_only_speaks_if_asked(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    calls = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: calls.append(a)))

    window._update_manual = False
    window._on_update_result(None)
    assert not calls                    # at start-up, in silence

    window._update_manual = True
    window._on_update_result(None)
    assert calls                        # asked by hand, it answers


def test_the_start_up_check_can_be_switched_off(window):
    window.act_update_auto.setChecked(False)
    assert window.settings.value("updates/auto", True, type_=bool) is False
    window.act_update_auto.setChecked(True)
    assert window.settings.value("updates/auto", True, type_=bool) is True


# --------------------------------------------------------------------------
# Guides pulled out of the rulers
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
    view.drop_guide(-30.0)              # off the margin: it goes
    assert view.page_guides(0)["h"] == []


def test_the_guide_under_the_mouse_is_found(window):
    from PySide6.QtCore import QPointF

    view = window.view
    view.start_guide("h", 300.0)
    view.drop_guide(300.0)
    page_item = view._page_items[0]

    above = page_item.mapToScene(QPointF(100.0, 300.0))
    found_one = view.guide_at(above)
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
    offset = 150.0 - box.bounds()[0] + 2.5      # almost on top of the guide
    item.setPos(item.compute_snap(QPointF(item.pos().x() + offset, item.pos().y())))
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
# The templates panel
# --------------------------------------------------------------------------

def _template_leaves(window):
    """The templates in the tree, without the group headings."""
    output = []
    tree = window.tpl_tree
    for i in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(i)
        for j in range(group.childCount()):
            rama = group.child(j)
            for k in range(rama.childCount()):
                output.append((group.text(0), rama.text(0), rama.child(k)))
    return output


def test_the_panel_lists_the_builtin_templates_by_category(window):
    leaves = _template_leaves(window)
    assert len(leaves) >= 4
    assert len({rama for _g, rama, _i in leaves}) >= 3   # varios tipos


def test_a_builtin_template_applies_over_the_document(window, qapp):
    leaves = _template_leaves(window)
    from easypdf.templates import builtin_infos

    # looked up by its branch, not by name: the name follows the language
    first = builtin_infos()[0].name
    letterhead = next(i for _g, _r, i in leaves if first in i.text(0))
    window.tpl_tree.setCurrentItem(letterhead)
    assert window.btn_tpl_use.isEnabled()

    before = len(window.view.store)
    assert window.use_selected_template()
    qapp.processEvents()
    assert len(window.view.store) > before


def test_builtin_templates_cannot_be_deleted(window):
    leaves = _template_leaves(window)
    window.tpl_tree.setCurrentItem(leaves[0][2])
    assert not window.btn_tpl_del.isEnabled()
    assert window.delete_selected_template() is False


def test_new_document_from_a_builtin_template(window, qapp):
    leaves = _template_leaves(window)
    from easypdf.templates import builtin_infos

    con_tabla = next(i.name for i in builtin_infos() if i.category == "table"
                     and i.annotations > 5)
    acta = next(i for _g, _r, i in leaves if con_tabla in i.text(0))
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
    mias = [i for _g, _r, i in _template_leaves(window) if "Mi informe" in i.text(0)]
    assert len(mias) == 1

    window.tpl_tree.setCurrentItem(mias[0])
    assert window.btn_tpl_del.isEnabled()     # your own one can be deleted
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    assert window.delete_selected_template()
    assert not [i for _g, _r, i in _template_leaves(window)
                if "My report" in i.text(0)]


def test_the_ruler_shows_where_the_guides_are(window, qapp):
    """A horizontal guide is measured on the vertical ruler, and the other way round."""
    view = window.view
    view.start_guide("v", 150.0)      # a vertical line: it goes on the top ruler
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
    """Without this signal, the ruler's marker did not follow the guide."""
    notices = []
    window.view.guidesChanged.connect(lambda: notices.append(1))

    window.view.start_guide("h", 100.0)
    window.view.move_guide(150.0)
    window.view.drop_guide(150.0)
    assert len(notices) >= 3


# -- copiar y pegar -------------------------------------------------------
def _clear_clipboard():
    from PySide6.QtGui import QGuiApplication

    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.clear()


def _select(window, *annotations):
    view = window.view
    for item in view.selected_items():
        item.setSelected(False)
    for ann in annotations:
        view._items[ann.id].setSelected(True)


def test_copy_and_paste_duplicates_the_selection(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _select(window, box)

    assert window.view.copy_selected() == 1
    assert window.view.paste_clipboard() == 1
    qapp.processEvents()

    copies = [a for a in window.view.annotations() if a.id != box.id]
    assert len(copies) == 1
    copy_of = copies[0]
    assert copy_of.id != box.id                 # it is another annotation, not the same one
    assert copy_of.kind is Kind.RECT
    offset = window.view.PASTE_OFFSET
    assert copy_of.rect == (100 + offset, 100 + offset, 200 + offset, 160 + offset)
    # and it is selected, ready to be moved
    assert [i.ann for i in window.view.selected_items()] == [copy_of]


def test_pasting_carries_everything_that_defines_the_annotation(window, qapp):
    """A line does not live in its rectangle: its ends have to move too."""
    line = Annotation(kind=Kind.LINE, page=0, p1=(50.0, 300.0), p2=(250.0, 380.0))
    stroke = Annotation(kind=Kind.INK, page=0, strokes=[[(10.0, 20.0), (30.0, 40.0)]])
    window.view.add_annotation(line)
    window.view.add_annotation(stroke)
    qapp.processEvents()
    _select(window, line, stroke)
    assert window.view.copy_selected() == 2
    assert window.view.paste_clipboard() == 2
    qapp.processEvents()

    offset = window.view.PASTE_OFFSET
    new_ones = [a for a in window.view.annotations() if a.id not in (line.id, stroke.id)]
    line_copy = next(a for a in new_ones if a.kind is Kind.LINE)
    ink_copy = next(a for a in new_ones if a.kind is Kind.INK)
    assert line_copy.p1 == (50 + offset, 300 + offset)
    assert line_copy.p2 == (250 + offset, 380 + offset)
    assert ink_copy.strokes == [[(10 + offset, 20 + offset), (30 + offset, 40 + offset)]]


def test_pasting_a_table_keeps_its_content(window, qapp):
    table = Annotation(kind=Kind.TABLE, page=0, rect=(60.0, 60.0, 400.0, 200.0),
                       rows=2, cols=2, cells=["a", "b", "c", "d"], font_size=9.0)
    window.view.add_annotation(table)
    qapp.processEvents()
    _select(window, table)
    window.view.copy_selected()
    window.view.paste_clipboard()
    qapp.processEvents()

    copy_of = next(a for a in window.view.annotations() if a.id != table.id)
    assert (copy_of.rows, copy_of.cols) == (2, 2)
    assert copy_of.cells == ["a", "b", "c", "d"]
    assert copy_of.font_size == 9.0


def test_pasting_twice_does_not_stack_the_copies(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _select(window, box)
    window.view.copy_selected()
    window.view.paste_clipboard()
    window.view.paste_clipboard()
    qapp.processEvents()

    esquinas = sorted(a.rect[0] for a in window.view.annotations() if a.kind is Kind.RECT)
    offset = window.view.PASTE_OFFSET
    assert esquinas == [100.0, 100 + offset, 100 + 2 * offset]


def test_a_whole_paste_undoes_in_one_step(window, qapp):
    """Pasting three things is one undo step, not three."""
    originals = [
        Annotation(kind=Kind.RECT, page=0, rect=(10.0, 10.0, 60.0, 60.0)),
        Annotation(kind=Kind.RECT, page=0, rect=(80.0, 10.0, 130.0, 60.0)),
        Annotation(kind=Kind.RECT, page=0, rect=(150.0, 10.0, 200.0, 60.0)),
    ]
    for ann in originals:
        window.view.add_annotation(ann)
    qapp.processEvents()
    _select(window, *originals)
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
    _select(window, box)

    assert window.view.cut_selected() == 1
    qapp.processEvents()
    assert window.view.annotation_count() == 0

    assert window.view.paste_clipboard() == 1     # it was still on the clipboard
    qapp.processEvents()
    assert window.view.annotation_count() == 1


def test_with_nothing_copied_paste_does_nothing(window, qapp):
    _clear_clipboard()
    before = window.view.annotation_count()
    assert window.view.paste_clipboard() == 0
    assert window.view.annotation_count() == before


def test_it_pastes_on_the_page_being_viewed(window, qapp):
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _select(window, box)
    window.view.copy_selected()

    assert window.view.paste_clipboard(page=2) == 1
    qapp.processEvents()
    copy_of = next(a for a in window.view.annotations() if a.id != box.id)
    assert copy_of.page == 2


def test_copy_and_paste_do_not_steal_the_shortcut_while_typing(window, qapp):
    """Inside a text, Ctrl+C and Ctrl+V are the editor's, not ours."""
    text = Annotation(kind=Kind.TEXT, page=0, rect=(80.0, 80.0, 300.0, 130.0),
                       text="hola")
    item = window.view.add_annotation(text)
    qapp.processEvents()
    _select(window, text)
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
    """What was asked for: Ctrl+C and Ctrl+V, not just the menu."""
    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    window.view.add_annotation(box)
    qapp.processEvents()
    _select(window, box)
    window._update_actions()

    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == 2

    _select(window, box)
    window._update_actions()
    QTest.keyClick(window, Qt.Key_X, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == 1


def test_what_another_program_copied_is_not_pasted(window, qapp):
    """Any old text on the clipboard must not turn into annotations."""
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText("a note I copied from somewhere else")
    before = window.view.annotation_count()
    assert window.view.paste_clipboard() == 0
    assert window.view.annotation_count() == before


# -- the eraser stays inside the sheet ------------------------------------
def _light_pixels_off_the_page(window, page_item: int = 0, margin: int = 40) -> int:
    """Count the light pixels painted on the border outside the paper.

    A strip around the sheet is painted and only those pixels are looked at:
    that is where anything running off would show. The document has more pages,
    so any that fall inside the strip are discounted; they are paper too.
    """
    from PySide6.QtCore import QRect, QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    view = window.view
    paper = view._page_items[page_item].mapRectToScene(
        view._page_items[page_item].boundingRect()
    )
    strip = paper.adjusted(-margin, -margin, margin, margin)
    image = QImage(int(strip.width()), int(strip.height()), QImage.Format_RGB32)
    image.fill(QColor("#404040"))
    pintor = QPainter(image)
    view.scene().render(pintor, QRectF(image.rect()), strip)
    pintor.end()

    # The sheet's own edge is antialiased: two pixels of leeway.
    inside = paper.translated(-strip.x(), -strip.y()).adjusted(-2, -2, 2, 2)
    others = [
        item.mapRectToScene(item.boundingRect())
        .translated(-strip.x(), -strip.y())
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
    """Running the eraser off the page ate into the grey background around it."""
    window.select_tool(Tool.ERASER)
    window.view.set_eraser_size(24)
    _run_the_eraser(window, [(200, 200), (50, 100), (-150, -80), (-200, 300)])
    qapp.processEvents()
    assert _light_pixels_off_the_page(window) == 0


def test_an_annotation_is_not_painted_outside_the_sheet_either(window, qapp):
    """What runs off the paper does not print, so it is not shown on screen either."""
    window.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(-200.0, 100.0, 300.0, 200.0),
                   color=(1.0, 1.0, 1.0), fill=(1.0, 1.0, 1.0), width=3)
    )
    qapp.processEvents()
    assert _light_pixels_off_the_page(window) == 0


# -- DEL and the notice that nothing is selected --------------------------
def test_del_says_something_instead_of_doing_nothing_with_another_tool(window, qapp):
    """With the eraser active nothing can be selected, and DEL stayed mute."""
    window.select_tool(Tool.ERASER)
    _run_the_eraser(window, [(120, 150), (200, 150)])
    qapp.processEvents()
    window._update_actions()

    # The action has to stay enabled: if it is disabled the shortcut does not
    # even fire and the user learns nothing.
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
    """The whole path the user complained about, end to end."""
    from PySide6.QtCore import QPointF

    box = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 300.0, 200.0))
    window.view.add_annotation(box)
    window.select_tool(Tool.ERASER)
    _run_the_eraser(window, [(120, 150), (280, 150)])
    qapp.processEvents()
    # the eraser took the box with it and left its own pass
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


# -- the about box and the licences ---------------------------------------
def test_the_about_box_has_no_library_small_print():
    """It was asked to be taken out of there; it is still around, in its own window."""
    text = tr("about_html", url="https://easypdf.surf")
    assert "PySide6" not in text
    assert "PyMuPDF" not in text
    assert "warranty" not in text.lower()


def test_the_licences_are_still_one_click_away(window, qapp):
    """PySide6 is LGPL: its use and its licence have to be stated."""
    from easypdf.ui.main_window import AboutDialog, LicencesDialog

    licences = tr("licences_html")
    assert "PySide6" in licences and "LGPL" in licences
    assert "PyMuPDF" in licences and "AGPL" in licences

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


# -- the templates panel --------------------------------------------------
def test_the_side_panel_has_room_for_the_templates_tree(window, qapp):
    """At 190 px the tree showed three rows and the save button was out of sight."""
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
    """What is saved has to end up in Templates, not just anywhere."""
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
    """The undo menu used to say 'Add drawing': inside it is ink, but what
    the user did was rub something out."""
    window.select_tool(Tool.ERASER)
    _run_the_eraser(window, [(120, 150), (200, 150)])
    qapp.processEvents()
    assert window.view.undo_stack.undoText() == tr("cmd_erase")


# -- piezas de formulario -------------------------------------------------
def _choose_element(window, key):
    """Select a piece from the tree by its key."""
    for i in range(window.el_tree.topLevelItemCount()):
        root = window.el_tree.topLevelItem(i)
        for j in range(root.childCount()):
            if root.child(j).data(0, Qt.UserRole) == key:
                window.el_tree.setCurrentItem(root.child(j))
                return root.child(j)
    raise AssertionError(f"no esta la pieza {key}")


def test_the_panel_has_an_elements_tab(window, qapp):
    """What was asked for: a list of pieces for building forms."""
    from easypdf.elements import ELEMENTS

    titles = [window.side_tabs.tabText(i) for i in range(window.side_tabs.count())]
    assert tr("elements_tab") in titles

    claves = set()
    for i in range(window.el_tree.topLevelItemCount()):
        root = window.el_tree.topLevelItem(i)
        for j in range(root.childCount()):
            claves.add(root.child(j).data(0, Qt.UserRole))
    assert claves == set(ELEMENTS)


def test_inserting_a_piece_puts_it_on_the_visible_page(window, qapp):
    window.view.go_to_page(1)
    qapp.processEvents()
    _choose_element(window, "checklist")
    window._update_element_buttons()
    assert window.btn_el_insert.isEnabled()

    before = window.view.annotation_count()
    assert window.insert_selected_element()
    qapp.processEvents()
    new_ones = list(window.view.annotations())[before:]
    assert len(new_ones) == 8                       # 4 tick boxes with their labels
    assert {a.page for a in new_ones} == {1}        # on the page being viewed
    assert len(window.view.selected_items()) == 8


def test_the_piece_lands_inside_the_paper(window, qapp):
    _choose_element(window, "table")
    before = window.view.annotation_count()
    window.insert_selected_element()
    qapp.processEvents()
    sheet = window.view._page_items[window.view.current_page].boundingRect()
    for ann in list(window.view.annotations())[before:]:
        x0, y0, x1, y1 = ann.bounds()
        assert x0 >= 0 and y0 >= 0
        assert x1 <= sheet.width() and y1 <= sheet.height()


def test_a_whole_piece_undoes_in_one_step(window, qapp):
    _choose_element(window, "checklist")
    before = window.view.annotation_count()
    window.insert_selected_element()
    qapp.processEvents()
    assert window.view.annotation_count() == before + 8

    window.view.undo_stack.undo()
    qapp.processEvents()
    assert window.view.annotation_count() == before


def test_with_no_document_nothing_can_be_inserted(window, qapp):
    window.close_document()
    qapp.processEvents()
    _choose_element(window, "checkbox")
    window._update_element_buttons()
    assert not window.btn_el_insert.isEnabled()
    assert not window.insert_selected_element()


def test_the_panel_tabs_do_not_get_mixed_up_when_the_language_changes(window, qapp):
    """They were named by index, and adding Elements in the middle crossed them."""
    from easypdf.i18n import set_language

    try:
        set_language("es")
        window.retranslate()
        qapp.processEvents()
        titles = [window.side_tabs.tabText(i) for i in range(window.side_tabs.count())]
        assert titles[window.side_tabs.indexOf(window.el_tree.parentWidget())]\
            == tr("elements_tab")
        assert titles[window.side_tabs.indexOf(window.tpl_tree.parentWidget())]\
            == tr("templates_tab")
    finally:
        set_language("en")
        window.retranslate()
        qapp.processEvents()


# -- the table used to lock the program up --------------------------------
def _draw_table(window, qapp, start=(80.0, 120.0), end_at=(420.0, 300.0)):
    """Insert a table by dragging, the way the user does with the tool."""
    from PySide6.QtCore import QPointF

    view = window.view
    page_item = view._page_items[view.current_page]

    def point(x, y):
        return view.mapFromScene(page_item.mapToScene(QPointF(x, y)))

    window.select_tool(Tool.TABLE)
    qapp.processEvents()
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*start))
    QTest.mouseMove(view.viewport(), point(*end_at))
    qapp.processEvents()
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*end_at))
    qapp.processEvents()
    return point


def test_clicking_outside_ends_the_cell_edit(window, qapp):
    """The editor is a child of the table: when it lost the focus, the table
    never found out.

    It stayed in editing mode forever, and in that mode the shortcuts are given
    to the text editor: DEL, Ctrl+C and Ctrl+V stopped working across the whole
    document until somebody pressed Esc.
    """
    point = _draw_table(window, qapp)
    assert window.view.is_editing_text          # the table opens its first cell

    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(500.0, 620.0))
    qapp.processEvents()
    assert not window.view.is_editing_text


def test_a_table_can_be_deleted_with_del(window, qapp):
    point = _draw_table(window, qapp)
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
    point = _draw_table(window, qapp)
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
    tables = [a for a in window.view.annotations() if a.kind is Kind.TABLE]
    assert len(tables) == 2
    assert tables[0].id != tables[1].id


def test_tab_moves_to_the_next_cell_and_shift_tab_back(window, qapp):
    """The help had always promised this and it never happened: the widget
    took Tab to move the focus before it ever reached the table."""
    table = Annotation(kind=Kind.TABLE, page=0, rect=(80.0, 120.0, 420.0, 300.0),
                       rows=2, cols=2)
    item = window.view.add_annotation(table)
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
    assert table.cells[:2] == ["uno", "dos"]


def test_while_typing_in_a_cell_del_does_not_delete_the_table(window, qapp):
    """The other way round has to keep holding too."""
    table = Annotation(kind=Kind.TABLE, page=0, rect=(80.0, 120.0, 420.0, 300.0),
                       rows=2, cols=2)
    item = window.view.add_annotation(table)
    qapp.processEvents()
    item.edit_cell(0)
    qapp.processEvents()
    window._update_actions()
    assert not window.act_delete.isEnabled()
    assert not window.act_copy.isEnabled()

    QTest.keyClick(window.view.viewport(), Qt.Key_Escape)
    qapp.processEvents()


def test_the_eraser_warns_the_erasure_is_permanent(window, qapp):
    """On save it disappears from the file: the user has to know that."""
    window.select_tool(Tool.ERASER)
    window.statusBar().clearMessage()
    _run_the_eraser(window, [(120, 150), (200, 150)])
    qapp.processEvents()
    assert window.statusBar().currentMessage() == tr("status_erased")


# -- showing and hiding the side panel ------------------------------------
def test_the_view_menu_shows_and_hides_the_side_panel(window, qapp):
    """It could be closed with the cross and then there was no way to get it back."""
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
    window.act_side_panel.trigger()      # and the menu brings it back
    qapp.processEvents()
    assert window.bookmark_dock.isVisible()


def test_one_guide_serves_every_page(window, qapp):
    """They are put there to align the same thing on every sheet, not just one."""
    view = window.view
    view.clear_all_guides()
    view.start_guide("h", 250.0)
    view.drop_guide(250.0)
    qapp.processEvents()

    assert view.rulers_guides["h"] == [250.0]
    # it does not matter which page is asked about: the guide is the document's
    assert view.page_guides(0)["h"] == [250.0]
    assert view.page_guides(2)["h"] == [250.0]
    assert view.page_guides(0) is view.page_guides(2)


def test_an_annotation_on_another_page_snaps_to_the_guide(window, qapp):
    """Seeing it on every page is little use if it only pulls on its own."""
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

    # it is proposed to drop it with its top edge three points past the guide
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


# -- leaving an element and still being able to copy it -------------------
def _draw(window, qapp, tool, start, end_at):
    """Draw an annotation by dragging, the way the user does."""
    from PySide6.QtCore import QPointF

    view = window.view
    page_item = view._page_items[view.current_page]

    def point(x, y):
        return view.mapFromScene(page_item.mapToScene(QPointF(x, y)))

    window.select_tool(tool)
    qapp.processEvents()
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*start))
    QTest.mouseMove(view.viewport(), point(*end_at))
    qapp.processEvents()
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(*end_at))
    qapp.processEvents()
    return point


@pytest.mark.parametrize("tool", [Tool.TEXT, Tool.RECT, Tool.TABLE, Tool.ARROW])
def test_esc_leaves_the_element_ready_to_copy(window, qapp, tool):
    """Esc used to drop the selection too, leaving Ctrl+C nothing to copy."""
    _clear_clipboard()
    _draw(window, qapp, tool, (80.0, 100.0), (350.0, 160.0))
    QTest.keyClick(window.view.viewport(), Qt.Key_Escape)
    qapp.processEvents()

    assert window.view.tool is Tool.SELECT
    assert not window.view.is_editing_text
    assert len(window.view.selected_items()) == 1

    before = window.view.annotation_count()
    window._update_actions()
    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == before + 1


@pytest.mark.parametrize("tool", [Tool.TEXT, Tool.TABLE])
def test_the_first_click_outside_leaves_the_box_still_selected(window, qapp, tool):
    """Leaving a text or a cell must not leave you with nothing selected."""
    _clear_clipboard()
    point = _draw(window, qapp, tool, (80.0, 100.0), (350.0, 160.0))
    assert window.view.is_editing_text

    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(480.0, 700.0))
    qapp.processEvents()
    assert not window.view.is_editing_text
    assert len(window.view.selected_items()) == 1

    before = window.view.annotation_count()
    window._update_actions()
    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    assert window.view.annotation_count() == before + 1


def test_the_second_click_on_empty_space_does_clear_the_selection(window, qapp):
    """Deselecting still works, otherwise there would be no way to."""
    point = _draw(window, qapp, Tool.TEXT, (80.0, 100.0), (350.0, 160.0))
    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(480.0, 700.0))
    qapp.processEvents()
    assert window.view.selected_items()

    QTest.mouseClick(window.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     point(480.0, 700.0))
    qapp.processEvents()
    assert not window.view.selected_items()


def test_esc_still_cancels_what_is_being_drawn(window, qapp):
    """What Esc does have to throw away: the half-finished stroke."""
    from PySide6.QtCore import QPointF

    view = window.view
    page_item = view._page_items[0]

    def point(x, y):
        return view.mapFromScene(page_item.mapToScene(QPointF(x, y)))

    before = view.annotation_count()
    window.select_tool(Tool.RECT)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, point(80.0, 100.0))
    QTest.mouseMove(view.viewport(), point(300.0, 200.0))
    qapp.processEvents()
    QTest.keyClick(view.viewport(), Qt.Key_Escape)
    qapp.processEvents()
    assert view.annotation_count() == before
    assert view.tool is Tool.SELECT
