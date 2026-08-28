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

from .. import __app_name__, __url__, __version__
from ..config import PALETTE, Settings
from ..document import DEFAULT_PAGE_SIZE, PAGE_SIZES, PasswordRequired, PdfDocument, PdfError
from ..i18n import LANGUAGES, language, page_size_label, set_language, tr
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

#: Borde gris de las miniaturas. Sin el, una pagina en blanco es invisible
#: sobre el fondo claro del panel y parece que no se ha cargado nada.
THUMB_BORDER = "#9a9a9a"


def _framed(pixmap: QPixmap, fill: bool = False) -> QPixmap:
    """Devuelve la miniatura con un borde fino para que se vea el papel."""
    from PySide6.QtGui import QPainter, QPen

    if fill:
        pixmap.fill(QColor("#ffffff"))
    painter = QPainter(pixmap)
    painter.setPen(QPen(QColor(THUMB_BORDER), 1))
    painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)
    painter.end()
    return pixmap


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
    """Ventana de informacion del programa."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("about_title", app=__app_name__))
        self.resize(520, 380)
        layout = QVBoxLayout(self)
        header = QLabel()
        header.setPixmap(icons.icon("app").pixmap(64, 64))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        text = QTextBrowser()
        text.setOpenExternalLinks(True)
        text.setHtml(
            f"<h2 style='text-align:center;margin-bottom:0'>{__app_name__} {__version__}</h2>"
            f"<p style='text-align:center;color:#666'>{tr('about_tagline')}</p>"
            + tr("about_html", url=__url__)
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
        self.setWindowTitle(tr("help_title"))
        self.resize(660, 540)
        layout = QVBoxLayout(self)
        text = QTextBrowser()
        text.setHtml(tr("help_html"))
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
        set_language(self.settings.language())
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
        # Cada accion guarda las claves de su texto para poder retraducirse.
        self._action_keys: dict[QAction, tuple[str, str | None]] = {}

        def action(key, slot, icon_name=None, shortcut=None, tip=None, checkable=False):
            act = QAction(tr(key), self)
            if icon_name:
                act.setIcon(icons.icon(icon_name))
            if shortcut:
                act.setShortcut(shortcut)
            act.setCheckable(checkable)
            act.setStatusTip(tr(tip) if tip else tr(key))
            act.triggered.connect(slot)
            self._action_keys[act] = (key, tip)
            return act

        self.act_new = action("new", self.new_document, "new", QKeySequence.New, "new_tip")
        self.act_open = action("open", self.open_file_dialog, "open", QKeySequence.Open,
                               "open_tip")
        self.act_save = action("save", self.save, "save", QKeySequence.Save, "save_tip")
        self.act_save_as = action("save_as", self.save_as, "save_as",
                                  QKeySequence.SaveAs, "save_as_tip")
        self.act_print = action("print", self.print_file, "print", QKeySequence.Print,
                                "print_tip")
        self.act_preview = action("preview", self.preview_print,
                                  shortcut="Ctrl+Shift+P", tip="preview_tip")
        self.act_close = action("close_doc", self.close_document, shortcut="Ctrl+W")
        self.act_quit = action("quit", self.close, shortcut=QKeySequence.Quit)

        self.act_undo = self.view.undo_stack.createUndoAction(self, tr("undo"))
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setIcon(icons.icon("undo"))
        self.act_redo = self.view.undo_stack.createRedoAction(self, tr("redo"))
        self.act_redo.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Y")])
        self.act_redo.setIcon(icons.icon("redo"))

        self.act_delete = action("delete_sel", self.delete_selection, "delete",
                                 QKeySequence.Delete, "delete_sel_tip")
        self.act_select_all = action("select_all", self.view.select_all_annotations,
                                     shortcut=QKeySequence.SelectAll)
        self.act_find = action("find", self.show_search, "search",
                               QKeySequence.Find, "find_tip")
        self.act_find_next = action("find_next", self.view.next_hit,
                                    shortcut=QKeySequence.FindNext)
        self.act_find_prev = action("find_prev", self.view.previous_hit,
                                    shortcut=QKeySequence.FindPrevious)

        self.act_zoom_in = action("zoom_in", lambda: self.zoom_or_eraser(1),
                                  "zoom_in", QKeySequence.ZoomIn)
        self.act_zoom_in.setShortcuts([QKeySequence.ZoomIn, QKeySequence("Ctrl++")])
        self.act_zoom_out = action("zoom_out", lambda: self.zoom_or_eraser(-1),
                                   "zoom_out", QKeySequence.ZoomOut)
        self.act_zoom_reset = action("zoom_reset", self.view.reset_zoom, shortcut="Ctrl+0")
        self.act_fit_width = action("fit_width", self.view.fit_width, "fit_width",
                                    shortcut="Ctrl+1")
        self.act_fit_page = action("fit_page", self.view.fit_page, "fit_page",
                                   shortcut="Ctrl+2")
        self.act_prev_page = action("prev_page", self.view.previous_page, "prev",
                                    shortcut="Ctrl+Up")
        self.act_next_page = action("next_page", self.view.next_page, "next",
                                    shortcut="Ctrl+Down")
        self.act_goto = action("goto", self.goto_page_dialog, shortcut="Ctrl+G")
        self.act_fullscreen = action("fullscreen", self.toggle_fullscreen,
                                     shortcut="F11", checkable=True)
        self.act_thumbnails = action("thumbnails", self.toggle_thumbnails,
                                     shortcut="F9", checkable=True)

        self.act_page_add = action("page_add", self.add_page_end, shortcut="Ctrl+Shift+N")
        self.act_page_insert = action("page_insert", self.insert_page_here)
        self.act_page_duplicate = action("page_duplicate", self.duplicate_current_page)
        self.act_page_delete = action("page_delete", self.delete_current_page)
        self.act_rotate_left = action("page_rotate_left",
                                      lambda: self.rotate_current_page(-90))
        self.act_rotate_right = action("page_rotate_right",
                                       lambda: self.rotate_current_page(90))
        self.act_rotate_180 = action("page_rotate_180",
                                     lambda: self.rotate_current_page(180))
        self.act_page_up = action("page_up", lambda: self.move_current_page(-1),
                                  shortcut="Ctrl+Shift+Up")
        self.act_page_down = action("page_down", lambda: self.move_current_page(1),
                                    shortcut="Ctrl+Shift+Down")

        self.act_help = action("help", self.show_help, shortcut=QKeySequence.HelpContents)
        self.act_about = action("about", self.show_about)
        self.act_about.setText(tr("about", app=__app_name__))
        self.act_website = action("website", lambda: QDesktopServices.openUrl(QUrl(__url__)))

        # Herramientas (excluyentes entre si)
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_actions = {}
        self.tool_keys = {
            Tool.SELECT: ("tool_select", "select", "S"),
            Tool.PAN: ("tool_pan", "hand", "H"),
            Tool.RECT: ("tool_rect", "rect", "R"),
            Tool.HIGHLIGHT: ("tool_highlight", "highlight", "M"),
            Tool.LINE: ("tool_line", "line", "L"),
            Tool.ARROW: ("tool_arrow", "arrow", "F"),
            Tool.TEXT: ("tool_text", "text", "T"),
            Tool.INK: ("tool_ink", "ink", "D"),
            Tool.TABLE: ("tool_table", "table", "A"),
            Tool.IMAGE: ("tool_image", "image", "I"),
            Tool.ERASER: ("tool_eraser", "eraser", "E"),
        }
        for tool, (clave, icon_name, key) in self.tool_keys.items():
            act = QAction(icons.icon(icon_name), tr(clave), self)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(key))
            act.setStatusTip(tr("tool_status", name=tr(clave).replace("&", ""), key=key))
            act.triggered.connect(lambda checked=False, t=tool: self.select_tool(t))
            self.tool_group.addAction(act)
            self.tool_actions[tool] = act
        self.tool_actions[Tool.SELECT].setChecked(True)

    def _create_menus(self) -> None:
        self._menu_keys = {}
        file_menu = self.menuBar().addMenu(tr("menu_file"))
        self._menu_keys[file_menu] = "menu_file"
        file_menu.addAction(self.act_new)
        file_menu.addAction(self.act_open)
        self.recent_menu = QMenu(tr("recent"), self)
        self._menu_keys[self.recent_menu] = "recent"
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

        edit_menu = self.menuBar().addMenu(tr("menu_edit"))
        self._menu_keys[edit_menu] = "menu_edit"
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_delete)
        edit_menu.addAction(self.act_select_all)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_find)
        edit_menu.addAction(self.act_find_next)
        edit_menu.addAction(self.act_find_prev)

        view_menu = self.menuBar().addMenu(tr("menu_view"))
        self._menu_keys[view_menu] = "menu_view"
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

        doc_menu = self.menuBar().addMenu(tr("menu_document"))
        self._menu_keys[doc_menu] = "menu_document"
        doc_menu.addAction(self.act_page_add)
        doc_menu.addAction(self.act_page_insert)
        doc_menu.addAction(self.act_page_duplicate)
        doc_menu.addAction(self.act_page_delete)
        doc_menu.addSeparator()
        doc_menu.addAction(self.act_page_up)
        doc_menu.addAction(self.act_page_down)
        doc_menu.addSeparator()
        girar_menu = doc_menu.addMenu(tr("page_rotate_menu"))
        girar_menu.addAction(self.act_rotate_left)
        girar_menu.addAction(self.act_rotate_right)
        girar_menu.addAction(self.act_rotate_180)
        self.rotate_menu = girar_menu
        self._menu_keys[girar_menu] = "page_rotate_menu"
        doc_menu.addSeparator()
        tamano_menu = doc_menu.addMenu(tr("page_size_menu"))
        self._menu_keys[tamano_menu] = "page_size_menu"
        self.page_size_group = QActionGroup(self)
        self.page_size_group.setExclusive(True)
        elegido = self.settings.value("document/page_size", DEFAULT_PAGE_SIZE)
        self.page_size_actions = {}
        for nombre in PAGE_SIZES:
            act = QAction(page_size_label(nombre), self)
            act.setCheckable(True)
            act.setChecked(nombre == elegido)
            act.triggered.connect(lambda checked=False, n=nombre: self._set_page_size(n))
            self.page_size_group.addAction(act)
            tamano_menu.addAction(act)
            self.page_size_actions[nombre] = act
        self.new_page_size = str(elegido)

        doc_menu.addSeparator()
        self.templates_menu = QMenu(tr("templates"), self)
        self._menu_keys[self.templates_menu] = "templates"
        doc_menu.addMenu(self.templates_menu)
        self.templates_menu.aboutToShow.connect(self._refresh_templates_menu)
        self._refresh_templates_menu()

        tools_menu = self.menuBar().addMenu(tr("menu_tools"))
        self._menu_keys[tools_menu] = "menu_tools"
        for act in self.tool_group.actions():
            tools_menu.addAction(act)

        help_menu = self.menuBar().addMenu(tr("menu_help"))
        self._menu_keys[help_menu] = "menu_help"
        idioma_menu = help_menu.addMenu(tr("language"))
        self._menu_keys[idioma_menu] = "language"
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.language_actions = {}
        for codigo, nombre in LANGUAGES.items():
            act = QAction(nombre, self)
            act.setCheckable(True)
            act.setChecked(codigo == language())
            act.triggered.connect(lambda checked=False, c=codigo: self.set_language(c))
            self.language_group.addAction(act)
            idioma_menu.addAction(act)
            self.language_actions[codigo] = act
        help_menu.addSeparator()
        help_menu.addAction(self.act_help)
        help_menu.addAction(self.act_website)
        help_menu.addSeparator()
        help_menu.addAction(self.act_about)

    def _create_toolbars(self) -> None:
        bar = QToolBar(tr("toolbar_main"), self)
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

        tools = QToolBar(tr("toolbar_tools"), self)
        tools.setObjectName("toolbar_tools")
        tools.setIconSize(QSize(22, 22))
        for act in self.tool_group.actions():
            tools.addAction(act)
        tools.addSeparator()

        # Color del trazo
        self.color_button = QToolButton(self)
        self.color_button.setPopupMode(QToolButton.InstantPopup)
        self.color_button.setToolTip(tr("color_tip"))
        self.color_button.setMenu(self._color_menu(self._set_color, allow_none=False))
        tools.addWidget(self.color_button)

        # Color de relleno
        self.fill_button = QToolButton(self)
        self.fill_button.setPopupMode(QToolButton.InstantPopup)
        self.fill_button.setToolTip(tr("fill_tip"))
        self.fill_button.setMenu(self._color_menu(self._set_fill, allow_none=True))
        tools.addWidget(self.fill_button)

        self.lbl_width = QLabel(tr("width"))
        tools.addWidget(self.lbl_width)
        self.width_spin = QDoubleSpinBox(self)
        self.width_spin.setRange(0.0, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setDecimals(1)
        self.width_spin.setSuffix(" pt")
        self.width_spin.setToolTip(tr("width_tip"))
        self.width_spin.valueChanged.connect(self._set_width)
        tools.addWidget(self.width_spin)

        self.lbl_opacity = QLabel(tr("opacity"))
        tools.addWidget(self.lbl_opacity)
        self.opacity_spin = QSpinBox(self)
        self.opacity_spin.setRange(10, 100)
        self.opacity_spin.setSingleStep(5)
        self.opacity_spin.setSuffix(" %")
        self.opacity_spin.setToolTip(tr("opacity_tip"))
        self.opacity_spin.valueChanged.connect(self._set_opacity)
        tools.addWidget(self.opacity_spin)

        self.lbl_font = QLabel(tr("font_size"))
        tools.addWidget(self.lbl_font)
        self.font_spin = QDoubleSpinBox(self)
        self.font_spin.setRange(4.0, 96.0)
        self.font_spin.setSingleStep(1.0)
        self.font_spin.setDecimals(0)
        self.font_spin.setSuffix(" pt")
        self.font_spin.setToolTip(tr("font_size_tip"))
        self.font_spin.valueChanged.connect(self._set_font_size)
        tools.addWidget(self.font_spin)

        self.addToolBar(tools)
        self.toolbar_tools = tools

        # Los ajustes de estilo van en su propia fila: si no, la barra se
        # desborda en pantallas normales y aparece el boton de "mas".
        estilo = QToolBar(tr("toolbar_style"), self)
        estilo.setObjectName("toolbar_style")
        estilo.setIconSize(QSize(22, 22))
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(estilo)
        self.toolbar_style = estilo
        tools = estilo

        self.font_combo = QComboBox(self)
        for familia in (Font.SANS, Font.SERIF, Font.MONO):
            self.font_combo.addItem(tr(f"font_{familia.name.lower()}"), familia.value)
        self.font_combo.setToolTip(tr("font_tip"))
        self.font_combo.currentIndexChanged.connect(self._set_font_family)
        tools.addWidget(self.font_combo)

        self.act_bold = QAction(icons.icon("bold"), tr("bold"), self)
        self.act_bold.setCheckable(True)
        self.act_bold.setShortcut(QKeySequence.Bold)
        self.act_bold.setToolTip(tr("bold_tip"))
        self.act_bold.triggered.connect(self._set_bold)
        tools.addAction(self.act_bold)

        self.act_italic = QAction(icons.icon("italic"), tr("italic"), self)
        self.act_italic.setCheckable(True)
        self.act_italic.setShortcut(QKeySequence.Italic)
        self.act_italic.setToolTip(tr("italic_tip"))
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
            act = QAction(icons.icon(nombre), tr(f"act_align_{alineacion.name.lower()}"), self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked=False, a=alineacion: self._set_align(a))
            self.align_group.addAction(act)
            self.align_actions[alineacion] = act
            tools.addAction(act)
        self.align_actions[Align.LEFT].setChecked(True)

        tools.addSeparator()
        self.lbl_table = QLabel(tr("table_label"))
        tools.addWidget(self.lbl_table)
        self.rows_spin = QSpinBox(self)
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setPrefix(tr("rows_prefix"))
        self.rows_spin.setToolTip(tr("rows_tip"))
        self.rows_spin.valueChanged.connect(self._set_rows)
        tools.addWidget(self.rows_spin)

        self.cols_spin = QSpinBox(self)
        self.cols_spin.setRange(1, 30)
        self.cols_spin.setPrefix(tr("cols_prefix"))
        self.cols_spin.setToolTip(tr("cols_tip"))
        self.cols_spin.valueChanged.connect(self._set_cols)
        tools.addWidget(self.cols_spin)

        tools.addSeparator()
        tools.addAction(self.act_delete)

        self._create_search_bar()

    def _create_search_bar(self) -> None:
        bar = QToolBar(tr("toolbar_search"), self)
        bar.setObjectName("toolbar_search")
        bar.setIconSize(QSize(18, 18))
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(tr("search_placeholder"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(360)
        self.search_edit.returnPressed.connect(self.run_search)
        bar.addWidget(self.search_edit)
        bar.addAction(self.act_find_prev)
        bar.addAction(self.act_find_next)
        self.search_label = QLabel("  ")
        bar.addWidget(self.search_label)
        close_action = QAction(tr("search_close"), self)
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
            act = QAction(_swatch(None), tr("no_fill"), self)
            act.triggered.connect(lambda: slot(None))
            menu.addAction(act)
            menu.addSeparator()
        for name, hexvalue in PALETTE:
            act = QAction(_swatch(QColor(hexvalue)), name, self)
            act.triggered.connect(lambda checked=False, h=hexvalue: slot(QColor(h)))
            menu.addAction(act)
        menu.addSeparator()
        more = QAction(tr("more_colours"), self)
        more.triggered.connect(lambda: self._pick_custom_color(slot))
        menu.addAction(more)
        return menu

    def _pick_custom_color(self, slot) -> None:
        color = QColorDialog.getColor(QColor("#d81b1b"), self, tr("pick_colour"))
        if color.isValid():
            slot(color)

    def _create_thumbnails(self) -> None:
        from PySide6.QtWidgets import QDockWidget

        from .thumbnails import ThumbnailList

        self.thumb_list = ThumbnailList(THUMB_WIDTH, self)
        self.thumb_list.currentRowChanged.connect(self._on_thumbnail_selected)
        self.thumb_list.page_moved.connect(self._on_thumbnail_dropped)
        self.thumb_list.customContextMenuRequested.connect(self._thumbnail_menu)

        dock = QDockWidget(tr("pages_dock"), self)
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
        self.page_spin.setToolTip(tr("status_page"))
        self.page_spin.setFixedWidth(70)
        self.page_spin.valueChanged.connect(self._on_page_spin)
        self.page_label = QLabel(tr("status_of", total=0))
        self.zoom_label = QLabel("100 %")
        self.info_label = QLabel("")
        self.lbl_page = QLabel(tr("status_page"))
        status.addPermanentWidget(self.lbl_page)
        status.addPermanentWidget(self.page_spin)
        status.addPermanentWidget(self.page_label)
        status.addPermanentWidget(QLabel("   "))
        status.addPermanentWidget(self.zoom_label)
        status.addWidget(self.info_label)
        status.showMessage(tr("status_start"), 6000)

    def _connect_view(self) -> None:
        self.view.pageChanged.connect(self._on_page_changed)
        self.view.zoomChanged.connect(self._on_zoom_changed)
        self.view.eraserSizeChanged.connect(self._on_eraser_size)
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
            self.statusBar().showMessage(tr("status_editing"), 4000)

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

    def choose_image(self) -> bool:
        """Pide una imagen y la deja lista para colocarla. False si se cancela."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("image_title"),
            self.settings.last_dir() or os.path.expanduser("~"),
            tr("image_filter"),
        )
        if not path:
            return False
        try:
            with open(path, "rb") as fh:
                datos = fh.read()
        except OSError as exc:
            QMessageBox.warning(self, __app_name__, tr("image_unreadable", error=exc))
            return False
        if QPixmap.fromImage(QImage.fromData(datos)).isNull():
            QMessageBox.warning(self, __app_name__, tr("image_invalid"))
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
            self.statusBar().showMessage(tr("hint_highlight"), 4000)
        elif tool is Tool.TEXT:
            self.statusBar().showMessage(tr("hint_text"), 5000)
        elif tool is Tool.IMAGE:
            nombre = (self.view.style_defaults.get("image") or ("", b""))[0]
            self.statusBar().showMessage(tr("hint_image", name=nombre), 6000)
        elif tool is Tool.TABLE:
            self.statusBar().showMessage(
                tr("hint_table", rows=self.rows_spin.value(), cols=self.cols_spin.value()),
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
        self.statusBar().showMessage(tr("status_new"), 6000)
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
            QMessageBox.information(self, __app_name__, tr("last_page"))
            return
        actual = self.view.current_page
        anotaciones = len(self.view.items_on_page(actual))
        aviso = tr("delete_page_ask", page=actual + 1, total=self.view.page_count)
        if anotaciones:
            aviso += tr("delete_page_annots", count=anotaciones)
        aviso += tr("delete_page_undo")
        if QMessageBox.question(self, __app_name__, aviso) != QMessageBox.Yes:
            return
        self.view.delete_page(actual)
        self._after_page_change(min(actual, self.view.page_count - 1))

    def zoom_or_eraser(self, delta: int) -> None:
        """Ctrl+ y Ctrl-: cambian la goma si esta activa, si no el zoom.

        Con la goma en la mano lo que se quiere ajustar es su tamano, igual
        que en cualquier programa de dibujo.
        """
        if self.view.tool is Tool.ERASER:
            self.view.step_eraser_size(delta)
            return
        self.view.zoom_in() if delta > 0 else self.view.zoom_out()

    def _on_eraser_size(self, size: float) -> None:
        self.statusBar().showMessage(tr("eraser_size", size=round(size)), 4000)

    def rotate_current_page(self, delta: int) -> None:
        if self.view.has_document():
            actual = self.view.current_page
            self.view.rotate_page(actual, delta)
            self._after_page_change(actual)

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
        guardar = QAction(tr("template_save"), self)
        guardar.setStatusTip(tr("template_save_tip"))
        guardar.triggered.connect(self.save_as_template)
        guardar.setEnabled(self.view.has_document())
        menu.addAction(guardar)
        menu.addSeparator()

        plantillas = list_templates(self.templates_dir())
        if not plantillas:
            vacio = QAction(tr("template_none"), self)
            vacio.setEnabled(False)
            menu.addAction(vacio)
        else:
            nuevo = menu.addMenu(tr("template_new"))
            aplicar = menu.addMenu(tr("template_apply"))
            aplicar.setEnabled(self.view.has_document())
            for plantilla in plantillas:
                detalle = tr("template_detail", count=plantilla.annotations)
                if plantilla.pages:
                    detalle = tr(
                        "template_detail_pages",
                        pages=plantilla.pages,
                        count=plantilla.annotations,
                    )
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

            borrar = menu.addMenu(tr("template_delete"))
            for plantilla in plantillas:
                act = QAction(plantilla.name, self)
                act.triggered.connect(
                    lambda checked=False, p=plantilla: self.delete_template(p)
                )
                borrar.addAction(act)

        menu.addSeparator()
        carpeta = QAction(tr("template_folder"), self)
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
                tr("template_empty"),
            )
            return False
        propuesto = os.path.splitext(self.view.document.name)[0]
        nombre, ok = QInputDialog.getText(
            self, tr("template_name_title"), tr("template_name_label"), text=propuesto
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
            tr("template_saved", name=os.path.basename(ruta)), 5000
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
            tr("template_applied", name=nombre, count=colocadas,
               page=self.view.current_page + 1),
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
        self.statusBar().showMessage(tr("template_new_done", name=nombre), 6000)
        self.documentChanged.emit()
        return True

    def delete_template(self, plantilla) -> bool:
        from ..templates import delete_template as borrar

        respuesta = QMessageBox.question(
            self, __app_name__, tr("template_delete_ask", name=plantilla.name)
        )
        if respuesta != QMessageBox.Yes:
            return False
        try:
            borrar(plantilla.path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        self.statusBar().showMessage(tr("template_deleted", name=plantilla.name), 4000)
        return True

    # ------------------------------------------------------------------ idioma
    def set_language(self, code: str) -> None:
        """Cambia el idioma de la interfaz y la retraduce al vuelo."""
        set_language(code)
        self.settings.set_language(code)
        if code in self.language_actions:
            self.language_actions[code].setChecked(True)
        self.retranslate()
        self.statusBar().showMessage(tr("language_changed"), 4000)

    def retranslate(self) -> None:
        """Vuelve a poner todos los textos en el idioma activo."""
        for act, (clave, tip) in self._action_keys.items():
            act.setText(tr(clave, app=__app_name__))
            act.setStatusTip(tr(tip) if tip else tr(clave, app=__app_name__))
        for menu, clave in self._menu_keys.items():
            menu.setTitle(tr(clave))
        for nombre, act in getattr(self, "page_size_actions", {}).items():
            act.setText(page_size_label(nombre))
        for tool, (clave, _icono, key) in self.tool_keys.items():
            accion = self.tool_actions[tool]
            accion.setText(tr(clave))
            accion.setStatusTip(
                tr("tool_status", name=tr(clave).replace("&", ""), key=key)
            )
        self.act_undo.setText(tr("undo"))
        self.act_redo.setText(tr("redo"))
        self.act_bold.setText(tr("bold"))
        self.act_bold.setToolTip(tr("bold_tip"))
        self.act_italic.setText(tr("italic"))
        self.act_italic.setToolTip(tr("italic_tip"))
        for alineacion, accion in self.align_actions.items():
            accion.setText(tr(f"act_align_{alineacion.name.lower()}"))
        self.act_close_search.setText(tr("search_close"))
        self.search_edit.setPlaceholderText(tr("search_placeholder"))
        self.color_button.setToolTip(tr("color_tip"))
        self.fill_button.setToolTip(tr("fill_tip"))
        self.color_button.setMenu(self._color_menu(self._set_color, allow_none=False))
        self.fill_button.setMenu(self._color_menu(self._set_fill, allow_none=True))
        self.lbl_width.setText(tr("width"))
        self.width_spin.setToolTip(tr("width_tip"))
        self.lbl_opacity.setText(tr("opacity"))
        self.opacity_spin.setToolTip(tr("opacity_tip"))
        self.lbl_font.setText(tr("font_size"))
        self.font_spin.setToolTip(tr("font_size_tip"))
        self.font_combo.setToolTip(tr("font_tip"))
        indice = self.font_combo.currentIndex()
        self.font_combo.blockSignals(True)
        for posicion, familia in enumerate((Font.SANS, Font.SERIF, Font.MONO)):
            self.font_combo.setItemText(posicion, tr(f"font_{familia.name.lower()}"))
        self.font_combo.setCurrentIndex(indice)
        self.font_combo.blockSignals(False)
        self.lbl_table.setText(tr("table_label"))
        self.rows_spin.setPrefix(tr("rows_prefix"))
        self.rows_spin.setToolTip(tr("rows_tip"))
        self.cols_spin.setPrefix(tr("cols_prefix"))
        self.cols_spin.setToolTip(tr("cols_tip"))
        self.lbl_page.setText(tr("status_page"))
        self.page_spin.setToolTip(tr("status_page"))
        self.thumb_dock.setWindowTitle(tr("pages_dock"))
        self.toolbar_main.setWindowTitle(tr("toolbar_main"))
        self.toolbar_tools.setWindowTitle(tr("toolbar_tools"))
        self.toolbar_style.setWindowTitle(tr("toolbar_style"))
        self.toolbar_search.setWindowTitle(tr("toolbar_search"))
        self._refresh_recent_menu()
        self._update_actions()
        self._update_title()

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("open_title"),
            self.settings.last_dir() or os.path.expanduser("~"),
            tr("pdf_filter"),
        )
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> bool:
        """Abre un archivo pidiendo confirmacion si hay cambios sin guardar."""
        if not self._confirm_discard():
            return False
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            QMessageBox.warning(self, __app_name__, tr("no_such_file", path=path))
            return False
        password = ""
        while True:
            try:
                document = PdfDocument.open(path, password=password)
                break
            except PasswordRequired:
                password, ok = QInputDialog.getText(
                    self,
                    tr("password_title"),
                    tr("password_label", name=os.path.basename(path)),
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
        self.statusBar().showMessage(tr("status_opened", path=path), 5000)
        self.documentChanged.emit()
        return True

    def close_document(self) -> bool:
        if not self._confirm_discard():
            return False
        document = self.view.document
        self.view.set_document(None)
        if document is not None:
            document.close()
        self._thumb_timer.stop()
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
            self, tr("save_title"), suggestion, tr("pdf_filter")
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
        self.statusBar().showMessage(tr("status_saved", path=path), 5000)
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
            self.statusBar().showMessage(tr("status_printed"), 5000)

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
            clear = QAction(tr("recent_clear"), self)
            clear.triggered.connect(self._clear_recent)
            self.recent_menu.addAction(clear)

    def _clear_recent(self) -> None:
        self.settings.clear_recent()
        self._refresh_recent_menu([])

    # ------------------------------------------------------------------ miniaturas
    def _build_thumbnails(self) -> None:
        # Se rehace la lista entera sin avisar: quien llama coloca despues la
        # pagina que toca, y sin esto el setCurrentRow(0) saltaria a la primera.
        bloqueado = self.thumb_list.blockSignals(True)
        try:
            self.thumb_list.clear()
            self._thumb_queue.clear()
            document = self.view.document
            if document is None:
                return
            placeholder = _framed(QPixmap(THUMB_WIDTH, int(THUMB_WIDTH * 1.4)), fill=True)
            for index in range(document.page_count):
                item = QListWidgetItem(QIcon(placeholder), str(index + 1))
                item.setTextAlignment(Qt.AlignHCenter)
                self.thumb_list.addItem(item)
                self._thumb_queue.append(index)
            self.thumb_list.setCurrentRow(min(self.view.current_page, document.page_count - 1))
        finally:
            self.thumb_list.blockSignals(bloqueado)
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
            # El documento se puede cerrar entre dos disparos del temporizador
            # (cerrar el archivo o la ventana), asi que aqui no se da por hecho
            # que la pagina siga existiendo.
            try:
                if index >= document.page_count:
                    continue
                width, _alto = document.page_size(index)
                if width <= 0:
                    continue
                page = document.render_page(index, THUMB_WIDTH / width)
            except Exception:  # pragma: no cover - PDF cerrado o danado
                self._thumb_timer.stop()
                self._thumb_queue.clear()
                return
            image = QImage(
                page.samples, page.width, page.height, page.stride, QImage.Format_RGB888
            )
            item = self.thumb_list.item(index)
            if item is not None:
                item.setIcon(QIcon(_framed(QPixmap.fromImage(image.copy()))))
        if not self._thumb_queue:
            self._thumb_timer.stop()

    def _on_thumbnail_selected(self, row: int) -> None:
        if row >= 0 and row != self.view.current_page:
            self.view.go_to_page(row)

    def _on_thumbnail_dropped(self, origen: int, destino: int) -> None:
        """Reordena el documento tras arrastrar una miniatura."""
        if not self.view.has_document():
            return
        if not (0 <= origen < self.view.page_count):
            return
        destino = max(0, min(destino, self.view.page_count - 1))
        if destino == origen:
            return
        self.view.move_page(origen, destino)
        self._after_page_change(destino)
        self.statusBar().showMessage(
            tr("page_move_undo", origin=origen + 1, target=destino + 1), 6000
        )

    def _thumbnail_menu(self, pos) -> None:
        """Menu contextual de una miniatura: duplicar, insertar y eliminar."""
        if not self.view.has_document():
            return
        item = self.thumb_list.itemAt(pos)
        if item is None:
            return
        pagina = self.thumb_list.row(item)
        self.thumb_list.setCurrentRow(pagina)
        menu, acciones = self.build_page_menu(pagina)
        elegido = menu.exec(self.thumb_list.viewport().mapToGlobal(pos))
        if elegido is not None:
            self.run_page_action(acciones.get(elegido), pagina)

    def build_page_menu(self, pagina: int):
        """Menu de una pagina. Separado del gesto para poder probarlo."""
        menu = QMenu(self)
        acciones = {}

        def submenu_insertar(clave: str, texto: str) -> None:
            """Insertar una pagina, eligiendo su tamano en el momento."""
            sub = menu.addMenu(texto)
            igual = sub.addAction(tr("size_same"))
            acciones[igual] = f"{clave}:"          # sin tamano = como la vecina
            sub.addSeparator()
            for nombre in PAGE_SIZES:
                acciones[sub.addAction(page_size_label(nombre))] = f"{clave}:{nombre}"

        submenu_insertar("insert_before", tr("page_insert_before"))
        submenu_insertar("insert_after", tr("page_insert_after"))
        menu.addSeparator()
        duplicar = menu.addAction(tr("page_duplicate"))
        menu.addSeparator()
        girar_izq = menu.addAction(tr("page_rotate_left"))
        girar_der = menu.addAction(tr("page_rotate_right"))
        girar_180 = menu.addAction(tr("page_rotate_180"))
        menu.addSeparator()
        arriba = menu.addAction(tr("page_up"))
        abajo = menu.addAction(tr("page_down"))
        arriba.setEnabled(pagina > 0)
        abajo.setEnabled(pagina < self.view.page_count - 1)
        menu.addSeparator()
        borrar = menu.addAction(tr("page_delete"))
        borrar.setEnabled(self.view.page_count > 1)
        acciones.update({
            duplicar: "duplicate",
            girar_izq: "rotate_left",
            girar_der: "rotate_right",
            girar_180: "rotate_180",
            arriba: "up",
            abajo: "down",
            borrar: "delete",
        })
        return menu, acciones

    def run_page_action(self, accion: str | None, pagina: int) -> None:
        """Ejecuta una de las opciones del menu de pagina."""
        if accion is None or not self.view.has_document():
            return
        # Las opciones de insertar llevan el tamano detras: "insert_after:A4".
        # Sin nada detras, la pagina nueva copia el tamano de la de al lado.
        tamano = None
        if ":" in accion:
            accion, _, nombre = accion.partition(":")
            tamano = nombre or None
        if accion == "insert_before":
            self.view.add_page(pagina, tamano)
            self._after_page_change(pagina)
        elif accion == "insert_after":
            self.view.add_page(pagina + 1, tamano)
            self._after_page_change(pagina + 1)
        elif accion == "duplicate":
            self.view.duplicate_page(pagina)
            self._after_page_change(pagina + 1)
        elif accion in ("rotate_left", "rotate_right", "rotate_180"):
            grados = {"rotate_left": -90, "rotate_right": 90, "rotate_180": 180}[accion]
            self.view.rotate_page(pagina, grados)
            self._after_page_change(pagina)
        elif accion == "up" and pagina > 0:
            self.view.move_page(pagina, pagina - 1)
            self._after_page_change(pagina - 1)
        elif accion == "down" and pagina < self.view.page_count - 1:
            self.view.move_page(pagina, pagina + 1)
            self._after_page_change(pagina + 1)
        elif accion == "delete":
            self.view.go_to_page(pagina)
            self.delete_current_page()

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
            self.search_label.setText(
                tr("search_of", current=self.view.hit_index + 1, total=len(hits))
            )
        else:
            self.search_label.setText(tr("search_none"))
            self.statusBar().showMessage(tr("search_not_found", text=needle), 4000)

    # ------------------------------------------------------------------ vista
    def goto_page_dialog(self) -> None:
        if not self.view.has_document():
            return
        page, ok = QInputDialog.getInt(
            self,
            tr("goto_title"),
            tr("goto_label", total=self.view.page_count),
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
            self.statusBar().showMessage(tr("status_no_selection"), 3000)

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
            self.act_page_down, self.act_rotate_left, self.act_rotate_right,
            self.act_rotate_180,
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
        self.page_label.setText(tr("status_of", total=self.view.page_count))
        if not has_doc:
            self.info_label.setText("")
        elif count == 1:
            self.info_label.setText(tr("status_annotation"))
        else:
            self.info_label.setText(tr("status_annotations", count=count))

    # ------------------------------------------------------------------ cierre
    def _confirm_discard(self) -> bool:
        if not self._is_dirty():
            return True
        answer = QMessageBox.question(
            self,
            __app_name__,
            tr("unsaved"),
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
        # Antes de cerrar el documento hay que parar el temporizador: si no,
        # sigue pidiendo miniaturas de un PDF que ya no esta abierto.
        self._thumb_timer.stop()
        self._thumb_queue.clear()
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
            QMessageBox.warning(self, __app_name__, tr("image_unreadable", error=exc))
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
        self.statusBar().showMessage(tr("status_image_placed", name=os.path.basename(path)), 4000)
        return True

    # ------------------------------------------------------------------ ayuda
    def show_about(self) -> None:
        AboutDialog(self).exec()

    def show_help(self) -> None:
        HelpDialog(self).exec()


__all__ = ["MainWindow", "AboutDialog", "HelpDialog"]
