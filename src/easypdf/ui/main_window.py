"""Ventana principal de easypdf.surf."""

from __future__ import annotations

import os
from collections import deque

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDesktopServices,
    QIcon,
    QImage,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSpinBox,
    QTextBrowser,
    QToolBar,
    QToolButton,
    QVBoxLayout,
)

from .. import __app_name__, __repo_url__, __url__, __version__
from ..config import PALETTE, Settings
from ..document import DEFAULT_PAGE_SIZE, PAGE_SIZES, PasswordRequired, PdfDocument, PdfError
from ..model import Align, Font
from ..printing import print_document, print_preview
from ..templates import (
    TemplateError,
    list_templates,
    load_template,
    save_template,
)
from . import icons
from .items import to_rgb
from .page_view import PdfView, Tool

THUMB_WIDTH = 116


def _swatch(color: QColor | None, size: int = 22) -> QIcon:
    """Icono cuadrado con el color indicado (o un aspa si no hay color)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    from PySide6.QtGui import QPainter, QPen

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
    if color is None or not color.isValid():
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(1, 1, size - 3, size - 3)
        painter.setPen(QPen(QColor("#c62828"), 2))
        painter.drawLine(3, size - 4, size - 4, 3)
    else:
        painter.setBrush(color)
        painter.drawRect(1, 1, size - 3, size - 3)
    painter.end()
    return QIcon(pixmap)


class AboutDialog(QDialog):
    """Ventana 'Acerca de easypdf.surf'."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {__app_name__}")
        self.resize(520, 380)
        layout = QVBoxLayout(self)
        header = QLabel()
        header.setPixmap(icons.icon("app").pixmap(64, 64))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        text = QTextBrowser()
        text.setOpenExternalLinks(True)
        text.setHtml(
            f"""
            <h2 style="text-align:center;margin-bottom:0">{__app_name__} {__version__}</h2>
            <p style="text-align:center;color:#666">Lector y anotador de PDF sencillo</p>
            <p>Software libre publicado bajo la licencia
            <b>GNU AGPL v3 o posterior</b>. Puedes usarlo, copiarlo, modificarlo y
            redistribuirlo respetando esa licencia.</p>
            <p>Pagina web: <a href="{__url__}">easypdf.surf</a><br>
            Codigo fuente: <a href="{__repo_url__}">{__repo_url__}</a></p>
            <p>Construido con <a href="https://pymupdf.readthedocs.io">PyMuPDF</a> (AGPL)
            y <a href="https://doc.qt.io/qtforpython/">PySide6</a> (LGPL).</p>
            <p style="color:#666">Este programa se distribuye sin ninguna garantia.</p>
            """
        )
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class HelpDialog(QDialog):
    """Guia rapida de uso."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guia rapida")
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        text = QTextBrowser()
        text.setHtml(
            """
            <h2>Guia rapida</h2>
            <h3>Abrir, crear e imprimir</h3>
            <ul>
              <li><b>Ctrl+O</b> abre un PDF. Tambien puedes arrastrarlo sobre la ventana.</li>
              <li><b>Ctrl+N</b> crea un documento en blanco. Desde el menu <b>Documento</b>
                  puedes anadir, duplicar, mover y eliminar paginas, y elegir su tamano.</li>
              <li><b>Ctrl+P</b> imprime. La vista previa muestra el documento con las
                  anotaciones tal y como saldran en papel.</li>
              <li><b>Ctrl+S</b> guarda las anotaciones dentro del PDF.</li>
            </ul>
            <h3>Anotar</h3>
            <ul>
              <li>Elige una herramienta en la barra: cuadro, resaltado, linea, flecha,
                  texto, dibujo a mano alzada o tabla.</li>
              <li>Arrastra sobre la pagina para crear la anotacion.</li>
              <li>Manten <b>Mayus</b> para cuadrados perfectos o lineas a 45 grados.</li>
              <li>Con la herramienta <b>Seleccionar</b> puedes mover, redimensionar
                  (tiradores azules) y borrar con <b>Supr</b>.</li>
              <li>Doble clic sobre un cuadro de texto para escribir dentro.</li>
              <li>Con la herramienta <b>Imagen</b> (o soltando un archivo de imagen sobre
                  la ventana) puedes colocar fotos, firmas o logotipos encima del PDF.</li>
              <li>En las tablas, doble clic en una celda para escribir y <b>Tab</b> para
                  pasar a la siguiente. El numero de filas y columnas se elige en la
                  barra antes de dibujarla.</li>
              <li>El texto admite tipo de letra (sans, serif o monoespaciada),
                  <b>negrita</b> (Ctrl+B), <i>cursiva</i> (Ctrl+I) y alineacion.</li>
              <li><b>Ctrl+Z</b> y <b>Ctrl+Y</b> deshacen y rehacen.</li>
            </ul>
            <h3>Moverse por el documento</h3>
            <ul>
              <li><b>Ctrl+rueda</b> hace zoom; <b>Ctrl+0</b> vuelve al 100%.</li>
              <li><b>Ctrl+F</b> busca texto; <b>F3</b> salta al siguiente resultado.
                  <b>Esc</b> o el boton de cerrar quitan el resaltado amarillo.</li>
              <li>La barra lateral de miniaturas permite saltar de pagina.</li>
              <li><b>Esc</b> vuelve siempre a la herramienta Seleccionar.</li>
            </ul>
            <h3>Plantillas</h3>
            <p>En <b>Documento -&gt; Plantillas</b> puedes guardar lo que hayas montado
            (membretes, tablas, sellos, logotipos) y reutilizarlo: crear un documento
            nuevo a partir de una plantilla o aplicarla encima del PDF que tengas
            abierto, desde la pagina en la que estes. Se deshace de una vez con
            <b>Ctrl+Z</b>.</p>

            <h3>Como se guardan las anotaciones</h3>
            <p>El programa escribe anotaciones PDF estandar (cuadro, linea, texto libre,
            resaltado, tinta y poligono), asi que se ven igual en Adobe Reader, Edge o
            Firefox. Las tablas se guardan como su rejilla mas el texto de cada celda, y las
            imagenes se incrustan en la propia pagina para que se impriman siempre.
            El contenido original del documento no se modifica.</p>
            """
        )
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    """Ventana principal: menus, barras, miniaturas y visor."""

    documentChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.settings = Settings()
        self.setWindowTitle(__app_name__)
        self.setWindowIcon(icons.app_icon())
        self.setAcceptDrops(True)
        self.resize(1180, 820)

        self.view = PdfView(self)
        self.setCentralWidget(self.view)

        self._modified = False
        self._thumb_queue: deque[int] = deque()
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setInterval(0)
        self._thumb_timer.timeout.connect(self._render_next_thumbnail)
        self._updating_page_box = False

        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_thumbnails()
        self._create_status_bar()
        self._connect_view()
        self._restore_settings()
        self._load_style_defaults()
        self.view.set_tool(Tool.SELECT)
        self._update_actions()

    # ------------------------------------------------------------------ acciones
    def _create_actions(self) -> None:
        def action(text, slot, icon_name=None, shortcut=None, tip=None, checkable=False):
            act = QAction(text, self)
            if icon_name:
                act.setIcon(icons.icon(icon_name))
            if shortcut:
                act.setShortcut(shortcut)
            act.setCheckable(checkable)
            act.setStatusTip(tip or text)
            act.triggered.connect(slot)
            return act

        self.act_new = action("&Nuevo documento en blanco", self.new_document, "new",
                              QKeySequence.New, "Crear un PDF vacio para empezar de cero")
        self.act_open = action("&Abrir...", self.open_file_dialog, "open", QKeySequence.Open,
                               "Abrir un documento PDF")
        self.act_save = action("&Guardar", self.save, "save", QKeySequence.Save,
                               "Guardar las anotaciones en el PDF")
        self.act_save_as = action("Guardar &como...", self.save_as, "save_as",
                                  QKeySequence.SaveAs, "Guardar una copia del PDF")
        self.act_print = action("&Imprimir...", self.print_file, "print", QKeySequence.Print,
                                "Imprimir el documento")
        self.act_preview = action("Vista pre&via de impresion...", self.preview_print,
                                  shortcut="Ctrl+Shift+P", tip="Ver como quedara impreso")
        self.act_close = action("&Cerrar documento", self.close_document, shortcut="Ctrl+W")
        self.act_quit = action("&Salir", self.close, shortcut=QKeySequence.Quit)

        self.act_undo = self.view.undo_stack.createUndoAction(self, "Deshacer")
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setIcon(icons.icon("undo"))
        self.act_redo = self.view.undo_stack.createRedoAction(self, "Rehacer")
        self.act_redo.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Y")])
        self.act_redo.setIcon(icons.icon("redo"))

        self.act_delete = action("&Eliminar seleccion", self.delete_selection, "delete",
                                 QKeySequence.Delete, "Eliminar las anotaciones seleccionadas")
        self.act_select_all = action("Seleccionar &todas las anotaciones",
                                     self.view.select_all_annotations,
                                     shortcut=QKeySequence.SelectAll)
        self.act_find = action("&Buscar texto...", self.show_search, "search",
                               QKeySequence.Find, "Buscar texto en el documento")
        self.act_find_next = action("Buscar &siguiente", self.view.next_hit,
                                    shortcut=QKeySequence.FindNext)
        self.act_find_prev = action("Buscar &anterior", self.view.previous_hit,
                                    shortcut=QKeySequence.FindPrevious)

        self.act_zoom_in = action("&Acercar", self.view.zoom_in, "zoom_in", QKeySequence.ZoomIn)
        self.act_zoom_in.setShortcuts([QKeySequence.ZoomIn, QKeySequence("Ctrl++")])
        self.act_zoom_out = action("A&lejar", self.view.zoom_out, "zoom_out", QKeySequence.ZoomOut)
        self.act_zoom_reset = action("Zoom &100%", self.view.reset_zoom, shortcut="Ctrl+0")
        self.act_fit_width = action("Ajustar al &ancho", self.view.fit_width, "fit_width",
                                    shortcut="Ctrl+1")
        self.act_fit_page = action("Ajustar a la &pagina", self.view.fit_page, "fit_page",
                                   shortcut="Ctrl+2")
        self.act_prev_page = action("Pagina &anterior", self.view.previous_page, "prev",
                                    shortcut="Ctrl+Up")
        self.act_next_page = action("Pagina &siguiente", self.view.next_page, "next",
                                    shortcut="Ctrl+Down")
        self.act_goto = action("&Ir a la pagina...", self.goto_page_dialog, shortcut="Ctrl+G")
        self.act_fullscreen = action("Pantalla &completa", self.toggle_fullscreen,
                                     shortcut="F11", checkable=True)
        self.act_thumbnails = action("Panel de &miniaturas", self.toggle_thumbnails,
                                     shortcut="F9", checkable=True)

        self.act_page_add = action("&Anadir una pagina al final", self.add_page_end,
                                   shortcut="Ctrl+Shift+N")
        self.act_page_insert = action("&Insertar una pagina despues de esta",
                                      self.insert_page_here)
        self.act_page_duplicate = action("&Duplicar esta pagina", self.duplicate_current_page)
        self.act_page_delete = action("&Eliminar esta pagina", self.delete_current_page)
        self.act_page_up = action("Mover la pagina &arriba", lambda: self.move_current_page(-1),
                                  shortcut="Ctrl+Shift+Up")
        self.act_page_down = action("Mover la pagina aba&jo", lambda: self.move_current_page(1),
                                    shortcut="Ctrl+Shift+Down")

        self.act_help = action("&Guia rapida", self.show_help, shortcut=QKeySequence.HelpContents)
        self.act_about = action(f"&Acerca de {__app_name__}", self.show_about)
        self.act_website = action("Pagina &web de easypdf.surf",
                                  lambda: QDesktopServices.openUrl(QUrl(__url__)))
        self.act_source = action("Codigo &fuente en GitHub",
                                 lambda: QDesktopServices.openUrl(QUrl(__repo_url__)))

        # Herramientas (excluyentes entre si)
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_actions = {}
        tools = [
            (Tool.SELECT, "&Seleccionar", "select", "S"),
            (Tool.PAN, "&Mover la vista", "hand", "H"),
            (Tool.RECT, "&Cuadro", "rect", "R"),
            (Tool.HIGHLIGHT, "&Resaltar", "highlight", "M"),
            (Tool.LINE, "&Linea", "line", "L"),
            (Tool.ARROW, "&Flecha", "arrow", "F"),
            (Tool.TEXT, "&Texto", "text", "T"),
            (Tool.INK, "&Dibujo libre", "ink", "D"),
            (Tool.TABLE, "Ta&bla", "table", "A"),
            (Tool.IMAGE, "&Imagen", "image", "I"),
        ]
        for tool, label, icon_name, key in tools:
            act = QAction(icons.icon(icon_name), label, self)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(key))
            act.setStatusTip(f"Herramienta: {label.replace('&', '')} ({key})")
            act.triggered.connect(lambda checked=False, t=tool: self.select_tool(t))
            self.tool_group.addAction(act)
            self.tool_actions[tool] = act
        self.tool_actions[Tool.SELECT].setChecked(True)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&Archivo")
        file_menu.addAction(self.act_new)
        file_menu.addAction(self.act_open)
        self.recent_menu = QMenu("Abrir &reciente", self)
        file_menu.addMenu(self.recent_menu)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_print)
        file_menu.addAction(self.act_preview)
        file_menu.addSeparator()
        file_menu.addAction(self.act_close)
        file_menu.addAction(self.act_quit)
        self._refresh_recent_menu()

        edit_menu = self.menuBar().addMenu("&Editar")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_delete)
        edit_menu.addAction(self.act_select_all)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_find)
        edit_menu.addAction(self.act_find_next)
        edit_menu.addAction(self.act_find_prev)

        view_menu = self.menuBar().addMenu("&Ver")
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addAction(self.act_zoom_reset)
        view_menu.addAction(self.act_fit_width)
        view_menu.addAction(self.act_fit_page)
        view_menu.addSeparator()
        view_menu.addAction(self.act_prev_page)
        view_menu.addAction(self.act_next_page)
        view_menu.addAction(self.act_goto)
        view_menu.addSeparator()
        view_menu.addAction(self.act_thumbnails)
        view_menu.addAction(self.act_fullscreen)

        doc_menu = self.menuBar().addMenu("&Documento")
        doc_menu.addAction(self.act_page_add)
        doc_menu.addAction(self.act_page_insert)
        doc_menu.addAction(self.act_page_duplicate)
        doc_menu.addAction(self.act_page_delete)
        doc_menu.addSeparator()
        doc_menu.addAction(self.act_page_up)
        doc_menu.addAction(self.act_page_down)
        doc_menu.addSeparator()
        tamano_menu = doc_menu.addMenu("&Tamano de las paginas nuevas")
        self.page_size_group = QActionGroup(self)
        self.page_size_group.setExclusive(True)
        elegido = self.settings.value("document/page_size", DEFAULT_PAGE_SIZE)
        for nombre in PAGE_SIZES:
            act = QAction(nombre, self)
            act.setCheckable(True)
            act.setChecked(nombre == elegido)
            act.triggered.connect(lambda checked=False, n=nombre: self._set_page_size(n))
            self.page_size_group.addAction(act)
            tamano_menu.addAction(act)
        self.new_page_size = str(elegido)

        doc_menu.addSeparator()
        self.templates_menu = QMenu("&Plantillas", self)
        doc_menu.addMenu(self.templates_menu)
        self.templates_menu.aboutToShow.connect(self._refresh_templates_menu)
        self._refresh_templates_menu()

        tools_menu = self.menuBar().addMenu("&Herramientas")
        for act in self.tool_group.actions():
            tools_menu.addAction(act)

        help_menu = self.menuBar().addMenu("A&yuda")
        help_menu.addAction(self.act_help)
        help_menu.addAction(self.act_website)
        help_menu.addAction(self.act_source)
        help_menu.addSeparator()
        help_menu.addAction(self.act_about)

    def _create_toolbars(self) -> None:
        bar = QToolBar("Principal", self)
        bar.setObjectName("toolbar_main")
        bar.setIconSize(QSize(22, 22))
        bar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        bar.addAction(self.act_new)
        bar.addAction(self.act_open)
        bar.addAction(self.act_save)
        bar.addAction(self.act_print)
        bar.addSeparator()
        bar.addAction(self.act_undo)
        bar.addAction(self.act_redo)
        bar.addSeparator()
        bar.addAction(self.act_zoom_out)
        bar.addAction(self.act_zoom_in)
        bar.addAction(self.act_fit_width)
        bar.addAction(self.act_fit_page)
        bar.addSeparator()
        bar.addAction(self.act_find)
        self.addToolBar(bar)
        self.toolbar_main = bar

        tools = QToolBar("Herramientas", self)
        tools.setObjectName("toolbar_tools")
        tools.setIconSize(QSize(22, 22))
        for act in self.tool_group.actions():
            tools.addAction(act)
        tools.addSeparator()

        # Color del trazo
        self.color_button = QToolButton(self)
        self.color_button.setPopupMode(QToolButton.InstantPopup)
        self.color_button.setToolTip("Color del trazo y del texto")
        self.color_button.setMenu(self._color_menu(self._set_color, allow_none=False))
        tools.addWidget(self.color_button)

        # Color de relleno
        self.fill_button = QToolButton(self)
        self.fill_button.setPopupMode(QToolButton.InstantPopup)
        self.fill_button.setToolTip("Color de relleno")
        self.fill_button.setMenu(self._color_menu(self._set_fill, allow_none=True))
        tools.addWidget(self.fill_button)

        tools.addWidget(QLabel(" Grosor "))
        self.width_spin = QDoubleSpinBox(self)
        self.width_spin.setRange(0.0, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setDecimals(1)
        self.width_spin.setSuffix(" pt")
        self.width_spin.setToolTip("Grosor de la linea")
        self.width_spin.valueChanged.connect(self._set_width)
        tools.addWidget(self.width_spin)

        tools.addWidget(QLabel(" Opacidad "))
        self.opacity_spin = QSpinBox(self)
        self.opacity_spin.setRange(10, 100)
        self.opacity_spin.setSingleStep(5)
        self.opacity_spin.setSuffix(" %")
        self.opacity_spin.setToolTip("Opacidad de la anotacion")
        self.opacity_spin.valueChanged.connect(self._set_opacity)
        tools.addWidget(self.opacity_spin)

        tools.addWidget(QLabel(" Letra "))
        self.font_spin = QDoubleSpinBox(self)
        self.font_spin.setRange(4.0, 96.0)
        self.font_spin.setSingleStep(1.0)
        self.font_spin.setDecimals(0)
        self.font_spin.setSuffix(" pt")
        self.font_spin.setToolTip("Tamano del texto")
        self.font_spin.valueChanged.connect(self._set_font_size)
        tools.addWidget(self.font_spin)

        self.addToolBar(tools)
        self.toolbar_tools = tools

        # Los ajustes de estilo van en su propia fila: si no, la barra se
        # desborda en pantallas normales y aparece el boton de "mas".
        estilo = QToolBar("Estilo", self)
        estilo.setObjectName("toolbar_style")
        estilo.setIconSize(QSize(22, 22))
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(estilo)
        self.toolbar_style = estilo
        tools = estilo

        self.font_combo = QComboBox(self)
        for familia in (Font.SANS, Font.SERIF, Font.MONO):
            self.font_combo.addItem(familia.label, familia.value)
        self.font_combo.setToolTip("Tipo de letra")
        self.font_combo.currentIndexChanged.connect(self._set_font_family)
        tools.addWidget(self.font_combo)

        self.act_bold = QAction(icons.icon("bold"), "Negrita", self)
        self.act_bold.setCheckable(True)
        self.act_bold.setShortcut(QKeySequence.Bold)
        self.act_bold.setToolTip("Negrita (Ctrl+B)")
        self.act_bold.triggered.connect(self._set_bold)
        tools.addAction(self.act_bold)

        self.act_italic = QAction(icons.icon("italic"), "Cursiva", self)
        self.act_italic.setCheckable(True)
        self.act_italic.setShortcut(QKeySequence.Italic)
        self.act_italic.setToolTip("Cursiva (Ctrl+I)")
        self.act_italic.triggered.connect(self._set_italic)
        tools.addAction(self.act_italic)

        self.align_group = QActionGroup(self)
        self.align_group.setExclusive(True)
        self.align_actions = {}
        for alineacion, nombre in (
            (Align.LEFT, "align_left"),
            (Align.CENTER, "align_center"),
            (Align.RIGHT, "align_right"),
        ):
            act = QAction(icons.icon(nombre), f"Alinear a la {alineacion.label.lower()}", self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked=False, a=alineacion: self._set_align(a))
            self.align_group.addAction(act)
            self.align_actions[alineacion] = act
            tools.addAction(act)
        self.align_actions[Align.LEFT].setChecked(True)

        tools.addSeparator()
        tools.addWidget(QLabel(" Tabla "))
        self.rows_spin = QSpinBox(self)
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setPrefix("filas ")
        self.rows_spin.setToolTip("Filas de la tabla")
        self.rows_spin.valueChanged.connect(self._set_rows)
        tools.addWidget(self.rows_spin)

        self.cols_spin = QSpinBox(self)
        self.cols_spin.setRange(1, 30)
        self.cols_spin.setPrefix("col. ")
        self.cols_spin.setToolTip("Columnas de la tabla")
        self.cols_spin.valueChanged.connect(self._set_cols)
        tools.addWidget(self.cols_spin)

        tools.addSeparator()
        tools.addAction(self.act_delete)

        self._create_search_bar()

    def _create_search_bar(self) -> None:
        bar = QToolBar("Buscar", self)
        bar.setObjectName("toolbar_search")
        bar.setIconSize(QSize(18, 18))
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Buscar texto en el documento...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(360)
        self.search_edit.returnPressed.connect(self.run_search)
        bar.addWidget(self.search_edit)
        bar.addAction(self.act_find_prev)
        bar.addAction(self.act_find_next)
        self.search_label = QLabel("  ")
        bar.addWidget(self.search_label)
        close_action = QAction("Cerrar y quitar el resaltado", self)
        close_action.setShortcut(QKeySequence("Esc"))
        close_action.triggered.connect(self.close_search)
        bar.addAction(close_action)
        self.act_close_search = close_action
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.addToolBar(Qt.TopToolBarArea, bar)
        self.insertToolBarBreak(bar)
        bar.setVisible(False)
        self.toolbar_search = bar

    def _color_menu(self, slot, allow_none: bool) -> QMenu:
        menu = QMenu(self)
        if allow_none:
            act = QAction(_swatch(None), "Sin relleno", self)
            act.triggered.connect(lambda: slot(None))
            menu.addAction(act)
            menu.addSeparator()
        for name, hexvalue in PALETTE:
            act = QAction(_swatch(QColor(hexvalue)), name, self)
            act.triggered.connect(lambda checked=False, h=hexvalue: slot(QColor(h)))
            menu.addAction(act)
        menu.addSeparator()
        more = QAction("Mas colores...", self)
        more.triggered.connect(lambda: self._pick_custom_color(slot))
        menu.addAction(more)
        return menu

    def _pick_custom_color(self, slot) -> None:
        color = QColorDialog.getColor(QColor("#d81b1b"), self, "Elegir color")
        if color.isValid():
            slot(color)

    def _create_thumbnails(self) -> None:
        from PySide6.QtWidgets import QDockWidget

        self.thumb_list = QListWidget(self)
        self.thumb_list.setViewMode(QListWidget.IconMode)
        self.thumb_list.setIconSize(QSize(THUMB_WIDTH, int(THUMB_WIDTH * 1.5)))
        self.thumb_list.setResizeMode(QListWidget.Adjust)
        self.thumb_list.setMovement(QListWidget.Static)
        self.thumb_list.setSpacing(6)
        self.thumb_list.setUniformItemSizes(False)
        self.thumb_list.setWordWrap(True)
        self.thumb_list.currentRowChanged.connect(self._on_thumbnail_selected)

        dock = QDockWidget("Paginas", self)
        dock.setObjectName("dock_thumbnails")
        dock.setWidget(self.thumb_list)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setMinimumWidth(THUMB_WIDTH + 60)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.thumb_dock = dock
        dock.visibilityChanged.connect(self.act_thumbnails.setChecked)

    def _create_status_bar(self) -> None:
        status = self.statusBar()
        self.page_spin = QSpinBox(self)
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setToolTip("Pagina actual")
        self.page_spin.setFixedWidth(70)
        self.page_spin.valueChanged.connect(self._on_page_spin)
        self.page_label = QLabel("de 0")
        self.zoom_label = QLabel("100 %")
        self.info_label = QLabel("")
        status.addPermanentWidget(QLabel("Pagina"))
        status.addPermanentWidget(self.page_spin)
        status.addPermanentWidget(self.page_label)
        status.addPermanentWidget(QLabel("   "))
        status.addPermanentWidget(self.zoom_label)
        status.addWidget(self.info_label)
        status.showMessage("Abre un PDF con Ctrl+O o arrastralo aqui", 6000)

    def _connect_view(self) -> None:
        self.view.pageChanged.connect(self._on_page_changed)
        self.view.zoomChanged.connect(self._on_zoom_changed)
        self.view.modified.connect(self._on_modified)
        self.view.toolFinished.connect(
            lambda: self.tool_actions[Tool.SELECT].setChecked(True)
        )
        self.view.selectionChanged.connect(self._update_actions)
        self.view.textEditing.connect(self._on_text_editing)
        self.view.undo_stack.cleanChanged.connect(lambda clean: self._update_title())

    def _on_text_editing(self, editing: bool) -> None:
        """Mientras se escribe en un cuadro de texto, Supr y Ctrl+A son del editor."""
        self._update_actions()
        if editing:
            self.statusBar().showMessage("Escribe la nota; Esc para terminar", 4000)

    # ------------------------------------------------------------------ ajustes
    def _restore_settings(self) -> None:
        geometry = self.settings.window_geometry()
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.window_state()
        if state:
            self.restoreState(state)
        visible = self.settings.show_thumbnails()
        self.thumb_dock.setVisible(visible)
        self.act_thumbnails.setChecked(visible)

    def _load_style_defaults(self) -> None:
        color = QColor(self.settings.tool_color())
        fill_value = self.settings.tool_fill()
        fill = QColor(fill_value) if fill_value else None
        self.view.style_defaults["color"] = to_rgb(color)
        self.view.style_defaults["fill"] = to_rgb(fill) if fill else None
        self.view.style_defaults["width"] = self.settings.tool_width()
        self.view.style_defaults["opacity"] = self.settings.tool_opacity()
        self.view.style_defaults["font_size"] = self.settings.tool_font_size()
        self.view.style_defaults["font"] = Font(self.settings.tool_font())
        self.view.style_defaults["bold"] = self.settings.tool_bold()
        self.view.style_defaults["italic"] = self.settings.tool_italic()
        self.view.style_defaults["align"] = Align(self.settings.tool_align())
        self.view.style_defaults["rows"] = self.settings.table_rows()
        self.view.style_defaults["cols"] = self.settings.table_cols()
        self.color_button.setIcon(_swatch(color))
        self.fill_button.setIcon(_swatch(fill))
        self.font_combo.blockSignals(True)
        self.font_combo.setCurrentIndex(
            max(0, self.font_combo.findData(self.settings.tool_font()))
        )
        self.font_combo.blockSignals(False)
        self.act_bold.setChecked(self.settings.tool_bold())
        self.act_italic.setChecked(self.settings.tool_italic())
        self.align_actions[Align(self.settings.tool_align())].setChecked(True)
        for widget, value in (
            (self.width_spin, self.settings.tool_width()),
            (self.opacity_spin, int(round(self.settings.tool_opacity() * 100))),
            (self.font_spin, self.settings.tool_font_size()),
            (self.rows_spin, self.settings.table_rows()),
            (self.cols_spin, self.settings.table_cols()),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

    # ------------------------------------------------------------------ estilo
    def _set_color(self, color: QColor | None) -> None:
        if color is None or not color.isValid():
            return
        rgb = to_rgb(color)
        self.view.style_defaults["color"] = rgb
        if self.view.tool is Tool.HIGHLIGHT:
            self.view.style_defaults["highlight_color"] = rgb
        self.color_button.setIcon(_swatch(color))
        self.settings.set_tool_color(color.name())
        self.view.apply_style_to_selection(color=rgb)

    def _set_fill(self, color: QColor | None) -> None:
        rgb = to_rgb(color) if color and color.isValid() else None
        self.view.style_defaults["fill"] = rgb
        self.fill_button.setIcon(_swatch(color if rgb else None))
        self.settings.set_tool_fill(color.name() if rgb else "")
        self.view.apply_style_to_selection(fill=rgb)

    def _set_width(self, value: float) -> None:
        self.view.style_defaults["width"] = float(value)
        self.settings.set_tool_width(value)
        self.view.apply_style_to_selection(width=float(value))

    def _set_opacity(self, value: int) -> None:
        opacity = max(0.1, min(1.0, value / 100.0))
        self.view.style_defaults["opacity"] = opacity
        self.settings.set_tool_opacity(opacity)
        self.view.apply_style_to_selection(opacity=opacity)

    def _set_font_size(self, value: float) -> None:
        self.view.style_defaults["font_size"] = float(value)
        self.settings.set_tool_font_size(value)
        self.view.apply_style_to_selection(font_size=float(value))

    def _set_font_family(self, index: int) -> None:
        familia = Font(self.font_combo.itemData(index) or Font.SANS.value)
        self.view.style_defaults["font"] = familia
        self.settings.set_tool_font(familia.value)
        self.view.apply_style_to_selection(font=familia)

    def _set_bold(self, checked: bool) -> None:
        self.view.style_defaults["bold"] = bool(checked)
        self.settings.set_tool_bold(checked)
        self.view.apply_style_to_selection(bold=bool(checked))

    def _set_italic(self, checked: bool) -> None:
        self.view.style_defaults["italic"] = bool(checked)
        self.settings.set_tool_italic(checked)
        self.view.apply_style_to_selection(italic=bool(checked))

    def _set_align(self, alineacion: Align) -> None:
        self.view.style_defaults["align"] = alineacion
        self.settings.set_tool_align(int(alineacion))
        self.view.apply_style_to_selection(align=alineacion)

    def _set_rows(self, value: int) -> None:
        self.view.style_defaults["rows"] = int(value)
        self.settings.set_table_rows(value)
        self.view.apply_style_to_selection(rows=int(value))

    def _set_cols(self, value: int) -> None:
        self.view.style_defaults["cols"] = int(value)
        self.settings.set_table_cols(value)
        self.view.apply_style_to_selection(cols=int(value))

    IMAGE_FILTER = (
        "Imagenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;"
        "Todos los archivos (*)"
    )

    def choose_image(self) -> bool:
        """Pide una imagen y la deja lista para colocarla. False si se cancela."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Elegir imagen",
            self.settings.last_dir() or os.path.expanduser("~"),
            self.IMAGE_FILTER,
        )
        if not path:
            return False
        try:
            with open(path, "rb") as fh:
                datos = fh.read()
        except OSError as exc:
            QMessageBox.warning(self, __app_name__, f"No se pudo leer la imagen:\n{exc}")
            return False
        if QPixmap.fromImage(QImage.fromData(datos)).isNull():
            QMessageBox.warning(
                self, __app_name__, "Ese archivo no parece una imagen que se pueda abrir."
            )
            return False
        self.view.style_defaults["image"] = (os.path.basename(path), datos)
        self.settings.set_last_dir(os.path.dirname(path))
        return True

    def select_tool(self, tool: Tool) -> None:
        if tool is Tool.IMAGE and not self.choose_image():
            self.tool_actions[Tool.SELECT].setChecked(True)
            self.view.set_tool(Tool.SELECT)
            return
        self.view.set_tool(tool)
        self.tool_actions[tool].setChecked(True)
        if tool is Tool.HIGHLIGHT:
            self.statusBar().showMessage(
                "Arrastra sobre el texto que quieras resaltar", 4000
            )
        elif tool is Tool.TEXT:
            self.statusBar().showMessage(
                "Arrastra para crear el cuadro y escribe; Esc para terminar", 5000
            )
        elif tool is Tool.IMAGE:
            nombre = (self.view.style_defaults.get("image") or ("", b""))[0]
            self.statusBar().showMessage(
                f"Arrastra sobre la pagina para colocar {nombre}, o haz un clic "
                "para ponerla a un tamano comodo",
                6000,
            )
        elif tool is Tool.TABLE:
            self.statusBar().showMessage(
                f"Arrastra para crear una tabla de {self.rows_spin.value()} x "
                f"{self.cols_spin.value()}; doble clic en una celda para escribir, "
                "Tab pasa a la siguiente",
                6000,
            )

    # ------------------------------------------------------------------ archivos
    def _set_page_size(self, nombre: str) -> None:
        self.new_page_size = nombre
        self.settings.set_value("document/page_size", nombre)

    def new_document(self) -> None:
        """Crea un PDF vacio y lo abre."""
        if not self._confirm_discard():
            return
        anterior = self.view.document
        self.view.set_document(PdfDocument.blank(1, self.new_page_size))
        if anterior is not None:
            anterior.close()
        self._modified = False
        self.view.undo_stack.setClean()
        self._build_thumbnails()
        self._update_title()
        self._update_actions()
        self.statusBar().showMessage(
            "Documento nuevo. Anade paginas desde el menu Documento y guardalo con Ctrl+S",
            6000,
        )
        self.documentChanged.emit()

    def add_page_end(self) -> None:
        if self.view.has_document():
            self.view.add_page(None, self.new_page_size)
            self._after_page_change(self.view.page_count - 1)

    def insert_page_here(self) -> None:
        if self.view.has_document():
            destino = self.view.current_page + 1
            self.view.add_page(destino, self.new_page_size)
            self._after_page_change(destino)

    def duplicate_current_page(self) -> None:
        if self.view.has_document():
            actual = self.view.current_page
            self.view.duplicate_page(actual)
            self._after_page_change(actual + 1)

    def delete_current_page(self) -> None:
        if not self.view.has_document():
            return
        if self.view.page_count <= 1:
            QMessageBox.information(
                self, __app_name__, "El documento no puede quedarse sin paginas."
            )
            return
        actual = self.view.current_page
        anotaciones = len(self.view.items_on_page(actual))
        aviso = f"Eliminar la pagina {actual + 1} de {self.view.page_count}?"
        if anotaciones:
            aviso += f"\n\nSe borraran tambien sus {anotaciones} anotaciones."
        aviso += "\n\nSe puede deshacer con Ctrl+Z."
        if QMessageBox.question(self, __app_name__, aviso) != QMessageBox.Yes:
            return
        self.view.delete_page(actual)
        self._after_page_change(min(actual, self.view.page_count - 1))

    def move_current_page(self, delta: int) -> None:
        if not self.view.has_document():
            return
        actual = self.view.current_page
        destino = actual + delta
        if 0 <= destino < self.view.page_count:
            self.view.move_page(actual, destino)
            self._after_page_change(destino)

    def _after_page_change(self, pagina: int) -> None:
        """Rehace las miniaturas y coloca la vista en la pagina indicada."""
        self._build_thumbnails()
        self.view.go_to_page(max(0, min(pagina, self.view.page_count - 1)))
        self._update_actions()
        self._update_title()

    # ------------------------------------------------------------------ plantillas
    def templates_dir(self) -> str:
        """Carpeta donde se guardan las plantillas del usuario."""
        from PySide6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not base:  # pragma: no cover - sistemas raros
            base = os.path.join(os.path.expanduser("~"), ".easypdf")
        return os.path.join(base, "plantillas")

    def _refresh_templates_menu(self) -> None:
        menu = self.templates_menu
        menu.clear()
        guardar = QAction("&Guardar esto como plantilla...", self)
        guardar.setStatusTip("Guardar las anotaciones actuales para reutilizarlas")
        guardar.triggered.connect(self.save_as_template)
        guardar.setEnabled(self.view.has_document())
        menu.addAction(guardar)
        menu.addSeparator()

        plantillas = list_templates(self.templates_dir())
        if not plantillas:
            vacio = QAction("(todavia no hay plantillas guardadas)", self)
            vacio.setEnabled(False)
            menu.addAction(vacio)
        else:
            nuevo = menu.addMenu("&Nuevo documento desde plantilla")
            aplicar = menu.addMenu("&Aplicar al documento de ahora")
            aplicar.setEnabled(self.view.has_document())
            for plantilla in plantillas:
                detalle = f"{plantilla.annotations} anotaciones"
                if plantilla.pages:
                    detalle = f"{plantilla.pages} paginas, " + detalle
                act = QAction(f"{plantilla.name}  ({detalle})", self)
                act.triggered.connect(
                    lambda checked=False, p=plantilla.path: self.new_from_template(p)
                )
                nuevo.addAction(act)

                act2 = QAction(f"{plantilla.name}  ({detalle})", self)
                act2.triggered.connect(
                    lambda checked=False, p=plantilla.path: self.apply_template(p)
                )
                aplicar.addAction(act2)

            borrar = menu.addMenu("&Eliminar una plantilla")
            for plantilla in plantillas:
                act = QAction(plantilla.name, self)
                act.triggered.connect(
                    lambda checked=False, p=plantilla: self.delete_template(p)
                )
                borrar.addAction(act)

        menu.addSeparator()
        carpeta = QAction("Abrir la &carpeta de plantillas", self)
        carpeta.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._ensure_templates_dir()))
        )
        menu.addAction(carpeta)

    def _ensure_templates_dir(self) -> str:
        ruta = self.templates_dir()
        os.makedirs(ruta, exist_ok=True)
        return ruta

    def save_as_template(self) -> bool:
        """Guarda las anotaciones actuales como plantilla reutilizable."""
        if not self.view.has_document():
            return False
        anotaciones = list(self.view.annotations())
        if not anotaciones:
            QMessageBox.information(
                self,
                __app_name__,
                "Todavia no hay nada que guardar: anade cuadros, textos, tablas o "
                "imagenes y vuelve a intentarlo.",
            )
            return False
        propuesto = os.path.splitext(self.view.document.name)[0]
        nombre, ok = QInputDialog.getText(
            self, "Guardar como plantilla", "Nombre de la plantilla:", text=propuesto
        )
        if not ok or not nombre.strip():
            return False
        try:
            ruta = save_template(
                self._ensure_templates_dir(),
                nombre,
                anotaciones,
                self.view.document.page_sizes(),
            )
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        self.statusBar().showMessage(
            f"Plantilla guardada: {os.path.basename(ruta)}", 5000
        )
        return True

    def apply_template(self, path: str) -> bool:
        """Coloca las anotaciones de una plantilla sobre el documento abierto."""
        if not self.view.has_document():
            return False
        try:
            nombre, _paginas, anotaciones = load_template(path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        colocadas = self.view.apply_template(anotaciones)
        self.statusBar().showMessage(
            f"Plantilla '{nombre}': {colocadas} anotaciones colocadas desde la pagina "
            f"{self.view.current_page + 1}",
            6000,
        )
        return colocadas > 0

    def new_from_template(self, path: str) -> bool:
        """Crea un documento nuevo con las paginas y anotaciones de la plantilla."""
        try:
            nombre, paginas, anotaciones = load_template(path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        if not self._confirm_discard():
            return False
        anterior = self.view.document
        tamano = paginas[0] if paginas else self.new_page_size
        documento = PdfDocument.blank(1, tamano, title=f"{nombre}.pdf")
        for ancho, alto in paginas[1:]:
            documento.add_blank_page(size=(ancho, alto))
        self.view.set_document(documento)
        if anterior is not None:
            anterior.close()
        self.view.apply_template(anotaciones, first_page=0)
        self._modified = False
        self.view.undo_stack.setClean()
        self._build_thumbnails()
        self._update_title()
        self._update_actions()
        self.statusBar().showMessage(f"Documento nuevo desde la plantilla '{nombre}'", 6000)
        self.documentChanged.emit()
        return True

    def delete_template(self, plantilla) -> bool:
        from ..templates import delete_template as borrar

        respuesta = QMessageBox.question(
            self, __app_name__, f"Eliminar la plantilla '{plantilla.name}'?"
        )
        if respuesta != QMessageBox.Yes:
            return False
        try:
            borrar(plantilla.path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        self.statusBar().showMessage(f"Plantilla eliminada: {plantilla.name}", 4000)
        return True

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir PDF",
            self.settings.last_dir() or os.path.expanduser("~"),
            "Documentos PDF (*.pdf);;Todos los archivos (*)",
        )
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> bool:
        """Abre un archivo pidiendo confirmacion si hay cambios sin guardar."""
        if not self._confirm_discard():
            return False
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            QMessageBox.warning(self, __app_name__, f"No existe el archivo:\n{path}")
            return False
        password = ""
        while True:
            try:
                document = PdfDocument.open(path, password=password)
                break
            except PasswordRequired:
                password, ok = QInputDialog.getText(
                    self,
                    "Documento protegido",
                    f"Contrasena para {os.path.basename(path)}:",
                    QLineEdit.Password,
                )
                if not ok:
                    return False
            except PdfError as exc:
                QMessageBox.critical(self, __app_name__, str(exc))
                return False

        old = self.view.document
        self.view.set_document(document)
        if old is not None:
            old.close()
        self._modified = False
        self.view.undo_stack.setClean()
        self.settings.set_last_dir(os.path.dirname(path))
        self._refresh_recent_menu(self.settings.push_recent(path))
        self._build_thumbnails()
        self._update_title()
        self._update_actions()
        self.statusBar().showMessage(f"Abierto: {path}", 5000)
        self.documentChanged.emit()
        return True

    def close_document(self) -> bool:
        if not self._confirm_discard():
            return False
        document = self.view.document
        self.view.set_document(None)
        if document is not None:
            document.close()
        self.thumb_list.clear()
        self._thumb_queue.clear()
        self._modified = False
        self._update_title()
        self._update_actions()
        return True

    def save(self) -> bool:
        document = self.view.document
        if document is None:
            return False
        if not document.path:
            return self.save_as()
        return self._write_to(document.path)

    def save_as(self) -> bool:
        document = self.view.document
        if document is None:
            return False
        suggestion = document.path or os.path.join(
            self.settings.last_dir() or os.path.expanduser("~"), "documento.pdf"
        )
        if document.path:
            base, ext = os.path.splitext(document.path)
            suggestion = f"{base}-anotado{ext or '.pdf'}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF como", suggestion, "Documentos PDF (*.pdf)"
        )
        if not path:
            return False
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        return self._write_to(path)

    def _write_to(self, path: str) -> bool:
        document = self.view.document
        if document is None:
            return False
        try:
            document.save_as(path, self.view.annotations())
        except PdfError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        self._modified = False
        self.view.undo_stack.setClean()
        self.settings.set_last_dir(os.path.dirname(path))
        self._refresh_recent_menu(self.settings.push_recent(path))
        self._update_title()
        self.statusBar().showMessage(f"Guardado: {path}", 5000)
        return True

    def print_file(self) -> None:
        document = self.view.document
        if document is None:
            return
        try:
            printed = print_document(
                self, document, self.view.annotations(), self.view.current_page
            )
        except PdfError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return
        if printed:
            self.statusBar().showMessage("Documento enviado a la impresora", 5000)

    def preview_print(self) -> None:
        document = self.view.document
        if document is None:
            return
        try:
            print_preview(self, document, self.view.annotations())
        except PdfError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))

    # ------------------------------------------------------------------ recientes
    def _refresh_recent_menu(self, files: list[str] | None = None) -> None:
        files = files if files is not None else self.settings.recent_files()
        self.recent_menu.clear()
        existing = [p for p in files if os.path.isfile(p)]
        for index, path in enumerate(existing, start=1):
            act = QAction(f"&{index}  {os.path.basename(path)}", self)
            act.setStatusTip(path)
            act.triggered.connect(lambda checked=False, p=path: self.open_path(p))
            self.recent_menu.addAction(act)
        self.recent_menu.setEnabled(bool(existing))
        if existing:
            self.recent_menu.addSeparator()
            clear = QAction("Vaciar la lista", self)
            clear.triggered.connect(self._clear_recent)
            self.recent_menu.addAction(clear)

    def _clear_recent(self) -> None:
        self.settings.clear_recent()
        self._refresh_recent_menu([])

    # ------------------------------------------------------------------ miniaturas
    def _build_thumbnails(self) -> None:
        self.thumb_list.clear()
        self._thumb_queue.clear()
        document = self.view.document
        if document is None:
            return
        placeholder = QPixmap(THUMB_WIDTH, int(THUMB_WIDTH * 1.4))
        placeholder.fill(QColor("#ffffff"))
        for index in range(document.page_count):
            item = QListWidgetItem(QIcon(placeholder), str(index + 1))
            item.setTextAlignment(Qt.AlignHCenter)
            self.thumb_list.addItem(item)
            self._thumb_queue.append(index)
        self.thumb_list.setCurrentRow(0)
        self._thumb_timer.start()

    def _render_next_thumbnail(self) -> None:
        document = self.view.document
        if document is None or not self._thumb_queue:
            self._thumb_timer.stop()
            return
        for _ in range(2):
            if not self._thumb_queue:
                break
            index = self._thumb_queue.popleft()
            if index >= self.thumb_list.count():
                continue
            width, height = document.page_size(index)
            if width <= 0:
                continue
            scale = THUMB_WIDTH / width
            try:
                page = document.render_page(index, scale)
            except Exception:  # pragma: no cover - PDF danado
                continue
            image = QImage(
                page.samples, page.width, page.height, page.stride, QImage.Format_RGB888
            )
            item = self.thumb_list.item(index)
            if item is not None:
                item.setIcon(QIcon(QPixmap.fromImage(image.copy())))
        if not self._thumb_queue:
            self._thumb_timer.stop()

    def _on_thumbnail_selected(self, row: int) -> None:
        if row >= 0 and row != self.view.current_page:
            self.view.go_to_page(row)

    # ------------------------------------------------------------------ busqueda
    def show_search(self) -> None:
        self.toolbar_search.setVisible(True)
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def close_search(self) -> None:
        """Cierra la barra y quita el resaltado amarillo de los resultados."""
        self.view.clear_search()
        self.search_label.setText("  ")
        self.toolbar_search.setVisible(False)
        self.view.setFocus()

    def _on_search_text_changed(self, texto: str) -> None:
        if not texto.strip():
            self.view.clear_search()
            self.search_label.setText("  ")

    def run_search(self) -> None:
        document = self.view.document
        if document is None:
            return
        needle = self.search_edit.text().strip()
        if not needle:
            self.view.clear_search()
            self.search_label.setText("  ")
            return
        hits = document.search(needle)
        self.view.set_search_hits(hits)
        if hits:
            self.search_label.setText(f"  {self.view.hit_index + 1} de {len(hits)}  ")
        else:
            self.search_label.setText("  Sin resultados  ")
            self.statusBar().showMessage(f"No se encontro '{needle}'", 4000)

    # ------------------------------------------------------------------ vista
    def goto_page_dialog(self) -> None:
        if not self.view.has_document():
            return
        page, ok = QInputDialog.getInt(
            self,
            "Ir a la pagina",
            f"Numero de pagina (1-{self.view.page_count}):",
            self.view.current_page + 1,
            1,
            self.view.page_count,
        )
        if ok:
            self.view.go_to_page(page - 1)

    def toggle_fullscreen(self, checked: bool) -> None:
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def toggle_thumbnails(self, checked: bool) -> None:
        self.thumb_dock.setVisible(checked)
        self.settings.set_show_thumbnails(checked)

    def delete_selection(self) -> None:
        if not self.view.delete_selected():
            self.statusBar().showMessage("No hay ninguna anotacion seleccionada", 3000)

    # ------------------------------------------------------------------ estado
    def _on_page_changed(self, index: int) -> None:
        self._updating_page_box = True
        self.page_spin.setValue(index + 1)
        self._updating_page_box = False
        if self.thumb_list.currentRow() != index:
            self.thumb_list.blockSignals(True)
            self.thumb_list.setCurrentRow(index)
            self.thumb_list.blockSignals(False)

    def _on_page_spin(self, value: int) -> None:
        if not self._updating_page_box:
            self.view.go_to_page(value - 1)

    def _on_zoom_changed(self, zoom: float) -> None:
        self.zoom_label.setText(f"{zoom * 100:.0f} %")

    def _on_modified(self) -> None:
        self._modified = True
        self._update_title()
        self._update_actions()

    def _update_title(self) -> None:
        document = self.view.document
        if document is None:
            self.setWindowTitle(__app_name__)
            return
        dirty = "*" if self._is_dirty() else ""
        self.setWindowTitle(f"{dirty}{document.name} - {__app_name__}")

    def _is_dirty(self) -> bool:
        return self._modified and not self.view.undo_stack.isClean()

    def _update_actions(self) -> None:
        has_doc = self.view.has_document()
        for act in (
            self.act_save, self.act_save_as, self.act_print, self.act_preview,
            self.act_close, self.act_find, self.act_find_next, self.act_find_prev,
            self.act_zoom_in, self.act_zoom_out, self.act_zoom_reset,
            self.act_fit_width, self.act_fit_page, self.act_prev_page,
            self.act_next_page, self.act_goto, self.act_page_add,
            self.act_page_insert, self.act_page_duplicate, self.act_page_up,
            self.act_page_down,
        ):
            act.setEnabled(has_doc)
        for act in self.tool_group.actions():
            act.setEnabled(has_doc)
        editando = self.view.is_editing_text
        self.act_delete.setEnabled(bool(self.view.selected_items()) and not editando)
        self.act_page_delete.setEnabled(has_doc and self.view.page_count > 1)
        self.act_select_all.setEnabled(has_doc and not editando)
        count = self.view.annotation_count()
        self.page_spin.setEnabled(has_doc)
        self.page_spin.setMaximum(max(1, self.view.page_count))
        self.page_label.setText(f"de {self.view.page_count}")
        self.info_label.setText(
            f"{count} anotacion{'es' if count != 1 else ''}" if has_doc else ""
        )

    # ------------------------------------------------------------------ cierre
    def _confirm_discard(self) -> bool:
        if not self._is_dirty():
            return True
        answer = QMessageBox.question(
            self,
            __app_name__,
            "El documento tiene anotaciones sin guardar.\n\nQuieres guardarlas?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if answer == QMessageBox.Save:
            return self.save()
        return answer == QMessageBox.Discard

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        self.settings.set_window_geometry(self.saveGeometry())
        self.settings.set_window_state(self.saveState())
        self.settings.set_show_thumbnails(self.thumb_dock.isVisible())
        self.settings.sync()
        document = self.view.document
        if document is not None:
            document.close()
        event.accept()

    # ------------------------------------------------------------------ arrastrar
    IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp")

    def _dropped_files(self, event) -> list[str]:
        if not event.mimeData().hasUrls():
            return []
        return [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]

    def dragEnterEvent(self, event) -> None:
        for path in self._dropped_files(event):
            bajo = path.lower()
            if bajo.endswith(".pdf") or bajo.endswith(self.IMAGE_SUFFIXES):
                event.acceptProposedAction()
                return
        event.ignore()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event) -> None:
        for path in self._dropped_files(event):
            bajo = path.lower()
            if bajo.endswith(".pdf"):
                self.open_path(path)
                event.acceptProposedAction()
                return
            if bajo.endswith(self.IMAGE_SUFFIXES) and self.view.has_document():
                self.insert_image_from_file(path, event.position().toPoint())
                event.acceptProposedAction()
                return

    def insert_image_from_file(self, path: str, window_pos=None) -> bool:
        """Coloca una imagen del disco donde se haya soltado."""
        try:
            with open(path, "rb") as fh:
                datos = fh.read()
        except OSError as exc:
            QMessageBox.warning(self, __app_name__, f"No se pudo leer la imagen:\n{exc}")
            return False
        vista = self.view
        if window_pos is not None:
            punto = vista.viewport().mapFrom(self, window_pos)
            escena = vista.mapToScene(punto)
        else:
            escena = vista.mapToScene(vista.viewport().rect().center())
        pagina = vista.nearest_page(escena)
        if pagina is None:
            return False
        vista.place_image(os.path.basename(path), datos, pagina.index, pagina.mapFromScene(escena))
        self.statusBar().showMessage(f"Imagen colocada: {os.path.basename(path)}", 4000)
        return True

    # ------------------------------------------------------------------ ayuda
    def show_about(self) -> None:
        AboutDialog(self).exec()

    def show_help(self) -> None:
        HelpDialog(self).exec()


__all__ = ["MainWindow", "AboutDialog", "HelpDialog"]
