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


def test_soltar_donde_qt_no_ve_miniatura_no_manda_la_pagina_al_final(ventana, qapp):
    """El fallo original: si indexAt() no devolvia nada, drop_row daba la
    ultima posicion y la pagina se iba al final de todas.

    No se usan las medidas de los elementos, que cambian de un sistema a
    otro: se toma un punto claramente por encima de la primera miniatura,
    donde ninguna plataforma ve nada.
    """
    from PySide6.QtCore import QPoint

    lista = ventana.thumb_list
    assert lista.count() >= 3
    ultima = lista.count() - 1

    r0 = lista.visualRect(lista.model().index(0, 0))
    encima = QPoint(r0.center().x(), max(0, r0.top() - 40))
    assert not lista.indexAt(encima).isValid()     # aqui no hay ninguna

    destino = lista.drop_row(encima)
    assert destino == 0, f"por encima de la primera deberia dar 0, dio {destino}"
    assert destino != ultima


def test_la_miniatura_mas_cercana_se_busca_por_geometria(ventana):
    """La parte que arregla el fallo, sin depender de donde caiga el raton."""
    from PySide6.QtCore import QPoint

    lista = ventana.thumb_list
    r0 = lista.visualRect(lista.model().index(0, 0))
    r1 = lista.visualRect(lista.model().index(1, 0))

    assert lista.nearest_row(QPoint(r0.center().x(), r0.top() - 50)) == 0
    assert lista.nearest_row(r0.center()) == 0
    assert lista.nearest_row(r1.center()) == 1


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

    # se propone soltarla 3 pt pasado el borde izquierdo de la otra
    from PySide6.QtCore import QPointF

    propuesta = QPointF(item.pos().x() + 3.0, item.pos().y())
    ajustada = item.compute_snap(propuesta)
    item.setPos(ajustada)
    qapp.processEvents()
    assert abs(movida.bounds()[0] - 200.0) < 0.01


def test_al_arrastrar_se_alinea_con_el_centro_de_la_hoja(ventana, qapp):
    ancho, _alto = ventana.view.document.page_size(0)
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 400.0, 180.0, 450.0), width=2)
    ventana.view.add_annotation(caja)
    qapp.processEvents()

    from PySide6.QtCore import QPointF

    item = ventana.view._items[caja.id]
    medio = ancho / 2.0
    objetivo = medio - (caja.bounds()[2] - caja.bounds()[0]) / 2.0
    propuesta = QPointF(item.pos().x() + (objetivo - caja.bounds()[0]) + 2.0, item.pos().y())
    item.setPos(item.compute_snap(propuesta))
    qapp.processEvents()

    centro = (caja.bounds()[0] + caja.bounds()[2]) / 2.0
    assert abs(centro - medio) < 0.01


def test_con_el_iman_apagado_no_se_alinea_nada(ventana, qapp):
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 400.0, 180.0, 450.0), width=2)
    ventana.view.add_annotation(caja)
    qapp.processEvents()

    ventana.view.set_snap(False)
    try:
        from PySide6.QtCore import QPointF

        item = ventana.view._items[caja.id]
        antes = caja.bounds()[0]
        item.setPos(item.compute_snap(QPointF(item.pos().x() + 3.0, item.pos().y())))
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


def test_colocar_una_anotacion_no_deja_guias_pintadas(ventana, qapp):
    """El iman solo actua al arrastrar con el raton.

    Si actuara tambien al crear o cargar anotaciones, quedarian guias rosas
    dibujadas en la pagina sin que nadie este moviendo nada.
    """
    ventana.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0), width=2)
    )
    qapp.processEvents()
    assert ventana.view._guides == (None, None, None)

    ventana.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(103.0, 400.0, 180.0, 450.0), width=2)
    )
    qapp.processEvents()
    assert ventana.view._guides == (None, None, None)


# --------------------------------------------------------------------------
# Tablas
# --------------------------------------------------------------------------

def _tabla(ventana, qapp, alineacion=Align.CENTER):
    ann = Annotation(
        kind=Kind.TABLE, page=0, rect=(80.0, 150.0, 460.0, 290.0), rows=3, cols=3,
        cells=["Nombre", "Cantidad", "Precio", "Tornillo", "120", "3,50",
               "Tuerca", "80", "1,20"],
        align=alineacion, width=1,
    )
    ventana.view.add_annotation(ann)
    qapp.processEvents()
    return ann, ventana.view._items[ann.id]


def test_el_editor_de_celda_usa_la_alineacion_de_la_tabla(ventana, qapp):
    """Si no, el texto se ve a la izquierda al escribir y salta al terminar."""
    from PySide6.QtCore import Qt

    ann, item = _tabla(ventana, qapp, Align.CENTER)
    item.edit_cell(4)
    qapp.processEvents()
    try:
        alineacion = item._editor.document().defaultTextOption().alignment()
        assert alineacion == Qt.AlignHCenter
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


def test_el_editor_de_celda_ocupa_el_mismo_sitio_que_el_texto_pintado(ventana, qapp):
    from easypdf.ui.items import CELL_PADDING

    _ann, item = _tabla(ventana, qapp)
    celda = item.local_cell_rects()[4]
    item.edit_cell(4)
    qapp.processEvents()
    try:
        editor = item._editor
        assert abs(editor.pos().x() - (celda.left() + CELL_PADDING)) < 0.01
        assert abs(editor.pos().y() - (celda.top() + CELL_PADDING)) < 0.01
        assert abs(editor.textWidth() - (celda.width() - 2 * CELL_PADDING)) < 0.01
    finally:
        item.finish_editing()
        qapp.processEvents()


def test_se_puede_borrar_una_tabla_con_del_despues_de_editarla(ventana, qapp):
    """Tras editar una celda y pulsar Escape, DEL tiene que borrar la tabla.

    El editor de la celda se quedaba vivo con el foco y se comia la tecla.
    """
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    _ann, item = _tabla(ventana, qapp)
    total = len(ventana.view.store)

    item.edit_cell(1)
    qapp.processEvents()
    ventana.view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    qapp.processEvents()
    assert not ventana.view._text_editing

    item.setSelected(True)
    ventana.view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
    qapp.processEvents()
    assert len(ventana.view.store) == total - 1

    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert len(ventana.view.store) == total


def test_la_tabla_se_dibuja_en_cache_para_que_arrastrarla_no_la_repinte(ventana, qapp):
    from PySide6.QtWidgets import QGraphicsItem

    _ann, item = _tabla(ventana, qapp)
    assert item.cacheMode() == QGraphicsItem.DeviceCoordinateCache


def test_los_rectangulos_de_celda_se_memorizan_y_se_rehacen_al_cambiar(ventana, qapp):
    ann, item = _tabla(ventana, qapp)
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


def test_el_aviso_de_version_ofrece_descargar_esperar_o_saltar(ventana, monkeypatch):
    from PySide6.QtWidgets import QPushButton

    from easypdf import __version__
    from easypdf.i18n import tr
    from easypdf.ui.update_download import UpdateDialog

    visto = {}

    def falso_exec(self):
        visto["texto"] = self.texto.text()
        visto["botones"] = [b.text() for b in self.findChildren(QPushButton)]
        return 0

    monkeypatch.setattr(UpdateDialog, "exec", falso_exec)
    ventana.settings.set_value("updates/skip", "")
    ventana._update_manual = False
    ventana._on_update_result(dict(NOVEDAD))

    assert "9.9.9" in visto["texto"]
    assert __version__ in visto["texto"]
    # Lo que se pidio: bajarla desde aqui, sin tener que ir a la web a mano.
    assert tr("update_download") in visto["botones"]
    assert tr("update_go") in visto["botones"]
    assert tr("update_later") in visto["botones"]
    assert tr("update_skip") in visto["botones"]


def test_saltar_la_version_desde_el_aviso_queda_apuntado(ventana, monkeypatch):
    from easypdf.ui.update_download import UpdateDialog

    def falso_exec(self):
        self.skipped = True               # como pulsar "Saltar esta version"
        return 0

    monkeypatch.setattr(UpdateDialog, "exec", falso_exec)
    ventana.settings.set_value("updates/skip", "")
    ventana._update_manual = True
    ventana._on_update_result(dict(NOVEDAD))
    assert ventana.settings.value("updates/skip", "") == "9.9.9"
    ventana.settings.set_value("updates/skip", "")


def test_no_se_avisa_dos_veces_de_una_version_saltada(ventana, monkeypatch):
    from easypdf.ui.update_download import UpdateDialog

    visto = {}
    monkeypatch.setattr(UpdateDialog, "exec",
                        lambda self: visto.setdefault("texto", self.texto.text()) or 0)

    ventana.settings.set_value("updates/skip", "9.9.9")
    ventana._update_manual = False
    ventana._on_update_result(dict(NOVEDAD))
    assert "texto" not in visto           # en el arranque no molesta

    ventana._update_manual = True         # pero si la busca a mano, si
    ventana._on_update_result(dict(NOVEDAD))
    assert "9.9.9" in visto.get("texto", "")
    ventana.settings.set_value("updates/skip", "")


def test_instalar_cierra_el_programa_y_arranca_el_instalador(ventana, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from easypdf import updates
    from easypdf.ui.main_window import MainWindow

    arrancados = []
    monkeypatch.setattr(updates, "launch_installer", arrancados.append)
    monkeypatch.setattr(MainWindow, "close", lambda self: True)
    monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: None))

    assert ventana.install_update("C:/tmp/EasyPDF-9.9.9-Setup.exe")
    assert arrancados == ["C:/tmp/EasyPDF-9.9.9-Setup.exe"]


def test_si_no_se_puede_cerrar_no_se_instala_nada(ventana, monkeypatch):
    """Con cambios sin guardar el usuario puede cancelar: entonces no se toca nada."""
    from easypdf import updates
    from easypdf.ui.main_window import MainWindow

    arrancados = []
    monkeypatch.setattr(updates, "launch_installer", arrancados.append)
    monkeypatch.setattr(MainWindow, "close", lambda self: False)

    assert not ventana.install_update("C:/tmp/EasyPDF-9.9.9-Setup.exe")
    assert arrancados == []


def test_sin_novedad_solo_avisa_si_lo_pidio_el_usuario(ventana, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    llamadas = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: llamadas.append(a)))

    ventana._update_manual = False
    ventana._on_update_result(None)
    assert not llamadas                    # al arrancar, en silencio

    ventana._update_manual = True
    ventana._on_update_result(None)
    assert llamadas                        # buscando a mano, contesta


def test_el_aviso_al_arrancar_se_puede_desactivar(ventana):
    ventana.act_update_auto.setChecked(False)
    assert ventana.settings.value("updates/auto", True, type_=bool) is False
    ventana.act_update_auto.setChecked(True)
    assert ventana.settings.value("updates/auto", True, type_=bool) is True


# --------------------------------------------------------------------------
# Guias sacadas de las reglas
# --------------------------------------------------------------------------

def test_arrastrar_desde_la_regla_deja_una_guia(ventana):
    vista = ventana.view
    vista.start_guide("h", 200.0)
    vista.move_guide(250.0)
    vista.drop_guide(250.0)
    assert vista.page_guides(0)["h"] == [250.0]

    vista.start_guide("v", 100.0)
    vista.drop_guide(150.0)
    assert vista.page_guides(0)["v"] == [150.0]


def test_soltar_la_guia_fuera_de_la_pagina_no_la_crea(ventana):
    vista = ventana.view
    _ancho, alto = vista.document.page_size(0)

    vista.start_guide("h", 100.0)
    vista.drop_guide(alto + 50)
    assert vista.page_guides(0)["h"] == []

    vista.start_guide("h", 100.0)
    vista.drop_guide(-25.0)
    assert vista.page_guides(0)["h"] == []


def test_una_guia_se_mueve_y_sacandola_fuera_se_borra(ventana):
    vista = ventana.view
    vista.start_guide("h", 300.0)
    vista.drop_guide(300.0)

    vista.grab_guide("h", 0, 0, 300.0)
    vista.drop_guide(420.0)
    assert vista.page_guides(0)["h"] == [420.0]

    vista.grab_guide("h", 0, 0, 420.0)
    vista.drop_guide(-30.0)              # fuera del margen: se borra
    assert vista.page_guides(0)["h"] == []


def test_se_encuentra_la_guia_que_hay_bajo_el_raton(ventana):
    from PySide6.QtCore import QPointF

    vista = ventana.view
    vista.start_guide("h", 300.0)
    vista.drop_guide(300.0)
    pagina = vista._page_items[0]

    encima = pagina.mapToScene(QPointF(100.0, 300.0))
    hallada = vista.guide_at(encima)
    assert hallada is not None
    assert hallada[0] == "h" and hallada[3] == 300.0

    assert vista.guide_at(pagina.mapToScene(QPointF(100.0, 520.0))) is None


def test_las_anotaciones_se_alinean_con_las_guias(ventana, qapp):
    from PySide6.QtCore import QPointF

    vista = ventana.view
    vista.start_guide("v", 150.0)
    vista.drop_guide(150.0)

    caja = Annotation(kind=Kind.RECT, page=0, rect=(300.0, 400.0, 380.0, 450.0), width=2)
    vista.add_annotation(caja)
    qapp.processEvents()

    item = vista._items[caja.id]
    desfase = 150.0 - caja.bounds()[0] + 2.5      # casi encima de la guia
    item.setPos(item.compute_snap(QPointF(item.pos().x() + desfase, item.pos().y())))
    qapp.processEvents()
    assert abs(caja.bounds()[0] - 150.0) < 0.01


def test_se_pueden_quitar_todas_las_guias(ventana):
    vista = ventana.view
    vista.start_guide("h", 200.0)
    vista.drop_guide(200.0)
    vista.start_guide("v", 200.0)
    vista.drop_guide(200.0)
    assert vista.page_guides(0)["h"] and vista.page_guides(0)["v"]

    ventana._clear_guides()
    assert vista.page_guides(0)["h"] == []
    assert vista.page_guides(0)["v"] == []


# --------------------------------------------------------------------------
# Panel de plantillas
# --------------------------------------------------------------------------

def _hojas_de_plantilla(ventana):
    """Las plantillas del arbol, sin los titulos de grupo."""
    salida = []
    arbol = ventana.tpl_tree
    for i in range(arbol.topLevelItemCount()):
        grupo = arbol.topLevelItem(i)
        for j in range(grupo.childCount()):
            rama = grupo.child(j)
            for k in range(rama.childCount()):
                salida.append((grupo.text(0), rama.text(0), rama.child(k)))
    return salida


def test_el_panel_ensena_las_plantillas_de_serie_por_tipo(ventana):
    hojas = _hojas_de_plantilla(ventana)
    assert len(hojas) >= 4
    assert len({rama for _g, rama, _i in hojas}) >= 3   # varios tipos


def test_una_plantilla_de_serie_se_aplica_sobre_el_documento(ventana, qapp):
    hojas = _hojas_de_plantilla(ventana)
    from easypdf.templates import builtin_infos

    # se busca por su rama, no por el nombre: cambia con el idioma
    primera = builtin_infos()[0].name
    membrete = next(i for _g, _r, i in hojas if primera in i.text(0))
    ventana.tpl_tree.setCurrentItem(membrete)
    assert ventana.btn_tpl_use.isEnabled()

    antes = len(ventana.view.store)
    assert ventana.use_selected_template()
    qapp.processEvents()
    assert len(ventana.view.store) > antes


def test_las_de_serie_no_se_pueden_borrar(ventana):
    hojas = _hojas_de_plantilla(ventana)
    ventana.tpl_tree.setCurrentItem(hojas[0][2])
    assert not ventana.btn_tpl_del.isEnabled()
    assert ventana.delete_selected_template() is False


def test_documento_nuevo_desde_una_plantilla_de_serie(ventana, qapp):
    hojas = _hojas_de_plantilla(ventana)
    from easypdf.templates import builtin_infos

    con_tabla = next(i.name for i in builtin_infos() if i.category == "table"
                     and i.annotations > 5)
    acta = next(i for _g, _r, i in hojas if con_tabla in i.text(0))
    ventana.tpl_tree.setCurrentItem(acta)

    ventana._modified = False
    ventana.view.undo_stack.setClean()
    assert ventana.new_from_selected_template()
    qapp.processEvents()

    tipos = {a.kind for a in ventana.view.store}
    assert Kind.TABLE in tipos and Kind.TEXT in tipos


def test_guardar_y_borrar_una_plantilla_propia_desde_el_panel(ventana, qapp, tmp_path,
                                                              monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    monkeypatch.setattr(ventana, "templates_dir", lambda: str(tmp_path))
    monkeypatch.setattr(ventana, "_ensure_templates_dir", lambda: str(tmp_path))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Mi informe", True)))
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: (a[3][0], True)))

    ventana.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(10.0, 10.0, 90.0, 60.0), width=2)
    )
    qapp.processEvents()
    assert ventana.save_as_template()

    ventana.refresh_templates()
    mias = [i for _g, _r, i in _hojas_de_plantilla(ventana) if "Mi informe" in i.text(0)]
    assert len(mias) == 1

    ventana.tpl_tree.setCurrentItem(mias[0])
    assert ventana.btn_tpl_del.isEnabled()     # la propia si se borra
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    assert ventana.delete_selected_template()
    assert not [i for _g, _r, i in _hojas_de_plantilla(ventana)
                if "Mi informe" in i.text(0)]


def test_la_regla_ensena_donde_estan_las_guias(ventana, qapp):
    """Una guia horizontal se mide en la regla vertical, y al reves."""
    vista = ventana.view
    vista.start_guide("v", 150.0)      # linea vertical: va en la regla de arriba
    vista.drop_guide(150.0)
    qapp.processEvents()

    origen = vista.current_page_item().scenePos()
    esperado = ventana.ruler_h._guide_pixel(150.0, origen.x())
    real = ventana.ruler_h.value_at(esperado)
    assert real is not None
    from easypdf.ui.rulers import PT_PER_MM
    assert abs(real - 150.0 / PT_PER_MM) < 0.6


def test_al_mover_una_guia_se_ensena_su_medida(ventana, qapp):
    vista = ventana.view
    vista.start_guide("h", 200.0)
    vista.drop_guide(200.0)
    qapp.processEvents()

    vista.grab_guide("h", 0, 0, 200.0)
    vista.move_guide(300.0)
    qapp.processEvents()

    mensaje = ventana.statusBar().currentMessage()
    assert mensaje, "no se dijo donde esta la guia"
    # 300 pt son unos 105,8 mm
    assert "105" in mensaje or "106" in mensaje, mensaje
    vista.drop_guide(300.0)


def test_las_reglas_se_repintan_al_tocar_las_guias(ventana, qapp):
    """Sin este aviso, la marca de la regla no se movia con la guia."""
    avisos = []
    ventana.view.guidesChanged.connect(lambda: avisos.append(1))

    ventana.view.start_guide("h", 100.0)
    ventana.view.move_guide(150.0)
    ventana.view.drop_guide(150.0)
    assert len(avisos) >= 3


# -- copiar y pegar -------------------------------------------------------
def _vaciar_portapapeles():
    from PySide6.QtGui import QGuiApplication

    portapapeles = QGuiApplication.clipboard()
    if portapapeles is not None:
        portapapeles.clear()


def _seleccionar(ventana, *anotaciones):
    vista = ventana.view
    for item in vista.selected_items():
        item.setSelected(False)
    for ann in anotaciones:
        vista._items[ann.id].setSelected(True)


def test_copiar_y_pegar_duplica_lo_seleccionado(ventana, qapp):
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    ventana.view.add_annotation(caja)
    qapp.processEvents()
    _seleccionar(ventana, caja)

    assert ventana.view.copy_selected() == 1
    assert ventana.view.paste_clipboard() == 1
    qapp.processEvents()

    copias = [a for a in ventana.view.annotations() if a.id != caja.id]
    assert len(copias) == 1
    copia = copias[0]
    assert copia.id != caja.id                 # es otra anotacion, no la misma
    assert copia.kind is Kind.RECT
    salto = ventana.view.PASTE_OFFSET
    assert copia.rect == (100 + salto, 100 + salto, 200 + salto, 160 + salto)
    # y queda seleccionada, lista para moverla
    assert [i.ann for i in ventana.view.selected_items()] == [copia]


def test_pegar_arrastra_todo_lo_que_define_la_anotacion(ventana, qapp):
    """Una linea no vive en su rectangulo: hay que mover tambien sus extremos."""
    linea = Annotation(kind=Kind.LINE, page=0, p1=(50.0, 300.0), p2=(250.0, 380.0))
    trazo = Annotation(kind=Kind.INK, page=0, strokes=[[(10.0, 20.0), (30.0, 40.0)]])
    ventana.view.add_annotation(linea)
    ventana.view.add_annotation(trazo)
    qapp.processEvents()
    _seleccionar(ventana, linea, trazo)
    assert ventana.view.copy_selected() == 2
    assert ventana.view.paste_clipboard() == 2
    qapp.processEvents()

    salto = ventana.view.PASTE_OFFSET
    nuevas = [a for a in ventana.view.annotations() if a.id not in (linea.id, trazo.id)]
    copia_linea = next(a for a in nuevas if a.kind is Kind.LINE)
    copia_trazo = next(a for a in nuevas if a.kind is Kind.INK)
    assert copia_linea.p1 == (50 + salto, 300 + salto)
    assert copia_linea.p2 == (250 + salto, 380 + salto)
    assert copia_trazo.strokes == [[(10 + salto, 20 + salto), (30 + salto, 40 + salto)]]


def test_pegar_una_tabla_conserva_su_contenido(ventana, qapp):
    tabla = Annotation(kind=Kind.TABLE, page=0, rect=(60.0, 60.0, 400.0, 200.0),
                       rows=2, cols=2, cells=["a", "b", "c", "d"], font_size=9.0)
    ventana.view.add_annotation(tabla)
    qapp.processEvents()
    _seleccionar(ventana, tabla)
    ventana.view.copy_selected()
    ventana.view.paste_clipboard()
    qapp.processEvents()

    copia = next(a for a in ventana.view.annotations() if a.id != tabla.id)
    assert (copia.rows, copia.cols) == (2, 2)
    assert copia.cells == ["a", "b", "c", "d"]
    assert copia.font_size == 9.0


def test_pegar_dos_veces_no_deja_una_copia_encima_de_otra(ventana, qapp):
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    ventana.view.add_annotation(caja)
    qapp.processEvents()
    _seleccionar(ventana, caja)
    ventana.view.copy_selected()
    ventana.view.paste_clipboard()
    ventana.view.paste_clipboard()
    qapp.processEvents()

    esquinas = sorted(a.rect[0] for a in ventana.view.annotations() if a.kind is Kind.RECT)
    salto = ventana.view.PASTE_OFFSET
    assert esquinas == [100.0, 100 + salto, 100 + 2 * salto]


def test_una_pegada_entera_se_deshace_de_una_vez(ventana, qapp):
    """Pegar tres cosas es un solo paso de deshacer, no tres."""
    originales = [
        Annotation(kind=Kind.RECT, page=0, rect=(10.0, 10.0, 60.0, 60.0)),
        Annotation(kind=Kind.RECT, page=0, rect=(80.0, 10.0, 130.0, 60.0)),
        Annotation(kind=Kind.RECT, page=0, rect=(150.0, 10.0, 200.0, 60.0)),
    ]
    for ann in originales:
        ventana.view.add_annotation(ann)
    qapp.processEvents()
    _seleccionar(ventana, *originales)
    ventana.view.copy_selected()
    assert ventana.view.paste_clipboard() == 3
    qapp.processEvents()
    assert ventana.view.annotation_count() == 6

    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert ventana.view.annotation_count() == 3


def test_cortar_copia_y_quita_lo_seleccionado(ventana, qapp):
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    ventana.view.add_annotation(caja)
    qapp.processEvents()
    _seleccionar(ventana, caja)

    assert ventana.view.cut_selected() == 1
    qapp.processEvents()
    assert ventana.view.annotation_count() == 0

    assert ventana.view.paste_clipboard() == 1     # seguia en el portapapeles
    qapp.processEvents()
    assert ventana.view.annotation_count() == 1


def test_sin_nada_copiado_pegar_no_hace_nada(ventana, qapp):
    _vaciar_portapapeles()
    antes = ventana.view.annotation_count()
    assert ventana.view.paste_clipboard() == 0
    assert ventana.view.annotation_count() == antes


def test_se_pega_en_la_pagina_que_se_esta_viendo(ventana, qapp):
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    ventana.view.add_annotation(caja)
    qapp.processEvents()
    _seleccionar(ventana, caja)
    ventana.view.copy_selected()

    assert ventana.view.paste_clipboard(page=2) == 1
    qapp.processEvents()
    copia = next(a for a in ventana.view.annotations() if a.id != caja.id)
    assert copia.page == 2


def test_copiar_y_pegar_no_roban_el_atajo_mientras_se_escribe(ventana, qapp):
    """Dentro de un texto, Ctrl+C y Ctrl+V son los del editor, no los nuestros."""
    texto = Annotation(kind=Kind.TEXT, page=0, rect=(80.0, 80.0, 300.0, 130.0),
                       text="hola")
    item = ventana.view.add_annotation(texto)
    qapp.processEvents()
    _seleccionar(ventana, texto)
    ventana._update_actions()
    assert ventana.act_copy.isEnabled()
    assert ventana.act_paste.isEnabled()

    item.start_editing()
    qapp.processEvents()
    ventana._update_actions()
    assert not ventana.act_copy.isEnabled()
    assert not ventana.act_cut.isEnabled()
    assert not ventana.act_paste.isEnabled()
    ventana.view.finish_all_editing()
    qapp.processEvents()


def test_los_atajos_de_teclado_copian_y_pegan(ventana, qapp):
    """Lo que se pidio: Ctrl+C y Ctrl+V, no solo el menu."""
    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 200.0, 160.0))
    ventana.view.add_annotation(caja)
    qapp.processEvents()
    _seleccionar(ventana, caja)
    ventana._update_actions()

    QTest.keyClick(ventana, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(ventana, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    assert ventana.view.annotation_count() == 2

    _seleccionar(ventana, caja)
    ventana._update_actions()
    QTest.keyClick(ventana, Qt.Key_X, Qt.ControlModifier)
    qapp.processEvents()
    assert ventana.view.annotation_count() == 1


def test_lo_copiado_por_otro_programa_no_se_pega(ventana, qapp):
    """Un texto cualquiera del portapapeles no puede convertirse en anotaciones."""
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText("una nota que copie de otro sitio")
    antes = ventana.view.annotation_count()
    assert ventana.view.paste_clipboard() == 0
    assert ventana.view.annotation_count() == antes


# -- la goma se queda dentro de la hoja -----------------------------------
def _claros_fuera_de_la_pagina(ventana, pagina: int = 0, margen: int = 40) -> int:
    """Cuenta los pixeles claros pintados en el borde de fuera del papel.

    Se pinta una franja alrededor de la hoja y se miran solo esos pixeles: es
    donde se veria lo que se sale. El documento tiene mas paginas, asi que las
    que caigan dentro de la franja se descuentan; son papel tambien.
    """
    from PySide6.QtCore import QRect, QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    vista = ventana.view
    papel = vista._page_items[pagina].mapRectToScene(
        vista._page_items[pagina].boundingRect()
    )
    zona = papel.adjusted(-margen, -margen, margen, margen)
    imagen = QImage(int(zona.width()), int(zona.height()), QImage.Format_RGB32)
    imagen.fill(QColor("#404040"))
    pintor = QPainter(imagen)
    vista.scene().render(pintor, QRectF(imagen.rect()), zona)
    pintor.end()

    # El borde de la propia hoja va suavizado: dos pixeles de respeto.
    dentro = papel.translated(-zona.x(), -zona.y()).adjusted(-2, -2, 2, 2)
    otras = [
        item.mapRectToScene(item.boundingRect())
        .translated(-zona.x(), -zona.y())
        .adjusted(-2, -2, 2, 2)
        for i, item in enumerate(vista._page_items) if i != pagina
    ]
    ancho, alto = imagen.width(), imagen.height()
    franjas = [
        QRect(0, 0, ancho, margen),                       # arriba
        QRect(0, alto - margen, ancho, margen),           # abajo
        QRect(0, 0, margen, alto),                        # izquierda
        QRect(ancho - margen, 0, margen, alto),           # derecha
    ]
    vistos, claros = set(), 0
    for franja in franjas:
        for y in range(franja.top(), franja.bottom() + 1):
            for x in range(franja.left(), franja.right() + 1):
                if (x, y) in vistos or not imagen.rect().contains(x, y):
                    continue
                vistos.add((x, y))
                if dentro.contains(x, y) or any(r.contains(x, y) for r in otras):
                    continue
                if QColor(imagen.pixel(x, y)).lightness() > 200:
                    claros += 1
    return claros


def test_la_goma_no_pinta_fuera_de_la_hoja(ventana, qapp):
    """Sacando la goma de la pagina se comia el fondo gris de alrededor."""
    ventana.select_tool(Tool.ERASER)
    ventana.view.set_eraser_size(24)
    _pasar_la_goma(ventana, [(200, 200), (50, 100), (-150, -80), (-200, 300)])
    qapp.processEvents()
    assert _claros_fuera_de_la_pagina(ventana) == 0


def test_una_anotacion_tampoco_se_pinta_fuera_de_la_hoja(ventana, qapp):
    """Lo que sale del papel no se imprime, asi que tampoco se ve en pantalla."""
    ventana.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(-200.0, 100.0, 300.0, 200.0),
                   color=(1.0, 1.0, 1.0), fill=(1.0, 1.0, 1.0), width=3)
    )
    qapp.processEvents()
    assert _claros_fuera_de_la_pagina(ventana) == 0


# -- DEL y el aviso de que no hay nada seleccionado -----------------------
def test_del_avisa_en_vez_de_no_hacer_nada_con_otra_herramienta(ventana, qapp):
    """Con la goma activa no se puede seleccionar, y DEL se quedaba mudo."""
    ventana.select_tool(Tool.ERASER)
    _pasar_la_goma(ventana, [(120, 150), (200, 150)])
    qapp.processEvents()
    ventana._update_actions()

    # La accion tiene que seguir activa: si se desactiva, el atajo ni se
    # dispara y el usuario no se entera de nada.
    assert ventana.act_delete.isEnabled()
    ventana.statusBar().clearMessage()
    ventana.delete_selection()
    assert ventana.statusBar().currentMessage() == tr("status_pick_select")


def test_con_seleccionar_activo_el_aviso_es_el_de_siempre(ventana, qapp):
    ventana.select_tool(Tool.SELECT)
    ventana.view.scene().clearSelection()
    qapp.processEvents()
    ventana.statusBar().clearMessage()
    ventana.delete_selection()
    assert ventana.statusBar().currentMessage() == tr("status_no_selection")


def test_tras_la_goma_se_puede_volver_a_seleccionar_y_borrar(ventana, qapp):
    """El camino completo del que se quejaba el usuario, de punta a punta."""
    from PySide6.QtCore import QPointF

    caja = Annotation(kind=Kind.RECT, page=0, rect=(100.0, 100.0, 300.0, 200.0))
    ventana.view.add_annotation(caja)
    ventana.select_tool(Tool.ERASER)
    _pasar_la_goma(ventana, [(120, 150), (280, 150)])
    qapp.processEvents()
    assert ventana.view.annotation_count() == 2

    QTest.keyClick(ventana.view.viewport(), Qt.Key_Escape)
    qapp.processEvents()
    assert ventana.view.tool is Tool.SELECT

    pagina = ventana.view._page_items[0]
    punto = ventana.view.mapFromScene(pagina.mapToScene(QPointF(200.0, 150.0)))
    QTest.mouseClick(ventana.view.viewport(), Qt.LeftButton, Qt.NoModifier, punto)
    qapp.processEvents()
    assert ventana.view.selected_items()
    ventana._update_actions()
    QTest.keyClick(ventana, Qt.Key_Delete)
    qapp.processEvents()
    assert ventana.view.annotation_count() == 1


# -- el acerca de y las licencias ----------------------------------------
def test_el_acerca_de_no_lleva_la_letra_pequena_de_las_bibliotecas():
    """Se pidio quitarla de ahi; sigue estando, pero en su propia ventana."""
    texto = tr("about_html", url="https://easypdf.surf")
    assert "PySide6" not in texto
    assert "PyMuPDF" not in texto
    assert "warranty" not in texto.lower()


def test_las_licencias_siguen_estando_a_un_clic(ventana, qapp):
    """PySide6 es LGPL: hay que avisar de que se usa y bajo que licencia."""
    from easypdf.ui.main_window import AboutDialog, LicencesDialog

    licencias = tr("licences_html")
    assert "PySide6" in licencias and "LGPL" in licencias
    assert "PyMuPDF" in licencias and "AGPL" in licencias

    dialogo = AboutDialog(ventana)
    try:
        from PySide6.QtWidgets import QPushButton

        botones = [b.text() for b in dialogo.findChildren(QPushButton)]
        assert tr("about_licences") in botones
    finally:
        dialogo.deleteLater()

    ventana_licencias = LicencesDialog(ventana)
    try:
        assert ventana_licencias.windowTitle() == tr("licences_title")
    finally:
        ventana_licencias.deleteLater()


# -- el panel de plantillas ----------------------------------------------
def test_el_panel_lateral_cabe_para_el_arbol_de_plantillas(ventana, qapp):
    """Con 190 px el arbol ensenaba tres filas y el boton de guardar no se veia."""
    qapp.processEvents()
    assert ventana.side_tabs.minimumHeight() >= 300
    assert ventana.bookmark_dock.height() >= 300


def test_el_panel_de_plantillas_tiene_su_boton_de_guardar(ventana, qapp):
    ventana.side_tabs.setCurrentIndex(2)
    qapp.processEvents()
    ventana._update_template_buttons()
    assert ventana.btn_tpl_save.text() == tr("tpl_save")
    assert ventana.btn_tpl_save.isEnabled()      # hay documento abierto


def test_una_plantilla_nueva_se_guarda_en_la_carpeta_templates(ventana, tmp_path, monkeypatch):
    """Lo guardado tiene que acabar en Templates, no en cualquier sitio."""
    import os

    from easypdf.templates import list_templates

    monkeypatch.setattr(type(ventana), "templates_dir",
                        lambda self: str(tmp_path / "AppData" / "Templates"))
    ventana.view.add_annotation(
        Annotation(kind=Kind.RECT, page=0, rect=(60.0, 60.0, 500.0, 120.0))
    )
    monkeypatch.setattr("easypdf.ui.main_window.QInputDialog.getText",
                        staticmethod(lambda *a, **k: ("Mi membrete", True)))
    monkeypatch.setattr("easypdf.ui.main_window.QInputDialog.getItem",
                        staticmethod(lambda *a, **k: (tr("cat_letterhead"), True)))

    assert ventana.save_as_template()
    carpeta = ventana.templates_dir()
    assert os.path.basename(carpeta) == "Templates"
    archivos = os.listdir(carpeta)
    assert archivos == ["Mi membrete.easypdf-template.json"]
    guardadas = list_templates(carpeta)
    assert [(i.name, i.category) for i in guardadas] == [("Mi membrete", "letterhead")]


def test_deshacer_la_goma_dice_que_fue_la_goma(ventana, qapp):
    """En el menu de deshacer ponia 'Anadir dibujo': por dentro es tinta,
    pero lo que hizo el usuario fue borrar."""
    ventana.select_tool(Tool.ERASER)
    _pasar_la_goma(ventana, [(120, 150), (200, 150)])
    qapp.processEvents()
    assert ventana.view.undo_stack.undoText() == tr("cmd_erase")


# -- piezas de formulario -------------------------------------------------
def _elegir_elemento(ventana, clave):
    """Selecciona una pieza del arbol por su clave."""
    for i in range(ventana.el_tree.topLevelItemCount()):
        raiz = ventana.el_tree.topLevelItem(i)
        for j in range(raiz.childCount()):
            if raiz.child(j).data(0, Qt.UserRole) == clave:
                ventana.el_tree.setCurrentItem(raiz.child(j))
                return raiz.child(j)
    raise AssertionError(f"no esta la pieza {clave}")


def test_el_panel_tiene_pestana_de_elementos(ventana, qapp):
    """Lo que se pidio: una lista de piezas para montar formularios."""
    from easypdf.elements import ELEMENTS

    titulos = [ventana.side_tabs.tabText(i) for i in range(ventana.side_tabs.count())]
    assert tr("elements_tab") in titulos

    claves = set()
    for i in range(ventana.el_tree.topLevelItemCount()):
        raiz = ventana.el_tree.topLevelItem(i)
        for j in range(raiz.childCount()):
            claves.add(raiz.child(j).data(0, Qt.UserRole))
    assert claves == set(ELEMENTS)


def test_insertar_una_pieza_la_pone_en_la_pagina_que_se_ve(ventana, qapp):
    ventana.view.go_to_page(1)
    qapp.processEvents()
    _elegir_elemento(ventana, "checklist")
    ventana._update_element_buttons()
    assert ventana.btn_el_insert.isEnabled()

    antes = ventana.view.annotation_count()
    assert ventana.insert_selected_element()
    qapp.processEvents()
    nuevas = list(ventana.view.annotations())[antes:]
    assert len(nuevas) == 8                       # 4 casillas con su etiqueta
    assert {a.page for a in nuevas} == {1}        # en la pagina que se esta viendo
    assert len(ventana.view.selected_items()) == 8


def test_la_pieza_cae_dentro_del_papel(ventana, qapp):
    _elegir_elemento(ventana, "table")
    antes = ventana.view.annotation_count()
    ventana.insert_selected_element()
    qapp.processEvents()
    hoja = ventana.view._page_items[ventana.view.current_page].boundingRect()
    for ann in list(ventana.view.annotations())[antes:]:
        x0, y0, x1, y1 = ann.bounds()
        assert x0 >= 0 and y0 >= 0
        assert x1 <= hoja.width() and y1 <= hoja.height()


def test_una_pieza_entera_se_deshace_de_una_vez(ventana, qapp):
    _elegir_elemento(ventana, "checklist")
    antes = ventana.view.annotation_count()
    ventana.insert_selected_element()
    qapp.processEvents()
    assert ventana.view.annotation_count() == antes + 8

    ventana.view.undo_stack.undo()
    qapp.processEvents()
    assert ventana.view.annotation_count() == antes


def test_sin_documento_no_se_puede_insertar(ventana, qapp):
    ventana.close_document()
    qapp.processEvents()
    _elegir_elemento(ventana, "checkbox")
    ventana._update_element_buttons()
    assert not ventana.btn_el_insert.isEnabled()
    assert not ventana.insert_selected_element()


def test_las_pestanas_del_panel_no_se_confunden_al_cambiar_de_idioma(ventana, qapp):
    """Se nombraban por indice, y al meter Elementos en medio se cruzaban."""
    from easypdf.i18n import set_language

    try:
        set_language("es")
        ventana.retranslate()
        qapp.processEvents()
        titulos = [ventana.side_tabs.tabText(i) for i in range(ventana.side_tabs.count())]
        assert titulos[ventana.side_tabs.indexOf(ventana.el_tree.parentWidget())] \
            == tr("elements_tab")
        assert titulos[ventana.side_tabs.indexOf(ventana.tpl_tree.parentWidget())] \
            == tr("templates_tab")
    finally:
        set_language("en")
        ventana.retranslate()
        qapp.processEvents()


# -- la tabla dejaba el programa bloqueado --------------------------------
def _dibujar_tabla(ventana, qapp, desde=(80.0, 120.0), hasta=(420.0, 300.0)):
    """Inserta una tabla arrastrando, como hace el usuario con la herramienta."""
    from PySide6.QtCore import QPointF

    vista = ventana.view
    pagina = vista._page_items[vista.current_page]

    def punto(x, y):
        return vista.mapFromScene(pagina.mapToScene(QPointF(x, y)))

    ventana.select_tool(Tool.TABLE)
    qapp.processEvents()
    QTest.mousePress(vista.viewport(), Qt.LeftButton, Qt.NoModifier, punto(*desde))
    QTest.mouseMove(vista.viewport(), punto(*hasta))
    qapp.processEvents()
    QTest.mouseRelease(vista.viewport(), Qt.LeftButton, Qt.NoModifier, punto(*hasta))
    qapp.processEvents()
    return punto


def test_al_pinchar_fuera_la_celda_deja_de_editarse(ventana, qapp):
    """El editor es hijo de la tabla: al perder el foco, ella no se enteraba.

    Se quedaba en modo edicion para siempre, y en ese modo se le ceden los
    atajos al editor de texto: DEL, Ctrl+C y Ctrl+V dejaban de funcionar en
    todo el documento hasta que alguien pulsaba Esc.
    """
    punto = _dibujar_tabla(ventana, qapp)
    assert ventana.view.is_editing_text          # la tabla abre su primera celda

    QTest.mouseClick(ventana.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     punto(500.0, 620.0))
    qapp.processEvents()
    assert not ventana.view.is_editing_text


def test_una_tabla_se_puede_borrar_con_del(ventana, qapp):
    punto = _dibujar_tabla(ventana, qapp)
    QTest.mouseClick(ventana.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     punto(500.0, 620.0))
    QTest.mouseClick(ventana.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     punto(200.0, 200.0))
    qapp.processEvents()
    ventana._update_actions()
    assert ventana.act_delete.isEnabled()
    assert len(ventana.view.selected_items()) == 1

    QTest.keyClick(ventana, Qt.Key_Delete)
    qapp.processEvents()
    assert ventana.view.annotation_count() == 0


def test_una_tabla_se_puede_copiar_y_pegar(ventana, qapp):
    punto = _dibujar_tabla(ventana, qapp)
    QTest.mouseClick(ventana.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     punto(500.0, 620.0))
    QTest.mouseClick(ventana.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     punto(200.0, 200.0))
    qapp.processEvents()
    ventana._update_actions()

    QTest.keyClick(ventana, Qt.Key_C, Qt.ControlModifier)
    qapp.processEvents()
    QTest.keyClick(ventana, Qt.Key_V, Qt.ControlModifier)
    qapp.processEvents()
    tablas = [a for a in ventana.view.annotations() if a.kind is Kind.TABLE]
    assert len(tablas) == 2
    assert tablas[0].id != tablas[1].id


def test_tab_pasa_de_celda_y_shift_tab_vuelve(ventana, qapp):
    """La ayuda lo prometia desde siempre y no ocurria: el tabulador se lo
    quedaba el widget para mover el foco antes de llegar a la tabla."""
    tabla = Annotation(kind=Kind.TABLE, page=0, rect=(80.0, 120.0, 420.0, 300.0),
                       rows=2, cols=2)
    item = ventana.view.add_annotation(tabla)
    qapp.processEvents()
    item.edit_cell(0)
    qapp.processEvents()

    vista = ventana.view.viewport()
    QTest.keyClicks(vista, "uno")
    QTest.keyClick(vista, Qt.Key_Tab)
    qapp.processEvents()
    assert item._editing_cell == 1

    QTest.keyClicks(vista, "dos")
    QTest.keyClick(vista, Qt.Key_Backtab, Qt.ShiftModifier)
    qapp.processEvents()
    assert item._editing_cell == 0

    QTest.keyClick(vista, Qt.Key_Escape)
    qapp.processEvents()
    assert not ventana.view.is_editing_text
    assert tabla.cells[:2] == ["uno", "dos"]


def test_mientras_se_escribe_en_una_celda_del_no_borra_la_tabla(ventana, qapp):
    """Lo contrario tambien tiene que seguir siendo cierto."""
    tabla = Annotation(kind=Kind.TABLE, page=0, rect=(80.0, 120.0, 420.0, 300.0),
                       rows=2, cols=2)
    item = ventana.view.add_annotation(tabla)
    qapp.processEvents()
    item.edit_cell(0)
    qapp.processEvents()
    ventana._update_actions()
    assert not ventana.act_delete.isEnabled()
    assert not ventana.act_copy.isEnabled()

    QTest.keyClick(ventana.view.viewport(), Qt.Key_Escape)
    qapp.processEvents()
