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
from ..document import PasswordRequired, PdfDocument, PdfError
from ..printing import print_document, print_preview
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
            <h3>Abrir e imprimir</h3>
            <ul>
              <li><b>Ctrl+O</b> abre un PDF. Tambien puedes arrastrarlo sobre la ventana.</li>
              <li><b>Ctrl+P</b> imprime. La vista previa muestra el documento con las
                  anotaciones tal y como saldran en papel.</li>
              <li><b>Ctrl+S</b> guarda las anotaciones dentro del PDF.</li>
            </ul>
            <h3>Anotar</h3>
            <ul>
              <li>Elige una herramienta en la barra: cuadro, resaltado, linea, flecha,
                  texto o dibujo a mano alzada.</li>
              <li>Arrastra sobre la pagina para crear la anotacion.</li>
              <li>Manten <b>Mayus</b> para cuadrados perfectos o lineas a 45 grados.</li>
              <li>Con la herramienta <b>Seleccionar</b> puedes mover, redimensionar
                  (tiradores azules) y borrar con <b>Supr</b>.</li>
              <li>Doble clic sobre un cuadro de texto para escribir dentro.</li>
              <li><b>Ctrl+Z</b> y <b>Ctrl+Y</b> deshacen y rehacen.</li>
            </ul>
            <h3>Moverse por el documento</h3>
            <ul>
              <li><b>Ctrl+rueda</b> hace zoom; <b>Ctrl+0</b> vuelve al 100%.</li>
              <li><b>Ctrl+F</b> busca texto; <b>F3</b> salta al siguiente resultado.</li>
              <li>La barra lateral de miniaturas permite saltar de pagina.</li>
              <li><b>Esc</b> vuelve siempre a la herramienta Seleccionar.</li>
            </ul>
            <h3>Como se guardan las anotaciones</h3>
            <p>El programa escribe anotaciones PDF estandar (cuadro, linea, texto libre,
            resaltado y tinta), asi que se ven igual en Adobe Reader, Edge o Firefox.
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

        tools.addSeparator()
        tools.addAction(self.act_delete)
        self.addToolBar(tools)
        self.toolbar_tools = tools

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
        close_action = QAction("Cerrar", self)
        close_action.setShortcut(QKeySequence("Esc"))
        close_action.triggered.connect(lambda: bar.setVisible(False))
        bar.addAction(close_action)
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
        self.color_button.setIcon(_swatch(color))
        self.fill_button.setIcon(_swatch(fill))
        for widget, value in (
            (self.width_spin, self.settings.tool_width()),
            (self.opacity_spin, int(round(self.settings.tool_opacity() * 100))),
            (self.font_spin, self.settings.tool_font_size()),
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

    def select_tool(self, tool: Tool) -> None:
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

    # ------------------------------------------------------------------ archivos
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
            self.act_next_page, self.act_goto,
        ):
            act.setEnabled(has_doc)
        for act in self.tool_group.actions():
            act.setEnabled(has_doc)
        editando = self.view.is_editing_text
        self.act_delete.setEnabled(bool(self.view.selected_items()) and not editando)
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
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf"):
                self.open_path(url.toLocalFile())
                event.acceptProposedAction()
                return

    # ------------------------------------------------------------------ ayuda
    def show_about(self) -> None:
        AboutDialog(self).exec()

    def show_help(self) -> None:
        HelpDialog(self).exec()


__all__ = ["MainWindow", "AboutDialog", "HelpDialog"]
