"""Pruebas de la interfaz (se ejecutan con la plataforma Qt 'offscreen')."""

import pymupdf
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from easypdf import __app_name__  # noqa: E402
from easypdf.model import (
    Annotation,  # noqa: E402
    Kind,  # noqa: E402
)
from easypdf.ui.items import RectItem, TextItem, create_item, qcolor, to_rgb  # noqa: E402
from easypdf.ui.main_window import MainWindow  # noqa: E402
from easypdf.ui.page_view import Tool  # noqa: E402


@pytest.fixture()
def ventana(qapp, sample_pdf):
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


def test_abrir_documento_configura_la_ventana(ventana):
    assert ventana.view.page_count == 3
    assert ventana.page_label.text() == "de 3"
    assert "muestra.pdf" in ventana.windowTitle()
    assert ventana.act_print.isEnabled()


def test_dibujar_cada_herramienta(ventana):
    ventana.select_tool(Tool.RECT)
    _arrastrar(ventana, (150, 150), (400, 260))
    ventana.select_tool(Tool.LINE)
    _arrastrar(ventana, (150, 300), (420, 380))
    ventana.select_tool(Tool.ARROW)
    _arrastrar(ventana, (150, 420), (420, 500))
    ventana.select_tool(Tool.HIGHLIGHT)
    _arrastrar(ventana, (150, 120), (430, 145))
    tipos = [a.kind for a in ventana.view.annotations()]
    assert tipos == [Kind.RECT, Kind.LINE, Kind.ARROW, Kind.HIGHLIGHT]
    assert ventana.view.tool is Tool.SELECT  # vuelve a seleccionar al terminar


def test_dibujo_libre_acumula_puntos(ventana):
    ventana.select_tool(Tool.INK)
    viewport = ventana.view.viewport()
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(200, 500))
    for x in range(210, 340, 10):
        QTest.mouseMove(viewport, QPoint(x, 520))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(340, 520))
    QApplication.processEvents()
    anotaciones = list(ventana.view.annotations())
    assert len(anotaciones) == 1
    assert len(anotaciones[0].strokes[0]) > 5


def test_cuadro_de_texto_guarda_lo_escrito(ventana, tmp_path):
    ventana.select_tool(Tool.TEXT)
    _arrastrar(ventana, (150, 600), (420, 650))
    seleccion = ventana.view.selected_items()
    assert seleccion and isinstance(seleccion[0], TextItem)
    seleccion[0].setPlainText("Nota de prueba")
    seleccion[0].stop_editing()
    QApplication.processEvents()
    destino = tmp_path / "anotado.pdf"
    ventana.view.document.save_as(str(destino), ventana.view.annotations())
    salida = pymupdf.open(str(destino))
    pagina = salida[0]
    contenidos = [a.info.get("content", "") for a in pagina.annots()]
    assert "Nota de prueba" in contenidos


def test_clic_sin_arrastrar_crea_un_cuadro_de_texto_usable(ventana):
    ventana.select_tool(Tool.TEXT)
    _arrastrar(ventana, (200, 300), (203, 302))
    anotaciones = list(ventana.view.annotations())
    assert len(anotaciones) == 1
    x0, y0, x1, y1 = anotaciones[0].normalized_rect()
    assert x1 - x0 > 100 and y1 - y0 > 10


def test_deshacer_y_rehacer(ventana):
    ventana.select_tool(Tool.RECT)
    _arrastrar(ventana, (150, 150), (400, 260))
    assert ventana.view.annotation_count() == 1
    ventana.view.undo_stack.undo()
    assert ventana.view.annotation_count() == 0
    ventana.view.undo_stack.redo()
    assert ventana.view.annotation_count() == 1


def test_eliminar_seleccion(ventana):
    ventana.select_tool(Tool.RECT)
    _arrastrar(ventana, (150, 150), (400, 260))
    ventana.view.select_all_annotations()
    QApplication.processEvents()
    assert ventana.view.delete_selected()
    assert ventana.view.annotation_count() == 0
    ventana.view.undo_stack.undo()
    assert ventana.view.annotation_count() == 1


def test_mover_y_deshacer_conserva_la_posicion(ventana):
    ventana.select_tool(Tool.RECT)
    _arrastrar(ventana, (150, 150), (400, 260))
    item = ventana.view.selected_items()[0]
    inicial = item.ann.rect
    ventana.view._scene.begin_edit(item)
    item.moveBy(12, 20)
    item.sync_model()
    ventana.view._scene.end_edit(item)
    assert item.ann.rect != inicial
    ventana.view.undo_stack.undo()
    assert item.ann.rect == pytest.approx(inicial)


def test_cambiar_estilo_de_la_seleccion(ventana):
    ventana.select_tool(Tool.RECT)
    _arrastrar(ventana, (150, 150), (400, 260))
    item = ventana.view.selected_items()[0]
    assert ventana.view.apply_style_to_selection(color=(0.0, 0.0, 1.0), width=4.0)
    assert item.ann.color == (0.0, 0.0, 1.0)
    assert item.ann.width == 4.0
    ventana.view.undo_stack.undo()
    assert item.ann.width != 4.0


def test_buscar_texto(ventana):
    ventana.search_edit.setText("EasyPDF")
    ventana.run_search()
    assert ventana.view.hit_count == 3
    assert "1 de 3" in ventana.search_label.text()
    ventana.view.next_hit()
    assert ventana.view.hit_index == 1
    ventana.view.previous_hit()
    assert ventana.view.hit_index == 0
    ventana.search_edit.setText("palabra-que-no-existe")
    ventana.run_search()
    assert ventana.view.hit_count == 0


def test_navegacion_entre_paginas(ventana):
    ventana.view.go_to_page(2)
    QApplication.processEvents()
    assert ventana.view.current_page == 2
    ventana.view.previous_page()
    QApplication.processEvents()
    assert ventana.view.current_page == 1


def test_zoom(ventana):
    ventana.view.set_zoom(1.0)
    ventana.view.zoom_in()
    assert ventana.view.zoom > 1.0
    ventana.view.zoom_out()
    assert ventana.view.zoom == pytest.approx(1.0)
    ventana.view.fit_width()
    assert ventana.view.zoom > 0


def test_miniaturas(ventana, qapp):
    QTest.qWait(400)
    qapp.processEvents()
    assert ventana.thumb_list.count() == 3


def test_cerrar_documento(ventana):
    assert ventana.close_document()
    assert not ventana.view.has_document()
    assert ventana.windowTitle() == __app_name__


def test_color_ida_y_vuelta():
    from PySide6.QtGui import QColor

    color = QColor("#1565c0")
    assert to_rgb(color) == pytest.approx((0.0824, 0.396, 0.753), abs=0.01)
    assert qcolor(to_rgb(color)).name() == "#1565c0"


def test_item_de_cuadro_sincroniza_el_modelo(qapp):
    from PySide6.QtWidgets import QGraphicsScene

    escena = QGraphicsScene()
    ann = Annotation(kind=Kind.RECT, page=0, rect=(10, 20, 110, 70))
    item = create_item(ann)
    escena.addItem(item)
    assert isinstance(item, RectItem)
    assert item.pos().x() == 10 and item.rect().width() == 100
    item.moveBy(5, 5)
    item.sync_model()
    assert ann.rect == (15, 25, 115, 75)


def test_crear_el_item_no_altera_el_modelo(qapp):
    """Regresion: setPos() disparaba itemChange y machacaba la geometria."""
    from PySide6.QtWidgets import QGraphicsScene

    escena = QGraphicsScene()
    for ann in (
        Annotation(kind=Kind.RECT, page=0, rect=(66, 320, 460, 400)),
        Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(70, 152, 470, 172)),
        Annotation(kind=Kind.TEXT, page=0, rect=(300, 240, 520, 285), text="hola"),
        Annotation(kind=Kind.LINE, page=0, p1=(10, 20), p2=(200, 240)),
        Annotation(kind=Kind.INK, page=0, strokes=[[(10, 10), (40, 60), (80, 20)]]),
    ):
        esperado = ann.copy()
        item = create_item(ann)
        escena.addItem(item)
        item.apply_model()          # volver a aplicarlo tampoco puede cambiarlo
        assert ann.rect == pytest.approx(esperado.rect)
        assert ann.p1 == esperado.p1 and ann.p2 == esperado.p2
        assert ann.strokes == esperado.strokes


def test_add_annotation_es_deshacible(ventana):
    ann = Annotation(kind=Kind.RECT, page=1, rect=(50, 60, 300, 200))
    item = ventana.view.add_annotation(ann)
    assert item in ventana.view._annotation_items()
    assert ventana.view.annotation_count() == 1
    ventana.view.undo_stack.undo()
    assert ventana.view.annotation_count() == 0
    assert item not in ventana.view._annotation_items()
    with pytest.raises(IndexError):
        ventana.view.add_annotation(Annotation(kind=Kind.RECT, page=99, rect=(1, 1, 50, 50)))


def test_escribir_texto_libera_supr_y_ctrl_a(ventana):
    """Mientras se escribe, los atajos globales no pueden robar las teclas."""
    ventana.select_tool(Tool.TEXT)
    _arrastrar(ventana, (150, 600), (420, 650))
    item = ventana.view.selected_items()[0]
    assert ventana.view.is_editing_text
    assert not ventana.act_delete.isEnabled()
    assert not ventana.act_select_all.isEnabled()
    item.stop_editing()
    QApplication.processEvents()
    assert not ventana.view.is_editing_text
    assert ventana.act_delete.isEnabled()
    assert ventana.act_select_all.isEnabled()
