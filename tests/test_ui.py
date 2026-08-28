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
    Annotation,  # noqa: E402
    Kind,  # noqa: E402
)
from easypdf.ui.items import RectItem, TextItem, create_item, qcolor, to_rgb  # noqa: E402
from easypdf.ui.main_window import MainWindow  # noqa: E402
from easypdf.ui.page_view import Tool  # noqa: E402


@pytest.fixture()
def ventana(qapp, sample_pdf):
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


def test_abrir_documento_configura_la_ventana(ventana):
    assert ventana.view.page_count == 3
    assert ventana.page_label.text() == tr("status_of", total=3)
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
    assert tr("search_of", current=1, total=3).strip() in ventana.search_label.text()
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


def test_arrastrar_un_dibujo_no_lo_manda_fuera_de_la_pantalla(ventana):
    """Regresion: mover la posicion dentro de itemChange disparaba el dibujo."""
    ventana.select_tool(Tool.INK)
    viewport = ventana.view.viewport()
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(200, 300))
    for x in range(210, 360, 10):
        QTest.mouseMove(viewport, QPoint(x, 300 + (20 if (x // 10) % 2 else -20)))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, QPoint(360, 300))
    QApplication.processEvents()

    item = ventana.view._annotation_items()[0]
    antes = item.ann.bounds()
    ancho = antes[2] - antes[0]

    ventana.select_tool(Tool.SELECT)
    item.setSelected(True)
    centro = ventana.view.mapFromScene(item.sceneBoundingRect().center())
    QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, centro)
    for paso in range(1, 5):
        QTest.mouseMove(viewport, centro + QPoint(10 * paso, 5 * paso))
        QApplication.processEvents()
    QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, centro + QPoint(40, 20))
    QApplication.processEvents()

    despues = item.ann.bounds()
    escala = ventana.view.zoom * (ventana.view.logicalDpiX() / 72.0)
    assert despues[0] - antes[0] == pytest.approx(40 / escala, abs=3)
    assert despues[1] - antes[1] == pytest.approx(20 / escala, abs=3)
    assert (despues[2] - despues[0]) == pytest.approx(ancho, abs=0.5)
    assert item.scene() is not None and item.isVisible()


def test_la_punta_de_flecha_es_la_misma_en_pantalla_y_en_el_pdf(qapp):
    """La punta que se dibuja y la que se guarda tienen que medir lo mismo."""
    from easypdf.model import arrow_head

    ann = Annotation(kind=Kind.ARROW, page=0, p1=(20, 20), p2=(200, 100), width=3.0)
    item = create_item(ann)
    poligono, fin = item._arrow_points()
    _base, punta, izquierda, derecha = arrow_head(ann.p1, ann.p2, ann.width)
    assert (poligono[0].x(), poligono[0].y()) == pytest.approx(punta)
    assert (poligono[1].x(), poligono[1].y()) == pytest.approx(izquierda)
    assert (poligono[2].x(), poligono[2].y()) == pytest.approx(derecha)
    # el trazo termina dentro de la punta, no en el vertice
    assert fin.x() < punta[0] and fin.y() < punta[1]


def test_crear_una_tabla_y_escribir_en_sus_celdas(ventana, tmp_path):
    ventana.rows_spin.setValue(2)
    ventana.cols_spin.setValue(3)
    ventana.select_tool(Tool.TABLE)
    _arrastrar(ventana, (150, 200), (600, 320))

    tabla = ventana.view.selected_items()[0]
    assert tabla.ann.kind is Kind.TABLE
    assert tabla.ann.rows == 2 and tabla.ann.cols == 3
    assert len(tabla.local_cell_rects()) == 6
    assert tabla.is_editing  # entra directo a escribir en la primera celda

    for indice, texto in enumerate(["Concepto", "Cantidad", "Importe", "Gorras", "8", "64"]):
        tabla.edit_cell(indice)
        tabla._editor.setPlainText(texto)
    tabla.finish_editing()
    assert tabla.ann.cells[0] == "Concepto" and tabla.ann.cells[5] == "64"

    destino = tmp_path / "con-tabla.pdf"
    ventana.view.document.save_as(str(destino), ventana.view.annotations())
    pagina = pymupdf.open(str(destino))[0]
    tipos = [a.type[1] for a in pagina.annots()]
    assert tipos.count("Ink") == 1 and tipos.count("FreeText") == 6


def test_una_tabla_pequena_recibe_un_tamano_util(ventana):
    ventana.select_tool(Tool.TABLE)
    _arrastrar(ventana, (200, 300), (204, 303))
    tabla = ventana.view.selected_items()[0]
    x0, y0, x1, y1 = tabla.ann.normalized_rect()
    assert (x1 - x0) > 100 and (y1 - y0) > 40


def test_los_estilos_de_texto_se_aplican_a_la_seleccion(ventana):
    from easypdf.model import Align, Font

    ventana.select_tool(Tool.TEXT)
    _arrastrar(ventana, (150, 600), (420, 650))
    item = ventana.view.selected_items()[0]
    item.stop_editing()
    item.setSelected(True)

    ventana.font_combo.setCurrentIndex(ventana.font_combo.findData(Font.SERIF.value))
    ventana._set_bold(True)
    ventana._set_italic(True)
    ventana._set_align(Align.CENTER)

    assert item.ann.font is Font.SERIF
    assert item.ann.bold and item.ann.italic
    assert item.ann.align is Align.CENTER
    # y quedan guardados como preferencia para la siguiente anotacion
    assert ventana.view.style_defaults["bold"] is True


def test_cerrar_la_busqueda_quita_el_resaltado(ventana):
    ventana.search_edit.setText("EasyPDF")
    ventana.run_search()
    assert ventana.view.hit_count == 3
    assert ventana.view._search_items

    ventana.close_search()
    assert ventana.view.hit_count == 0
    assert ventana.view._search_items == []
    assert not ventana.toolbar_search.isVisible()

    # y tambien al vaciar el cuadro de busqueda
    ventana.search_edit.setText("EasyPDF")
    ventana.run_search()
    assert ventana.view.hit_count == 3
    ventana.search_edit.setText("")
    assert ventana.view.hit_count == 0


def test_colocar_una_imagen_arrastrandola_al_documento(ventana, sample_image, tmp_path):
    assert ventana.insert_image_from_file(sample_image)
    imagen = ventana.view._annotation_items()[0]
    assert imagen.ann.kind is Kind.IMAGE
    assert imagen.ann.image_name == "logo.png"
    x0, y0, x1, y1 = imagen.ann.normalized_rect()
    assert (x1 - x0) / (y1 - y0) == pytest.approx(200 / 120, rel=0.02)

    destino = tmp_path / "con-imagen.pdf"
    ventana.view.document.save_as(str(destino), ventana.view.annotations())
    assert len(pymupdf.open(str(destino))[0].get_images()) == 1


def test_la_imagen_conserva_la_proporcion_al_colocarla(ventana, sample_image_bytes):
    ventana.view.style_defaults["image"] = ("logo.png", sample_image_bytes)
    ventana.view.set_tool(Tool.IMAGE)
    _arrastrar(ventana, (200, 300), (500, 600))
    ann = ventana.view.annotations()[0]
    x0, y0, x1, y1 = ann.normalized_rect()
    assert (x1 - x0) / (y1 - y0) == pytest.approx(200 / 120, rel=0.02)


def test_redimensionar_una_imagen_por_la_esquina_mantiene_la_proporcion(
    ventana, sample_image
):
    ventana.insert_image_from_file(sample_image)
    imagen = ventana.view._annotation_items()[0]
    imagen.setSelected(True)
    from PySide6.QtCore import QPointF

    imagen.resize_to("br", QPointF(300, 500))
    assert imagen.rect().width() / imagen.rect().height() == pytest.approx(
        200 / 120, rel=0.02
    )


def test_crear_un_documento_en_blanco_y_anadir_paginas(ventana, tmp_path):
    ventana._modified = False
    ventana.view.undo_stack.setClean()
    ventana.new_document()
    assert ventana.view.page_count == 1
    assert "Documento nuevo" in ventana.windowTitle()

    ventana.view.add_annotation(
        Annotation(kind=Kind.TEXT, page=0, rect=(60, 60, 400, 110), text="Hola"),
        undoable=False,
    )
    ventana.add_page_end()
    ventana.add_page_end()
    assert ventana.view.page_count == 3

    ventana.duplicate_current_page()
    assert ventana.view.page_count == 4

    destino = tmp_path / "nuevo.pdf"
    ventana.view.document.save_as(str(destino), ventana.view.annotations())
    guardado = pymupdf.open(str(destino))
    assert guardado.page_count == 4
    assert len(list(guardado[0].annots())) == 1


def test_borrar_una_pagina_se_puede_deshacer(ventana):
    ventana.view.add_annotation(
        Annotation(kind=Kind.RECT, page=1, rect=(50, 50, 200, 150)), undoable=False
    )
    assert ventana.view.page_count == 3
    ventana.view.delete_page(1)
    assert ventana.view.page_count == 2
    assert ventana.view.annotation_count() == 0     # se va con su pagina

    ventana.view.undo_stack.undo()
    assert ventana.view.page_count == 3
    assert ventana.view.annotation_count() == 1
    assert ventana.view.annotations()[0].page == 1


def test_insertar_una_pagina_recoloca_las_anotaciones(ventana):
    ventana.view.add_annotation(
        Annotation(kind=Kind.RECT, page=2, rect=(50, 50, 200, 150)), undoable=False
    )
    ventana.view.add_page(0)
    assert ventana.view.annotations()[0].page == 3
    ventana.view.undo_stack.undo()
    assert ventana.view.annotations()[0].page == 2


def test_guardar_y_reutilizar_una_plantilla(ventana, tmp_path, sample_image_bytes):
    carpeta = tmp_path / "plantillas"
    ventana.templates_dir = lambda: str(carpeta)

    ventana.view.add_annotation(
        Annotation(kind=Kind.TEXT, page=0, rect=(50, 40, 500, 80), text="ACME", bold=True),
        undoable=False,
    )
    ventana.view.add_annotation(
        Annotation(
            kind=Kind.IMAGE, page=0, rect=(400, 300, 520, 380),
            image_data=sample_image_bytes, image_name="logo.png",
        ),
        undoable=False,
    )
    from easypdf.templates import list_templates, save_template

    ruta = save_template(
        str(carpeta), "Membrete", ventana.view.annotations(),
        ventana.view.document.page_sizes(),
    )
    assert [t.name for t in list_templates(str(carpeta))] == ["Membrete"]

    # aplicarla sobre el documento abierto, desde la pagina actual
    ventana.view.go_to_page(1)
    assert ventana.apply_template(ruta)
    assert ventana.view.annotation_count() == 4
    assert sorted({a.page for a in ventana.view.annotations()}) == [0, 1]
    # y un solo Ctrl+Z deshace toda la plantilla
    ventana.view.undo_stack.undo()
    assert ventana.view.annotation_count() == 2


def test_documento_nuevo_desde_una_plantilla(ventana, tmp_path):
    carpeta = tmp_path / "plantillas"
    ventana.templates_dir = lambda: str(carpeta)
    from easypdf.templates import save_template

    ruta = save_template(
        str(carpeta),
        "Dos paginas",
        [Annotation(kind=Kind.TEXT, page=1, rect=(50, 50, 400, 90), text="Anexo")],
        [(595, 842), (842, 595)],
    )
    ventana._modified = False
    ventana.view.undo_stack.setClean()
    assert ventana.new_from_template(ruta)
    assert ventana.view.page_count == 2
    assert [round(v) for v in ventana.view.document.page_size(1)] == [842, 595]
    assert ventana.view.annotation_count() == 1
    assert ventana.view.annotations()[0].page == 1


def test_cambiar_el_idioma_de_la_interfaz(ventana):
    """La ventana se retraduce entera sin reiniciar."""
    set_language("en")
    ventana.retranslate()
    assert ventana.act_save.text() == "&Save"
    assert [a.text() for a in ventana.menuBar().actions()][:2] == ["&File", "&Edit"]

    ventana.set_language("es")
    assert ventana.act_save.text() == "&Guardar"
    assert [a.text() for a in ventana.menuBar().actions()][:2] == ["&Archivo", "&Editar"]
    assert ventana.tool_actions[Tool.TABLE].text() == "Ta&bla"
    assert ventana.language_actions["es"].isChecked()
    assert ventana.settings.language() == "es"

    ventana.set_language("en")
    assert ventana.act_save.text() == "&Save"
    assert ventana.tool_actions[Tool.TABLE].text() == "Ta&ble"


# --------------------------------------------------------------------------
# Repintado: un item que dibuja fuera de su boundingRect() deja rastro en
# pantalla al arrastrarlo, porque Qt solo repinta el area que el item declara.
# --------------------------------------------------------------------------

ANOTACIONES_A_REPINTAR = {
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


@pytest.mark.parametrize("nombre", sorted(ANOTACIONES_A_REPINTAR))
def test_el_item_no_pinta_fuera_de_su_bounding_rect(qapp, nombre):
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem

    fondo = qcolor((1.0, 1.0, 1.0))
    margen = 40                       # cuanto se mira alrededor del boundingRect

    escena = QGraphicsScene()
    item = create_item(ANOTACIONES_A_REPINTAR[nombre].copy())
    escena.addItem(item)
    item.setSelected(True)            # peor caso: borde de seleccion y tiradores

    limites = item.boundingRect()
    zona = limites.adjusted(-margen, -margen, margen, margen)
    imagen = QImage(int(zona.width()), int(zona.height()), QImage.Format_RGB888)
    imagen.fill(fondo)
    painter = QPainter(imagen)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.translate(-zona.left(), -zona.top())
    item.paint(painter, QStyleOptionGraphicsItem(), None)
    painter.end()

    x0 = limites.left() - zona.left()
    y0 = limites.top() - zona.top()
    x1, y1 = x0 + limites.width(), y0 + limites.height()
    fuera = sum(
        1
        for y in range(imagen.height())
        for x in range(imagen.width())
        if not ((x0 - 1) <= x <= (x1 + 1) and (y0 - 1) <= y <= (y1 + 1))
        and imagen.pixelColor(x, y) != fondo
    )
    assert fuera == 0, f"{nombre} pinta {fuera} pixeles fuera de su boundingRect()"


# --------------------------------------------------------------------------
# Panel de miniaturas: reordenar arrastrando y menu contextual
# --------------------------------------------------------------------------

def _primera_linea(ventana, pagina):
    """Primera linea de texto de una pagina ('' si esta en blanco)."""
    lineas = ventana.view.document.page_text(pagina).strip().splitlines()
    return lineas[0] if lineas else ""


def test_arrastrar_una_miniatura_reordena_el_documento(ventana, qapp):
    assert ventana.view.page_count >= 3   # el PDF de prueba ya trae varias
    antes = [_primera_linea(ventana, i) for i in range(ventana.view.page_count)]

    ventana._on_thumbnail_dropped(0, 2)
    qapp.processEvents()
    despues = [_primera_linea(ventana, i) for i in range(ventana.view.page_count)]

    assert despues[2] == antes[0]
    assert sorted(despues) == sorted(antes)          # no se pierde ninguna
    assert ventana.view.current_page == 2

    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert [_primera_linea(ventana, i) for i in range(ventana.view.page_count)] == antes


def test_el_menu_de_una_miniatura_ofrece_todas_las_operaciones(ventana):
    _menu, acciones = ventana.build_page_menu(0)
    valores = set(acciones.values())
    # las de insertar llevan el tamano detras ("insert_after:A4"), asi que se
    # comparan por el prefijo
    familias = {v.split(":", 1)[0] for v in valores}
    assert familias == {
        "insert_before", "insert_after", "duplicate",
        "rotate_left", "rotate_right", "rotate_180",
        "up", "down", "delete",
    }


def test_insertar_y_duplicar_desde_el_menu_de_la_miniatura(ventana, qapp):
    total = ventana.view.page_count

    ventana.run_page_action("insert_after", 0)
    qapp.processEvents()
    assert ventana.view.page_count == total + 1
    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert ventana.view.page_count == total

    ventana.run_page_action("duplicate", 0)
    qapp.processEvents()
    assert ventana.view.page_count == total + 1
    assert _primera_linea(ventana, 1) == _primera_linea(ventana, 0)
    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert ventana.view.page_count == total


def test_girar_la_pagina_arrastra_consigo_las_anotaciones(ventana, qapp):
    ancho, alto = ventana.view.document.page_size(0)
    ann = Annotation(kind=Kind.RECT, page=0, rect=(50.0, 100.0, 150.0, 200.0), width=2)
    ventana.view.add_annotation(ann)
    qapp.processEvents()

    ventana.run_page_action("rotate_right", 0)
    qapp.processEvents()
    assert ventana.view.document.page_rotation(0) == 90
    assert ventana.view.document.page_size(0) == (alto, ancho)
    # la anotacion se ha movido, y sigue dentro de la pagina ya girada
    assert ann.rect != (50.0, 100.0, 150.0, 200.0)
    assert 0 <= ann.rect[0] and ann.rect[2] <= alto
    assert 0 <= ann.rect[1] and ann.rect[3] <= ancho

    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert ventana.view.document.page_rotation(0) == 0
    assert ventana.view.document.page_size(0) == (ancho, alto)
    assert ann.rect == (50.0, 100.0, 150.0, 200.0)


def test_girar_180_conserva_el_tamano_de_la_pagina(ventana, qapp):
    tamano = ventana.view.document.page_size(0)
    ventana.run_page_action("rotate_180", 0)
    qapp.processEvents()
    assert ventana.view.document.page_rotation(0) == 180
    assert ventana.view.document.page_size(0) == tamano


def test_insertar_una_pagina_permite_elegir_el_tamano(ventana, qapp):
    _menu, acciones = ventana.build_page_menu(0)
    opciones = {v for v in acciones.values() if v.startswith("insert_")}
    # "igual que esta pagina" mas cada tamano, por delante y por detras
    assert "insert_after:" in opciones
    assert "insert_after:A4" in opciones
    assert "insert_before:Carta" in opciones

    total = ventana.view.page_count
    ventana.run_page_action("insert_after:Carta", 0)
    qapp.processEvents()
    assert ventana.view.page_count == total + 1
    assert ventana.view.document.page_size(1) == (612.0, 792.0)

    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert ventana.view.page_count == total


def test_insertar_sin_tamano_copia_el_de_la_pagina_vecina(ventana, qapp):
    ventana.run_page_action("insert_before:", 0)
    qapp.processEvents()
    assert ventana.view.document.page_size(0) == ventana.view.document.page_size(1)


def test_los_tamanos_de_pagina_se_traducen(ventana):
    from easypdf.i18n import page_size_label

    set_language("en")
    assert page_size_label("Carta") == "Letter"
    assert page_size_label("Oficio") == "Legal"
    set_language("es")
    assert page_size_label("Carta") == "Carta"
    assert page_size_label("Oficio") == "Oficio"
    # un nombre desconocido se deja tal cual
    assert page_size_label("Cuartilla") == "Cuartilla"
    set_language("en")


def test_soltar_en_el_hueco_entre_miniaturas_no_manda_la_pagina_al_final(ventana, qapp):
    """Entre dos miniaturas hay un hueco de separacion.

    Soltar justo ahi es el gesto natural para decir "ponla aqui", pero
    indexAt() no devuelve nada en ese punto y antes se daba la posicion por
    perdida mandando la pagina al final de todas.
    """
    from PySide6.QtCore import QPoint

    lista = ventana.thumb_list
    assert lista.count() >= 3
    r0 = lista.visualRect(lista.model().index(0, 0))
    r1 = lista.visualRect(lista.model().index(1, 0))
    ultima = lista.count() - 1

    # el hueco entre la primera y la segunda
    hueco = QPoint(r0.center().x(), (r0.bottom() + r1.top()) // 2)
    assert not lista.indexAt(hueco).isValid()      # Qt no ve ninguna ahi
    destino = lista.drop_row(hueco)
    assert destino == 1, f"el hueco deberia dar la posicion 1, dio {destino}"
    assert destino != ultima or ultima == 1

    # por encima de la primera tampoco puede mandar al final
    encima = QPoint(r0.center().x(), max(0, r0.top() - 3))
    if not lista.indexAt(encima).isValid():
        assert lista.drop_row(encima) == 0


def test_el_destino_al_soltar_nunca_retrocede_al_bajar_el_raton(ventana):
    """Bajar el raton solo puede dar una posicion igual o mayor."""
    from PySide6.QtCore import QPoint

    lista = ventana.thumb_list
    r0 = lista.visualRect(lista.model().index(0, 0))
    r1 = lista.visualRect(lista.model().index(1, 0))
    x = r0.center().x()

    anterior = None
    for y in range(max(0, r0.top() - 4), r1.bottom() + 1, 3):
        destino = lista.drop_row(QPoint(x, y))
        if anterior is not None:
            assert destino >= anterior, f"en y={y} bajo de {anterior} a {destino}"
        anterior = destino


def test_soltar_sobre_una_miniatura_da_su_posicion_o_la_siguiente(ventana):
    lista = ventana.thumb_list
    for fila in range(min(3, lista.count())):
        centro = lista.visualRect(lista.model().index(fila, 0)).center()
        assert lista.drop_row(centro) in (fila, fila + 1)


# --------------------------------------------------------------------------
# Goma
# --------------------------------------------------------------------------

def test_ctrl_mas_y_menos_cambian_la_goma_cuando_esta_activa(ventana):
    from easypdf.model import ERASER_SIZES

    ventana.select_tool(Tool.ERASER)
    inicial = ventana.view.eraser_size
    zoom = ventana.view.zoom

    ventana.zoom_or_eraser(1)
    assert ventana.view.eraser_size > inicial
    assert ventana.view.zoom == zoom          # el zoom no se toca

    ventana.zoom_or_eraser(-1)
    assert ventana.view.eraser_size == inicial

    for _ in range(20):
        ventana.zoom_or_eraser(1)
    assert ventana.view.eraser_size == ERASER_SIZES[-1]
    for _ in range(20):
        ventana.zoom_or_eraser(-1)
    assert ventana.view.eraser_size == ERASER_SIZES[0]


def test_con_otra_herramienta_ctrl_mas_vuelve_a_ser_zoom(ventana):
    ventana.select_tool(Tool.SELECT)
    zoom, goma = ventana.view.zoom, ventana.view.eraser_size
    ventana.zoom_or_eraser(1)
    assert ventana.view.zoom > zoom
    assert ventana.view.eraser_size == goma


def _pasar_la_goma(ventana, puntos, pagina=0):
    """Simula una pasada de goma completa, con su paso de deshacer."""
    from PySide6.QtCore import QPointF

    from easypdf.ui.items import create_item

    vista = ventana.view
    ann = Annotation(
        kind=Kind.INK, page=pagina, color=tuple(vista.eraser_color),
        width=vista.eraser_size, opacity=1.0,
    )
    vista._erase_item = create_item(ann, vista._page_items[pagina])
    vista._erasing = True
    for x, y in puntos:
        vista.erase_at(pagina, QPointF(x, y))
    vista._finish_erase()
    return ann


def test_la_goma_pinta_encima_en_vez_de_quitar_anotaciones(ventana, qapp):
    """La goma tapa el documento, no borra lo que ya hay puesto."""
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0), width=2)
    ventana.view.add_annotation(caja)
    qapp.processEvents()
    total = len(ventana.view.store)

    ventana.select_tool(Tool.ERASER)
    trazo = _pasar_la_goma(ventana, [(120, 120), (140, 130), (160, 140)])
    qapp.processEvents()

    # la caja sigue ahi, y ademas hay un trazo nuevo que la tapa
    assert caja in list(ventana.view.store)
    assert len(ventana.view.store) == total + 1
    assert trazo.kind is Kind.INK
    assert trazo.opacity == 1.0


def test_la_goma_tapa_en_blanco_por_defecto(ventana, qapp):
    ventana.select_tool(Tool.ERASER)
    assert ventana.view.eraser_color == (1.0, 1.0, 1.0)
    trazo = _pasar_la_goma(ventana, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert trazo.color == (1.0, 1.0, 1.0)


def test_se_puede_elegir_el_color_de_la_goma(ventana, qapp):
    ventana.select_tool(Tool.ERASER)
    ventana.view.set_eraser_color((0.2, 0.4, 0.9))
    trazo = _pasar_la_goma(ventana, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert trazo.color == (0.2, 0.4, 0.9)


def test_el_trazo_de_la_goma_usa_el_tamano_elegido(ventana, qapp):
    ventana.select_tool(Tool.ERASER)
    ventana.view.set_eraser_size(36)
    trazo = _pasar_la_goma(ventana, [(100, 100), (150, 120)])
    qapp.processEvents()
    assert trazo.width == 36


def test_lo_que_pinta_la_goma_se_deshace_de_una_vez(ventana, qapp):
    ventana.select_tool(Tool.ERASER)
    total = len(ventana.view.store)
    _pasar_la_goma(ventana, [(100, 100), (120, 110), (140, 120), (160, 130)])
    qapp.processEvents()
    assert len(ventana.view.store) == total + 1

    ventana.view.undo_stack.undo()          # un solo Ctrl+Z para toda la pasada
    qapp.processEvents()
    assert len(ventana.view.store) == total


def test_un_toque_suelto_de_goma_no_deja_nada(ventana, qapp):
    ventana.select_tool(Tool.ERASER)
    total = len(ventana.view.store)
    pasos = ventana.view.undo_stack.count()
    _pasar_la_goma(ventana, [(100, 100)])   # un unico punto: no se dibuja
    qapp.processEvents()
    assert len(ventana.view.store) == total
    assert ventana.view.undo_stack.count() == pasos


def test_las_reglas_miden_desde_la_esquina_de_la_hoja(ventana, qapp):
    from PySide6.QtCore import QPointF

    from easypdf.ui.rulers import PT_PER_MM

    pagina = ventana.view.current_page_item()
    assert pagina is not None

    # el cero cae en la esquina superior izquierda de la pagina
    esquina = ventana.view.mapFromScene(pagina.scenePos())
    assert abs(ventana.ruler_h.value_at(esquina.x())) < 0.5
    assert abs(ventana.ruler_v.value_at(esquina.y())) < 0.5

    # y 100 x 50 mm dentro de la pagina se leen como 100 x 50
    punto = ventana.view.mapFromScene(
        pagina.mapToScene(QPointF(100 * PT_PER_MM, 50 * PT_PER_MM))
    )
    assert abs(ventana.ruler_h.value_at(punto.x()) - 100) < 0.6
    assert abs(ventana.ruler_v.value_at(punto.y()) - 50) < 0.6


def test_las_reglas_cambian_de_unidad(ventana):
    from PySide6.QtCore import QPointF

    from easypdf.ui.rulers import PT_PER_MM

    pagina = ventana.view.current_page_item()
    punto = ventana.view.mapFromScene(pagina.mapToScene(QPointF(100 * PT_PER_MM, 0)))

    ventana.set_ruler_unit("cm")
    assert abs(ventana.ruler_h.value_at(punto.x()) - 10) < 0.1
    ventana.set_ruler_unit("in")
    assert abs(ventana.ruler_h.value_at(punto.x()) - 100 / 25.4) < 0.05
    ventana.set_ruler_unit("pt")
    assert abs(ventana.ruler_h.value_at(punto.x()) - 100 * PT_PER_MM) < 1.0
    ventana.set_ruler_unit("mm")


def test_al_arrastrar_se_alinea_con_otra_anotacion(ventana, qapp):
    referencia = Annotation(kind=Kind.RECT, page=0, rect=(200.0, 200.0, 240.0, 260.0), width=2)
    ventana.view.add_annotation(referencia)
    movida = Annotation(kind=Kind.RECT, page=0, rect=(200.0, 400.0, 280.0, 450.0), width=2)
    ventana.view.add_annotation(movida)
    qapp.processEvents()

    item = ventana.view._items[movida.id]
    assert ventana.view.snap_enabled

    # se suelta 3 pt pasado el borde izquierdo de la otra: el iman lo pega
    item.setPos(item.pos().x() + 3.0, item.pos().y())
    qapp.processEvents()
    assert abs(movida.bounds()[0] - 200.0) < 0.01


def test_al_arrastrar_se_alinea_con_el_centro_de_la_hoja(ventana, qapp):
    ancho, _alto = ventana.view.document.page_size(0)
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 400.0, 180.0, 450.0), width=2)
    ventana.view.add_annotation(caja)
    qapp.processEvents()

    item = ventana.view._items[caja.id]
    medio = ancho / 2.0
    objetivo = medio - (caja.bounds()[2] - caja.bounds()[0]) / 2.0
    item.setPos(item.pos().x() + (objetivo - caja.bounds()[0]) + 2.0, item.pos().y())
    qapp.processEvents()

    centro = (caja.bounds()[0] + caja.bounds()[2]) / 2.0
    assert abs(centro - medio) < 0.01


def test_con_el_iman_apagado_no_se_alinea_nada(ventana, qapp):
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 400.0, 180.0, 450.0), width=2)
    ventana.view.add_annotation(caja)
    qapp.processEvents()

    ventana.view.set_snap(False)
    try:
        item = ventana.view._items[caja.id]
        antes = caja.bounds()[0]
        item.setPos(item.pos().x() + 3.0, item.pos().y())
        qapp.processEvents()
        assert abs(caja.bounds()[0] - (antes + 3.0)) < 0.01
    finally:
        ventana.view.set_snap(True)


def test_las_reglas_se_pueden_ocultar(ventana):
    ventana.toggle_rulers(False)
    assert not ventana.ruler_h.isVisible()
    assert not ventana.ruler_v.isVisible()
    ventana.toggle_rulers(True)
    assert ventana.ruler_h.isVisible()
