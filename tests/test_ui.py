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
