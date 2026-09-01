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
    QApplication,
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
from ..document import (
    DEFAULT_PAGE_SIZE,
    PAGE_SIZES,
    PasswordRequired,
    PdfDocument,
    PdfError,
    page_size_key,
)
from ..i18n import LANGUAGES, language, page_size_label, set_language, tr
from ..model import Align, Font, Kind
from ..printing import print_document, print_preview
from ..templates import (
    CATEGORIES,
    TemplateError,
    builtin_infos,
    delete_template,
    list_templates,
    load_builtin,
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
        # PySide6 es LGPL y pide avisar de que se usa y bajo que licencia. Va
        # en su propia ventana para no llenar el "acerca de" de letra pequena,
        # pero sigue estando a un clic.
        licencias = buttons.addButton(
            tr("about_licences"), QDialogButtonBox.ButtonRole.ActionRole
        )
        licencias.clicked.connect(lambda: LicencesDialog(self).exec())
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class LicencesDialog(QDialog):
    """Licencia del programa y de las bibliotecas que usa."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("licences_title"))
        self.resize(520, 340)
        layout = QVBoxLayout(self)
        text = QTextBrowser()
        text.setOpenExternalLinks(True)
        text.setHtml(tr("licences_html"))
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
        self.setCentralWidget(self._build_view_with_rulers())

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
        self._create_bookmarks()
        self._create_status_bar()
        self._connect_view()
        self._restore_settings()
        self.refresh_elements()
        self.refresh_templates()
        self._setup_updates()
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

        self.act_copy = action("copy_sel", self.copy_selection,
                               shortcut=QKeySequence.Copy)
        self.act_cut = action("cut_sel", self.cut_selection, shortcut=QKeySequence.Cut)
        self.act_paste = action("paste_sel", self.paste_clipboard,
                                shortcut=QKeySequence.Paste)
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

        # Los botones y el menu siempre amplian o reducen, tambien con la goma
        # en la mano: si no, no habria forma de acercarse para borrar fino.
        self.act_zoom_in = action("zoom_in", self.view.zoom_in, "zoom_in")
        self.act_zoom_out = action("zoom_out", self.view.zoom_out, "zoom_out")

        # Los atajos si dependen de la herramienta: con la goma cambian su
        # tamano, que es lo que se quiere ajustar mientras se borra.
        # Sin repetir combinaciones: QKeySequence.ZoomIn ya es Ctrl++ en esta
        # plataforma, y dos atajos iguales en la misma accion hacen que Qt los
        # considere ambiguos y no dispare ninguno.
        def _atajos(*candidatos):
            seen, output = set(), []
            for sec in candidatos:
                text = QKeySequence(sec).toString()
                if text and text not in seen:
                    seen.add(text)
                    output.append(QKeySequence(sec))
            return output

        self._sc_zoom_in = QAction(self)
        self._sc_zoom_in.setShortcuts(_atajos(QKeySequence.ZoomIn, "Ctrl++", "Ctrl+="))
        self._sc_zoom_in.triggered.connect(lambda: self.zoom_or_eraser(1))
        self._sc_zoom_out = QAction(self)
        self._sc_zoom_out.setShortcuts(_atajos(QKeySequence.ZoomOut, "Ctrl+-"))
        self._sc_zoom_out.triggered.connect(lambda: self.zoom_or_eraser(-1))
        # y ademas los corchetes, como en cualquier programa de dibujo
        self._sc_brush_up = QAction(self)
        self._sc_brush_up.setShortcut(QKeySequence("]"))
        self._sc_brush_up.triggered.connect(lambda: self.view.step_eraser_size(1))
        self._sc_brush_down = QAction(self)
        self._sc_brush_down.setShortcut(QKeySequence("["))
        self._sc_brush_down.triggered.connect(lambda: self.view.step_eraser_size(-1))
        self.addActions([self._sc_zoom_in, self._sc_zoom_out,
                         self._sc_brush_up, self._sc_brush_down])
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
        self.act_side_panel = action("side_panel", self.toggle_side_panel,
                                     shortcut="F10", checkable=True)

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
        self.act_update = action("update_check", lambda: self.check_updates(manual=True))
        self.act_update_auto = QAction(tr("update_auto"), self)
        self.act_update_auto.setCheckable(True)
        self.act_update_auto.toggled.connect(self._set_update_auto)
        self._action_keys[self.act_update_auto] = ("update_auto", None)

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
            Tool.NOTE: ("tool_note", "note", "N"),
            Tool.ERASER: ("tool_eraser", "eraser", "E"),
        }
        for tool, (text_key, icon_name, shortcut) in self.tool_keys.items():
            act = QAction(icons.icon(icon_name), tr(text_key), self)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(shortcut))
            act.setStatusTip(
                tr("tool_status", name=tr(text_key).replace("&", ""), key=shortcut)
            )
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
        edit_menu.addAction(self.act_cut)
        edit_menu.addAction(self.act_copy)
        edit_menu.addAction(self.act_paste)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_delete)
        edit_menu.addAction(self.act_select_all)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_find)
        edit_menu.addAction(self.act_find_next)
        edit_menu.addAction(self.act_find_prev)

        view_menu = self.menuBar().addMenu(tr("menu_view"))
        self._menu_keys[view_menu] = "menu_view"
        self.act_rulers = QAction(tr("rulers"), self)
        self.act_rulers.setCheckable(True)
        self.act_rulers.setChecked(True)
        self.act_rulers.toggled.connect(self.toggle_rulers)
        self._action_keys[self.act_rulers] = ("rulers", None)
        view_menu.addAction(self.act_rulers)

        units = view_menu.addMenu(tr("ruler_unit_menu"))
        self._menu_keys[units] = "ruler_unit_menu"
        self.unit_group = QActionGroup(self)
        self.unit_group.setExclusive(True)
        self.unit_actions = {}
        for codigo, key in (("mm", "unit_mm"), ("cm", "unit_cm"),
                              ("in", "unit_in"), ("pt", "unit_pt")):
            act = QAction(tr(key), self)
            act.setCheckable(True)
            act.setChecked(codigo == "mm")
            act.triggered.connect(lambda checked=False, c=codigo: self.set_ruler_unit(c))
            self.unit_group.addAction(act)
            units.addAction(act)
            self.unit_actions[codigo] = act
            self._action_keys[act] = (key, None)

        self.act_snap = QAction(tr("snap"), self)
        self.act_snap.setCheckable(True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(self.view.set_snap)
        self._action_keys[self.act_snap] = ("snap", None)
        view_menu.addAction(self.act_snap)
        self.act_guides_clear = QAction(tr("guides_clear"), self)
        self.act_guides_clear.triggered.connect(self._clear_guides)
        self._action_keys[self.act_guides_clear] = ("guides_clear", None)
        view_menu.addAction(self.act_guides_clear)
        view_menu.addSeparator()

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
        view_menu.addAction(self.act_side_panel)
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
        chosen = page_size_key(
            self.settings.value("document/page_size", DEFAULT_PAGE_SIZE)
        )
        self.page_size_actions = {}
        for name in PAGE_SIZES:
            act = QAction(page_size_label(name), self)
            act.setCheckable(True)
            act.setChecked(name == chosen)
            act.triggered.connect(lambda checked=False, n=name: self._set_page_size(n))
            self.page_size_group.addAction(act)
            tamano_menu.addAction(act)
            self.page_size_actions[name] = act
        self.new_page_size = str(chosen)

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
        for codigo, name in LANGUAGES.items():
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(codigo == language())
            act.triggered.connect(lambda checked=False, c=codigo: self.set_language(c))
            self.language_group.addAction(act)
            idioma_menu.addAction(act)
            self.language_actions[codigo] = act
        help_menu.addSeparator()
        help_menu.addAction(self.act_help)
        help_menu.addAction(self.act_website)
        help_menu.addAction(self.act_update)
        help_menu.addAction(self.act_update_auto)
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

        # Color con el que tapa la goma: blanco por defecto, que es el color
        # del papel, pero se puede elegir otro para tapar sobre fondos de color.
        self.eraser_color_button = QToolButton(self)
        self.eraser_color_button.setPopupMode(QToolButton.InstantPopup)
        self.eraser_color_button.setToolTip(tr("eraser_color_tip"))
        self.eraser_color_button.setIcon(_swatch(QColor("#ffffff")))
        self.eraser_color_button.setMenu(
            self._color_menu(self._set_eraser_color, allow_none=False)
        )
        tools.addWidget(self.eraser_color_button)

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
        for alignment, name in (
            (Align.LEFT, "align_left"),
            (Align.CENTER, "align_center"),
            (Align.RIGHT, "align_right"),
        ):
            act = QAction(icons.icon(name), tr(f"act_align_{alignment.name.lower()}"), self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked=False, a=alignment: self._set_align(a))
            self.align_group.addAction(act)
            self.align_actions[alignment] = act
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
        for key, hexvalue in PALETTE:
            act = QAction(_swatch(QColor(hexvalue)), tr(f"color_{key}"), self)
            act.triggered.connect(lambda checked=False, h=hexvalue: slot(QColor(h)))
            menu.addAction(act)
        menu.addSeparator()
        more = QAction(tr("more_colours"), self)
        more.triggered.connect(lambda: self._pick_custom_color(slot))
        menu.addAction(more)
        return menu

    def _set_eraser_color(self, color: QColor) -> None:
        """Cambia el color con el que la goma tapa el documento."""
        if color is None:
            return
        self.view.set_eraser_color(to_rgb(color))
        self.eraser_color_button.setIcon(_swatch(color))
        self.settings.set_value("tools/eraser_color", color.name())

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

    def _build_view_with_rulers(self):
        """Coloca la vista con una regla arriba y otra a la izquierda."""
        from PySide6.QtWidgets import QGridLayout, QWidget

        from .rulers import RULER_SIZE, Ruler

        self.ruler_h = Ruler(self.view, horizontal=True)
        self.ruler_v = Ruler(self.view, horizontal=False)

        esquina = QWidget()
        esquina.setFixedSize(RULER_SIZE, RULER_SIZE)

        box = QWidget(self)
        rejilla = QGridLayout(box)
        rejilla.setContentsMargins(0, 0, 0, 0)
        rejilla.setSpacing(0)
        rejilla.addWidget(esquina, 0, 0)
        rejilla.addWidget(self.ruler_h, 0, 1)
        rejilla.addWidget(self.ruler_v, 1, 0)
        rejilla.addWidget(self.view, 1, 1)

        # las reglas se redibujan cuando cambia lo que se ve
        self.view.horizontalScrollBar().valueChanged.connect(self.ruler_h.update)
        self.view.verticalScrollBar().valueChanged.connect(self.ruler_v.update)
        self.view.zoomChanged.connect(lambda *_: self._update_rulers())
        self.view.pageChanged.connect(lambda *_: self._update_rulers())
        self.view.mouseMovedOnPage.connect(self._on_mouse_on_page)
        self.view.guidesChanged.connect(self._on_guides_changed)
        return box

    def _clear_guides(self) -> None:
        self.view.clear_all_guides()
        self.statusBar().showMessage(tr("guides_hint"), 6000)

    def _on_guides_changed(self) -> None:
        """Repinta las reglas y ensena la medida de la guia que se mueve."""
        self._update_rulers()
        drag = self.view._guide_drag
        if drag is None:
            return
        orientation, _pagina, value, _indice = drag
        # la guia horizontal se mide en la regla vertical
        ruler = self.ruler_v if orientation == "h" else self.ruler_h
        _menor, _mayor, por_unidad = ruler._step_pt()
        self.statusBar().showMessage(
            tr("guide_at", value=f"{value / por_unidad:.1f}", unit=ruler.unit), 3000
        )

    def _update_rulers(self) -> None:
        if hasattr(self, "ruler_h"):
            self.ruler_h.update()
            self.ruler_v.update()

    def _on_mouse_on_page(self, viewport_pos) -> None:
        """Mueve la marca de las reglas y ensena la medida en la barra."""
        if not hasattr(self, "ruler_h"):
            return
        self.ruler_h.set_mouse(viewport_pos.x())
        self.ruler_v.set_mouse(viewport_pos.y())
        x = self.ruler_h.value_at(viewport_pos.x())
        y = self.ruler_v.value_at(viewport_pos.y())
        if x is not None and y is not None:
            self.cursor_label.setText(
                tr("cursor_pos", x=f"{x:.1f}", y=f"{y:.1f}", unit=self.ruler_h.unit)
            )

    def set_ruler_unit(self, unit: str) -> None:
        self.ruler_h.set_unit(unit)
        self.ruler_v.set_unit(unit)
        self.settings.set_value("view/ruler_unit", unit)

    def toggle_rulers(self, visible: bool) -> None:
        self.ruler_h.setVisible(visible)
        self.ruler_v.setVisible(visible)
        self.settings.set_value("view/rulers", visible)

    def _create_bookmarks(self) -> None:
        from PySide6.QtWidgets import (
            QDockWidget,
            QHBoxLayout,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )

        box = QWidget(self)
        column = QVBoxLayout(box)
        column.setContentsMargins(4, 4, 4, 4)
        self.bookmark_list = QListWidget(box)
        self.bookmark_list.itemActivated.connect(self._go_to_bookmark)
        self.bookmark_list.itemClicked.connect(self._go_to_bookmark)
        column.addWidget(self.bookmark_list)

        buttons = QHBoxLayout()
        self.btn_bookmark_add = QPushButton(tr("bookmark_add"), box)
        self.btn_bookmark_add.clicked.connect(self.add_bookmark)
        self.btn_bookmark_del = QPushButton(tr("bookmark_remove"), box)
        self.btn_bookmark_del.clicked.connect(self.remove_bookmark)
        buttons.addWidget(self.btn_bookmark_add)
        buttons.addWidget(self.btn_bookmark_del)
        column.addLayout(buttons)

        # --- pestana de notas ---
        caja_notas = QWidget(self)
        col_notas = QVBoxLayout(caja_notas)
        col_notas.setContentsMargins(4, 4, 4, 4)
        self.notes_list = QListWidget(caja_notas)
        self.notes_list.itemClicked.connect(self._go_to_note)
        self.notes_list.itemChanged.connect(self._on_note_checked)
        col_notas.addWidget(self.notes_list)
        fila_notas = QHBoxLayout()
        self.btn_notes_show = QPushButton(tr("notes_show_done"), caja_notas)
        self.btn_notes_show.setCheckable(True)
        self.btn_notes_show.toggled.connect(lambda *_: self.refresh_notes())
        fila_notas.addWidget(self.btn_notes_show)
        col_notas.addLayout(fila_notas)

        # --- pestana de plantillas ---
        from PySide6.QtWidgets import QTabWidget, QTreeWidget

        caja_tpl = QWidget(self)
        col_tpl = QVBoxLayout(caja_tpl)
        col_tpl.setContentsMargins(4, 4, 4, 4)
        self.tpl_tree = QTreeWidget(caja_tpl)
        self.tpl_tree.setHeaderHidden(True)
        self.tpl_tree.setRootIsDecorated(True)
        self.tpl_tree.itemDoubleClicked.connect(lambda *_: self.use_selected_template())
        self.tpl_tree.currentItemChanged.connect(lambda *_: self._update_template_buttons())
        col_tpl.addWidget(self.tpl_tree)

        fila1 = QHBoxLayout()
        self.btn_tpl_use = QPushButton(tr("tpl_use"), caja_tpl)
        self.btn_tpl_use.clicked.connect(self.use_selected_template)
        self.btn_tpl_new = QPushButton(tr("tpl_new"), caja_tpl)
        self.btn_tpl_new.clicked.connect(self.new_from_selected_template)
        fila1.addWidget(self.btn_tpl_use)
        fila1.addWidget(self.btn_tpl_new)
        col_tpl.addLayout(fila1)

        fila2 = QHBoxLayout()
        self.btn_tpl_save = QPushButton(tr("tpl_save"), caja_tpl)
        self.btn_tpl_save.clicked.connect(self.save_as_template)
        self.btn_tpl_del = QPushButton(tr("tpl_delete"), caja_tpl)
        self.btn_tpl_del.clicked.connect(self.delete_selected_template)
        fila2.addWidget(self.btn_tpl_save)
        fila2.addWidget(self.btn_tpl_del)
        col_tpl.addLayout(fila2)

        # --- pestana de elementos de formulario ---
        caja_el = QWidget(self)
        col_el = QVBoxLayout(caja_el)
        col_el.setContentsMargins(4, 4, 4, 4)
        self.el_tree = QTreeWidget(caja_el)
        self.el_tree.setHeaderHidden(True)
        self.el_tree.itemDoubleClicked.connect(lambda *_: self.insert_selected_element())
        self.el_tree.currentItemChanged.connect(lambda *_: self._update_element_buttons())
        col_el.addWidget(self.el_tree)
        self.el_hint = QLabel(tr("el_hint"), caja_el)
        self.el_hint.setWordWrap(True)
        self.el_hint.setStyleSheet("color:#666")
        col_el.addWidget(self.el_hint)
        self.btn_el_insert = QPushButton(tr("el_insert"), caja_el)
        self.btn_el_insert.clicked.connect(self.insert_selected_element)
        col_el.addWidget(self.btn_el_insert)

        self.side_tabs = QTabWidget(self)
        self.side_tabs.addTab(box, tr("bookmarks_dock"))
        self.side_tabs.addTab(caja_notas, tr("notes_tab"))
        self.side_tabs.addTab(caja_el, tr("elements_tab"))
        self.side_tabs.addTab(caja_tpl, tr("templates_tab"))

        # Sin un minimo, Qt le daba al panel lo que sobraba de las miniaturas
        # (unos 190 px): el arbol de plantillas ensenaba tres filas y el boton
        # de guardar quedaba pegado al borde.
        self.side_tabs.setMinimumHeight(300)

        dock = QDockWidget(tr("side_dock"), self)
        dock.setObjectName("dock_bookmarks")
        dock.setWidget(self.side_tabs)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.bookmark_dock = dock
        dock.visibilityChanged.connect(self.act_side_panel.setChecked)

    def refresh_bookmarks(self) -> None:
        """Rehace la lista con los marcadores del documento abierto."""
        if not hasattr(self, "bookmark_list"):
            return
        self.bookmark_list.clear()
        document = self.view.document
        if document is None:
            return
        for title, page_item in document.bookmarks():
            from PySide6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(tr("bookmark_entry", title=title, page=page_item + 1))
            item.setData(Qt.UserRole, page_item)
            item.setToolTip(title)
            self.bookmark_list.addItem(item)

    def _go_to_bookmark(self, item) -> None:
        page_item = item.data(Qt.UserRole)
        if page_item is not None:
            self.view.go_to_page(int(page_item))

    def add_bookmark(self) -> None:
        """Marca la pagina actual con el nombre que elija el usuario."""
        if not self.view.has_document():
            return
        page_item = self.view.current_page
        propuesto = tr("bookmark_default", page=page_item + 1)
        title, accepted = QInputDialog.getText(
            self, tr("bookmarks_dock"), tr("bookmark_prompt"), text=propuesto
        )
        if not accepted or not title.strip():
            return
        bookmarks = self.view.document.bookmarks()
        bookmarks.append((title.strip(), page_item))
        bookmarks.sort(key=lambda m: m[1])          # en orden de pagina
        self.view.document.set_bookmarks(bookmarks)
        self.refresh_bookmarks()
        self.refresh_notes()
        self.refresh_templates()
        self.view.notify_modified()

    def remove_bookmark(self) -> None:
        row = self.bookmark_list.currentRow() if hasattr(self, "bookmark_list") else -1
        if not self.view.has_document() or row < 0:
            return
        bookmarks = self.view.document.bookmarks()
        if row >= len(bookmarks):
            return
        del bookmarks[row]
        self.view.document.set_bookmarks(bookmarks)
        self.refresh_bookmarks()
        self.refresh_notes()
        self.refresh_templates()
        self.view.notify_modified()

    def refresh_elements(self) -> None:
        """Rellena el catalogo de piezas, agrupado por tipo."""
        from PySide6.QtWidgets import QTreeWidgetItem

        from ..elements import CATEGORIES as EL_CATEGORIES
        from ..elements import element_infos

        if not hasattr(self, "el_tree"):
            return
        remembered = self._chosen_element()
        self.el_tree.clear()
        por_grupo: dict[str, list] = {c: [] for c in EL_CATEGORIES}
        for info in element_infos():
            por_grupo.setdefault(info.category, []).append(info)
        for group in EL_CATEGORIES:
            pieces = por_grupo.get(group) or []
            if not pieces:
                continue
            root = QTreeWidgetItem([tr(f"elcat_{group}")])
            root.setFlags(Qt.ItemIsEnabled)
            self.el_tree.addTopLevelItem(root)
            for info in pieces:
                child = QTreeWidgetItem([info.name])
                child.setData(0, Qt.UserRole, info.key)
                root.addChild(child)
            root.setExpanded(True)
            if remembered is not None:
                for i in range(root.childCount()):
                    if root.child(i).data(0, Qt.UserRole) == remembered:
                        self.el_tree.setCurrentItem(root.child(i))
        self._update_element_buttons()

    def _chosen_element(self) -> str | None:
        item = self.el_tree.currentItem() if hasattr(self, "el_tree") else None
        return item.data(0, Qt.UserRole) if item is not None else None

    def _update_element_buttons(self) -> None:
        if not hasattr(self, "btn_el_insert"):
            return
        self.btn_el_insert.setEnabled(
            self._chosen_element() is not None and self.view.has_document()
        )

    def insert_selected_element(self) -> bool:
        """Suelta la pieza elegida en la pagina que se esta viendo."""
        from ..elements import build

        key = self._chosen_element()
        if key is None or not self.view.has_document():
            return False
        pieces = build(key, 0.0, 0.0)
        name = tr(f"el_{key}")
        if not self.view.insert_annotations(pieces, tr("cmd_element", name=name)):
            return False
        self.statusBar().showMessage(tr("status_element_added", name=name), 4000)
        return True

    def refresh_templates(self) -> None:
        """Rehace el arbol del panel: primero las de serie, luego las tuyas."""
        if not hasattr(self, "tpl_tree"):
            return
        from PySide6.QtWidgets import QTreeWidgetItem

        self.tpl_tree.clear()
        groups = [(tr("tpl_included"), builtin_infos()),
                  (tr("tpl_mine"), list_templates(self.templates_dir()))]
        for title, templates in groups:
            if not templates:
                continue
            root = QTreeWidgetItem([title])
            root.setFlags(Qt.ItemIsEnabled)          # el grupo no se elige
            self.tpl_tree.addTopLevelItem(root)
            por_tipo: dict[str, list] = {}
            for info in templates:
                por_tipo.setdefault(info.category, []).append(info)
            for categoria in CATEGORIES:
                lote = por_tipo.get(categoria)
                if not lote:
                    continue
                rama = QTreeWidgetItem([tr(f"cat_{categoria}")])
                rama.setFlags(Qt.ItemIsEnabled)
                root.addChild(rama)
                for info in lote:
                    sheet = QTreeWidgetItem([
                        tr("tpl_entry", name=info.name, pages=info.pages,
                           count=info.annotations)
                    ])
                    sheet.setData(0, Qt.UserRole, info.path)
                    sheet.setData(0, Qt.UserRole + 1, info.builtin)
                    sheet.setToolTip(0, info.saved_at or info.name)
                    rama.addChild(sheet)
            root.setExpanded(True)
            for i in range(root.childCount()):
                root.child(i).setExpanded(True)
        self._update_template_buttons()

    def _selected_template(self):
        """(ruta, es_de_serie) de la plantilla elegida, o None."""
        item = self.tpl_tree.currentItem() if hasattr(self, "tpl_tree") else None
        if item is None:
            return None
        path = item.data(0, Qt.UserRole)
        if not path:
            return None
        return (str(path), bool(item.data(0, Qt.UserRole + 1)))

    def _update_template_buttons(self) -> None:
        chosen = self._selected_template()
        hay_doc = self.view.has_document()
        self.btn_tpl_use.setEnabled(chosen is not None and hay_doc)
        self.btn_tpl_new.setEnabled(chosen is not None)
        self.btn_tpl_save.setEnabled(hay_doc)
        # las de serie no se borran: vienen con el programa
        self.btn_tpl_del.setEnabled(chosen is not None and not chosen[1])

    def _load_selected(self):
        """Carga la plantilla elegida venga de donde venga."""
        chosen = self._selected_template()
        if chosen is None:
            return None
        path, de_serie = chosen
        try:
            if de_serie:
                return load_builtin(path.split(":", 1)[1])
            return load_template(path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return None

    def use_selected_template(self) -> bool:
        """Pone la plantilla encima del documento abierto."""
        if not self.view.has_document():
            QMessageBox.information(self, __app_name__, tr("tpl_none"))
            return False
        data = self._load_selected()
        if data is None:
            return False
        name, _paginas, annotations = data
        placed = self.view.apply_template(annotations)
        self.statusBar().showMessage(
            tr("template_applied", name=name, count=placed,
               page=self.view.current_page + 1),
            6000,
        )
        return True

    def new_from_selected_template(self) -> bool:
        """Crea un documento nuevo a partir de la plantilla."""
        data = self._load_selected()
        if data is None:
            return False
        return self._document_from_template(*data)

    def delete_selected_template(self) -> bool:
        chosen = self._selected_template()
        if chosen is None or chosen[1]:
            return False
        path = chosen[0]
        if QMessageBox.question(
            self, __app_name__, tr("template_delete_ask", name=os.path.basename(path))
        ) != QMessageBox.Yes:
            return False
        try:
            delete_template(path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        self.refresh_templates()
        return True

    def refresh_notes(self) -> None:
        """Rehace la lista de notas del documento.

        Las leidas desaparecen, salvo que se pida verlas. Asi la lista es lo
        que queda por mirar, no un inventario.
        """
        if not hasattr(self, "notes_list"):
            return
        from PySide6.QtWidgets import QListWidgetItem

        ver_leidas = self.btn_notes_show.isChecked()
        self.notes_list.blockSignals(True)
        self.notes_list.clear()
        pending = 0
        for ann in sorted(
            (a for a in self.view.store if a.kind is Kind.NOTE),
            key=lambda a: (a.page, a.rect[1], a.rect[0]),
        ):
            if ann.done and not ver_leidas:
                continue
            if not ann.done:
                pending += 1
            text = (ann.text or "").strip().splitlines()
            resumen = text[0] if text else tr("note_empty")
            item = QListWidgetItem(tr("note_entry", page=ann.page + 1, text=resumen[:60]))
            item.setData(Qt.UserRole, ann.id)
            item.setToolTip(ann.text or "")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if ann.done else Qt.Unchecked)
            if ann.done:
                fuente = item.font()
                fuente.setStrikeOut(True)
                item.setFont(fuente)
            self.notes_list.addItem(item)
        self.notes_list.blockSignals(False)
        index = self.side_tabs.indexOf(self.notes_list.parentWidget())
        if index >= 0:
            label = tr("notes_tab")
            self.side_tabs.setTabText(
                index, f"{label} ({pending})" if pending else label
            )

    def _note_by_id(self, ann_id):
        for ann in self.view.store:
            if ann.id == ann_id:
                return ann
        return None

    def _go_to_note(self, item) -> None:
        """Lleva a la nota y ensena su texto."""
        ann = self._note_by_id(item.data(Qt.UserRole))
        if ann is None:
            return
        self.view.go_to_page(ann.page)
        grafico = self.view._items.get(ann.id)
        if grafico is not None:
            self.view.centerOn(grafico)
            self.view._scene.clearSelection()
            grafico.setSelected(True)
        self.statusBar().showMessage(ann.text or tr("note_empty"), 8000)

    def _on_note_checked(self, item) -> None:
        """Marca o desmarca una nota como leida."""
        ann = self._note_by_id(item.data(Qt.UserRole))
        if ann is None:
            return
        leida = item.checkState() == Qt.Checked
        if leida == ann.done:
            return
        ann.done = leida
        self.view.notify_modified()
        self.refresh_notes()

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
        self.cursor_label = QLabel("")
        self.info_label = QLabel("")
        self.lbl_page = QLabel(tr("status_page"))
        status.addPermanentWidget(self.lbl_page)
        status.addPermanentWidget(self.page_spin)
        status.addPermanentWidget(self.page_label)
        status.addPermanentWidget(self.cursor_label)
        status.addPermanentWidget(QLabel("   "))
        status.addPermanentWidget(self.zoom_label)
        status.addWidget(self.info_label)
        status.showMessage(tr("status_start"), 6000)

    def _connect_view(self) -> None:
        self.view.pageChanged.connect(self._on_page_changed)
        self.view.zoomChanged.connect(self._on_zoom_changed)
        self.view.eraserSizeChanged.connect(self._on_eraser_size)
        self.view.modified.connect(self.refresh_notes)
        self.view.noteCreated.connect(self.edit_note)
        self.view.modified.connect(self._on_modified)
        self.view.toolFinished.connect(
            lambda: self.tool_actions[Tool.SELECT].setChecked(True)
        )
        self.view.selectionChanged.connect(self._update_actions)
        self.view.erased.connect(
            lambda: self.statusBar().showMessage(tr("status_erased"), 5000)
        )
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
        else:
            # Primer arranque: la columna izquierda se reparte a medias entre
            # las miniaturas y el panel. Si el usuario la ha movido alguna vez,
            # manda lo que dejo guardado.
            self.resizeDocks(
                [self.thumb_dock, self.bookmark_dock], [55, 45], Qt.Vertical
            )
        visible = self.settings.show_thumbnails()
        self.thumb_dock.setVisible(visible)
        self.act_thumbnails.setChecked(visible)
        lateral = self.settings.value("view/side_panel", True, type_=bool)
        self.bookmark_dock.setVisible(bool(lateral))
        self.act_side_panel.setChecked(bool(lateral))

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

    def _set_align(self, alignment: Align) -> None:
        self.view.style_defaults["align"] = alignment
        self.settings.set_tool_align(int(alignment))
        self.view.apply_style_to_selection(align=alignment)

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
                data = fh.read()
        except OSError as exc:
            QMessageBox.warning(self, __app_name__, tr("image_unreadable", error=exc))
            return False
        if QPixmap.fromImage(QImage.fromData(data)).isNull():
            QMessageBox.warning(self, __app_name__, tr("image_invalid"))
            return False
        self.view.style_defaults["image"] = (os.path.basename(path), data)
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
            name = (self.view.style_defaults.get("image") or ("", b""))[0]
            self.statusBar().showMessage(tr("hint_image", name=name), 6000)
        elif tool is Tool.TABLE:
            self.statusBar().showMessage(
                tr("hint_table", rows=self.rows_spin.value(), cols=self.cols_spin.value()),
                6000,
            )

    # ------------------------------------------------------------------ archivos
    def _set_page_size(self, name: str) -> None:
        self.new_page_size = name
        self.settings.set_value("document/page_size", name)

    def new_document(self) -> None:
        """Crea un PDF vacio y lo abre."""
        if not self._confirm_discard():
            return
        previous = self.view.document
        self.view.set_document(PdfDocument.blank(1, self.new_page_size))
        if previous is not None:
            previous.close()
        self._modified = False
        self.view.undo_stack.setClean()
        self._build_thumbnails()
        self.refresh_bookmarks()
        self.refresh_notes()
        self.refresh_templates()
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
            target = self.view.current_page + 1
            self.view.add_page(target, self.new_page_size)
            self._after_page_change(target)

    def duplicate_current_page(self) -> None:
        if self.view.has_document():
            current = self.view.current_page
            self.view.duplicate_page(current)
            self._after_page_change(current + 1)

    def delete_current_page(self) -> None:
        if not self.view.has_document():
            return
        if self.view.page_count <= 1:
            QMessageBox.information(self, __app_name__, tr("last_page"))
            return
        current = self.view.current_page
        annotations = len(self.view.items_on_page(current))
        notice = tr("delete_page_ask", page=current + 1, total=self.view.page_count)
        if annotations:
            notice += tr("delete_page_annots", count=annotations)
        notice += tr("delete_page_undo")
        if QMessageBox.question(self, __app_name__, notice) != QMessageBox.Yes:
            return
        self.view.delete_page(current)
        self._after_page_change(min(current, self.view.page_count - 1))

    def edit_note(self, item) -> None:
        """Pide (o cambia) el texto de una nota adhesiva."""
        text, accepted = QInputDialog.getMultiLineText(
            self, tr("note_title"), tr("note_prompt"), item.ann.text or ""
        )
        if not accepted:
            return
        item.ann.text = text.strip()
        item.setToolTip(item.ann.text)
        item.update()
        self.view.notify_modified()
        self.refresh_notes()

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
            current = self.view.current_page
            self.view.rotate_page(current, delta)
            self._after_page_change(current)

    def move_current_page(self, delta: int) -> None:
        if not self.view.has_document():
            return
        current = self.view.current_page
        target = current + delta
        if 0 <= target < self.view.page_count:
            self.view.move_page(current, target)
            self._after_page_change(target)

    def _after_page_change(self, page_item: int) -> None:
        """Rehace las miniaturas y coloca la vista en la pagina indicada."""
        self._build_thumbnails()
        self.view.go_to_page(max(0, min(page_item, self.view.page_count - 1)))
        self._update_actions()
        self._update_title()

    # ------------------------------------------------------------------ plantillas
    def templates_dir(self) -> str:
        """Carpeta donde se guardan las plantillas del usuario."""
        from PySide6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not base:  # pragma: no cover - sistemas raros
            base = os.path.join(os.path.expanduser("~"), ".easypdf")
        folder = os.path.join(base, "Templates")
        # La carpeta se llamaba "plantillas". Si existe y todavia no hay una
        # con el nombre nuevo, se renombra: asi no se pierde nada de lo que
        # el usuario tuviera guardado.
        antigua = os.path.join(base, "plantillas")
        if os.path.isdir(antigua) and not os.path.exists(folder):
            try:
                os.rename(antigua, folder)
            except OSError:  # pragma: no cover - permisos raros
                return antigua
        return folder

    def _refresh_templates_menu(self) -> None:
        menu = self.templates_menu
        menu.clear()
        save_it = QAction(tr("template_save"), self)
        save_it.setStatusTip(tr("template_save_tip"))
        save_it.triggered.connect(self.save_as_template)
        save_it.setEnabled(self.view.has_document())
        menu.addAction(save_it)
        menu.addSeparator()

        templates = list_templates(self.templates_dir())
        if not templates:
            empty = QAction(tr("template_none"), self)
            empty.setEnabled(False)
            menu.addAction(empty)
        else:
            new_one = menu.addMenu(tr("template_new"))
            apply_it = menu.addMenu(tr("template_apply"))
            apply_it.setEnabled(self.view.has_document())
            for template in templates:
                detalle = tr("template_detail", count=template.annotations)
                if template.pages:
                    detalle = tr(
                        "template_detail_pages",
                        pages=template.pages,
                        count=template.annotations,
                    )
                act = QAction(f"{template.name}  ({detalle})", self)
                act.triggered.connect(
                    lambda checked=False, p=template.path: self.new_from_template(p)
                )
                new_one.addAction(act)

                act2 = QAction(f"{template.name}  ({detalle})", self)
                act2.triggered.connect(
                    lambda checked=False, p=template.path: self.apply_template(p)
                )
                apply_it.addAction(act2)

            erase_it = menu.addMenu(tr("template_delete"))
            for template in templates:
                act = QAction(template.name, self)
                act.triggered.connect(
                    lambda checked=False, p=template: self.delete_template(p)
                )
                erase_it.addAction(act)

        menu.addSeparator()
        folder = QAction(tr("template_folder"), self)
        folder.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._ensure_templates_dir()))
        )
        menu.addAction(folder)

    def _ensure_templates_dir(self) -> str:
        path = self.templates_dir()
        os.makedirs(path, exist_ok=True)
        return path

    def save_as_template(self) -> bool:
        """Guarda las anotaciones actuales como plantilla reutilizable."""
        if not self.view.has_document():
            return False
        annotations = list(self.view.annotations())
        if not annotations:
            QMessageBox.information(
                self,
                __app_name__,
                tr("template_empty"),
            )
            return False
        propuesto = os.path.splitext(self.view.document.name)[0]
        name, ok = QInputDialog.getText(
            self, tr("template_name_title"), tr("template_name_label"), text=propuesto
        )
        if not ok or not name.strip():
            return False
        labels = [tr(f"cat_{c}") for c in CATEGORIES]
        chosen, ok = QInputDialog.getItem(
            self, tr("template_name_title"), tr("tpl_kind"), labels, 0, False
        )
        if not ok:
            return False
        categoria = CATEGORIES[labels.index(chosen)]
        try:
            path = save_template(
                self._ensure_templates_dir(),
                name,
                annotations,
                self.view.document.page_sizes(),
                category=categoria,
            )
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        self.statusBar().showMessage(
            tr("template_saved", name=os.path.basename(path)), 5000
        )
        self.refresh_templates()
        return True

    def apply_template(self, path: str) -> bool:
        """Coloca las anotaciones de una plantilla sobre el documento abierto."""
        if not self.view.has_document():
            return False
        try:
            name, _paginas, annotations = load_template(path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        placed = self.view.apply_template(annotations)
        self.statusBar().showMessage(
            tr("template_applied", name=name, count=placed,
               page=self.view.current_page + 1),
            6000,
        )
        return placed > 0

    def new_from_template(self, path: str) -> bool:
        """Crea un documento nuevo con las paginas y anotaciones de la plantilla."""
        try:
            name, page_items, annotations = load_template(path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        return self._document_from_template(name, page_items, annotations)

    def _document_from_template(self, name, page_items, annotations) -> bool:
        """Crea el documento. Lo comparten el menu y el panel de plantillas."""
        if not self._confirm_discard():
            return False
        previous = self.view.document
        size = page_items[0] if page_items else self.new_page_size
        document = PdfDocument.blank(1, size, title=f"{name}.pdf")
        for width, height in page_items[1:]:
            document.add_blank_page(size=(width, height))
        self.view.set_document(document)
        if previous is not None:
            previous.close()
        self.view.apply_template(annotations, first_page=0)
        self._modified = False
        self.view.undo_stack.setClean()
        self._build_thumbnails()
        self.refresh_bookmarks()
        self.refresh_notes()
        self.refresh_templates()
        self._update_title()
        self._update_actions()
        self.statusBar().showMessage(tr("template_new_done", name=name), 6000)
        self.documentChanged.emit()
        return True

    def delete_template(self, template) -> bool:
        from ..templates import delete_template as erase_it

        response = QMessageBox.question(
            self, __app_name__, tr("template_delete_ask", name=template.name)
        )
        if response != QMessageBox.Yes:
            return False
        try:
            erase_it(template.path)
        except TemplateError as exc:
            QMessageBox.critical(self, __app_name__, str(exc))
            return False
        self.statusBar().showMessage(tr("template_deleted", name=template.name), 4000)
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
        for act, (key, tip) in self._action_keys.items():
            act.setText(tr(key, app=__app_name__))
            act.setStatusTip(tr(tip) if tip else tr(key, app=__app_name__))
        for menu, key in self._menu_keys.items():
            menu.setTitle(tr(key))
        if hasattr(self, "side_tabs"):
            # Por indice de la pestana no: al anadir "Elementos" en medio,
            # el numero fijo acababa poniendole el nombre de otra.
            for widget, key in ((self.bookmark_list, "bookmarks_dock"),
                                  (self.notes_list, "notes_tab"),
                                  (self.el_tree, "elements_tab"),
                                  (self.tpl_tree, "templates_tab")):
                index = self.side_tabs.indexOf(widget.parentWidget())
                if index >= 0:
                    self.side_tabs.setTabText(index, tr(key))
            for button, key in ((self.btn_tpl_use, "tpl_use"),
                                 (self.btn_tpl_new, "tpl_new"),
                                 (self.btn_tpl_save, "tpl_save"),
                                 (self.btn_tpl_del, "tpl_delete")):
                button.setText(tr(key))
            self.refresh_templates()
            self.btn_el_insert.setText(tr("el_insert"))
            self.el_hint.setText(tr("el_hint"))
            self.refresh_elements()
            self.btn_notes_show.setText(tr("notes_show_done"))
            self.refresh_notes()
        if hasattr(self, "bookmark_dock"):
            self.bookmark_dock.setWindowTitle(tr("side_dock"))
            self.btn_bookmark_add.setText(tr("bookmark_add"))
            self.btn_bookmark_del.setText(tr("bookmark_remove"))
            self.refresh_bookmarks()
        self.refresh_notes()
        self.refresh_templates()
        if hasattr(self, "thumb_dock"):
            self.thumb_dock.setWindowTitle(tr("pages_dock"))
        for name, act in getattr(self, "page_size_actions", {}).items():
            act.setText(page_size_label(name))
        for tool, (text_key, _icon, shortcut) in self.tool_keys.items():
            action = self.tool_actions[tool]
            action.setText(tr(text_key))
            action.setStatusTip(
                tr("tool_status", name=tr(text_key).replace("&", ""), key=shortcut)
            )
        self.act_undo.setText(tr("undo"))
        self.act_redo.setText(tr("redo"))
        self.act_bold.setText(tr("bold"))
        self.act_bold.setToolTip(tr("bold_tip"))
        self.act_italic.setText(tr("italic"))
        self.act_italic.setToolTip(tr("italic_tip"))
        for alignment, action in self.align_actions.items():
            action.setText(tr(f"act_align_{alignment.name.lower()}"))
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
        index = self.font_combo.currentIndex()
        self.font_combo.blockSignals(True)
        for position, familia in enumerate((Font.SANS, Font.SERIF, Font.MONO)):
            self.font_combo.setItemText(position, tr(f"font_{familia.name.lower()}"))
        self.font_combo.setCurrentIndex(index)
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
        self.refresh_bookmarks()
        self.refresh_notes()
        self.refresh_templates()
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
        blocked = self.thumb_list.blockSignals(True)
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
            self.thumb_list.blockSignals(blocked)
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

    def _on_thumbnail_dropped(self, source: int, target: int) -> None:
        """Reordena el documento tras arrastrar una miniatura."""
        if not self.view.has_document():
            return
        if not (0 <= source < self.view.page_count):
            return
        target = max(0, min(target, self.view.page_count - 1))
        if target == source:
            return
        self.view.move_page(source, target)
        self._after_page_change(target)
        self.statusBar().showMessage(
            tr("page_move_undo", origin=source + 1, target=target + 1), 6000
        )

    def _thumbnail_menu(self, pos) -> None:
        """Menu contextual de una miniatura: duplicar, insertar y eliminar."""
        if not self.view.has_document():
            return
        item = self.thumb_list.itemAt(pos)
        if item is None:
            return
        page_item = self.thumb_list.row(item)
        self.thumb_list.setCurrentRow(page_item)
        menu, actions = self.build_page_menu(page_item)
        chosen = menu.exec(self.thumb_list.viewport().mapToGlobal(pos))
        if chosen is not None:
            self.run_page_action(actions.get(chosen), page_item)

    def build_page_menu(self, page_item: int):
        """Menu de una pagina. Separado del gesto para poder probarlo."""
        menu = QMenu(self)
        actions = {}

        def submenu_insertar(key: str, text: str) -> None:
            """Insertar una pagina, eligiendo su tamano en el momento."""
            sub = menu.addMenu(text)
            igual = sub.addAction(tr("size_same"))
            actions[igual] = f"{key}:"          # sin tamano = como la vecina
            sub.addSeparator()
            for name in PAGE_SIZES:
                actions[sub.addAction(page_size_label(name))] = f"{key}:{name}"

        submenu_insertar("insert_before", tr("page_insert_before"))
        submenu_insertar("insert_after", tr("page_insert_after"))
        menu.addSeparator()
        duplicar = menu.addAction(tr("page_duplicate"))
        menu.addSeparator()
        girar_izq = menu.addAction(tr("page_rotate_left"))
        girar_der = menu.addAction(tr("page_rotate_right"))
        girar_180 = menu.addAction(tr("page_rotate_180"))
        menu.addSeparator()
        top = menu.addAction(tr("page_up"))
        bottom = menu.addAction(tr("page_down"))
        top.setEnabled(page_item > 0)
        bottom.setEnabled(page_item < self.view.page_count - 1)
        menu.addSeparator()
        erase_it = menu.addAction(tr("page_delete"))
        erase_it.setEnabled(self.view.page_count > 1)
        actions.update({
            duplicar: "duplicate",
            girar_izq: "rotate_left",
            girar_der: "rotate_right",
            girar_180: "rotate_180",
            top: "up",
            bottom: "down",
            erase_it: "delete",
        })
        return menu, actions

    def run_page_action(self, action: str | None, page_item: int) -> None:
        """Ejecuta una de las opciones del menu de pagina."""
        if action is None or not self.view.has_document():
            return
        # Las opciones de insertar llevan el tamano detras: "insert_after:A4".
        # Sin nada detras, la pagina nueva copia el tamano de la de al lado.
        size = None
        if ":" in action:
            action, _, name = action.partition(":")
            size = name or None
        if action == "insert_before":
            self.view.add_page(page_item, size)
            self._after_page_change(page_item)
        elif action == "insert_after":
            self.view.add_page(page_item + 1, size)
            self._after_page_change(page_item + 1)
        elif action == "duplicate":
            self.view.duplicate_page(page_item)
            self._after_page_change(page_item + 1)
        elif action in ("rotate_left", "rotate_right", "rotate_180"):
            grados = {"rotate_left": -90, "rotate_right": 90, "rotate_180": 180}[action]
            self.view.rotate_page(page_item, grados)
            self._after_page_change(page_item)
        elif action == "up" and page_item > 0:
            self.view.move_page(page_item, page_item - 1)
            self._after_page_change(page_item - 1)
        elif action == "down" and page_item < self.view.page_count - 1:
            self.view.move_page(page_item, page_item + 1)
            self._after_page_change(page_item + 1)
        elif action == "delete":
            self.view.go_to_page(page_item)
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

    def _on_search_text_changed(self, text: str) -> None:
        if not text.strip():
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

    def toggle_side_panel(self, checked: bool) -> None:
        """Ensena o esconde el panel de marcadores, notas y elementos."""
        self.bookmark_dock.setVisible(checked)
        self.settings.set_value("view/side_panel", bool(checked))

    def _nothing_selected(self) -> None:
        """Explica por que no pasa nada, en vez de quedarse callado.

        Con una herramienta de dibujo activa el clic pinta en lugar de
        seleccionar, asi que no hay nada que borrar ni que copiar. Antes DEL
        no hacia absolutamente nada y no habia forma de saber por que.
        """
        key = "status_no_selection" if self.view.tool is Tool.SELECT else "status_pick_select"
        self.statusBar().showMessage(tr(key), 4000)

    def delete_selection(self) -> None:
        if self.view.delete_selected():
            self.statusBar().clearMessage()   # no dejar colgado el aviso anterior
        else:
            self._nothing_selected()

    def copy_selection(self) -> None:
        how_many = self.view.copy_selected()
        if how_many:
            self.statusBar().showMessage(tr("status_copied", count=how_many), 3000)
        else:
            self._nothing_selected()

    def cut_selection(self) -> None:
        how_many = self.view.cut_selected()
        if how_many:
            self.statusBar().showMessage(tr("status_cut", count=how_many), 3000)
        else:
            self._nothing_selected()

    def paste_clipboard(self) -> None:
        how_many = self.view.paste_clipboard()
        if how_many:
            self.statusBar().showMessage(tr("status_pasted", count=how_many), 3000)
        else:
            self.statusBar().showMessage(tr("status_clipboard_empty"), 3000)

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
        editing = self.view.is_editing_text
        # Estas tres van activas aunque no haya nada seleccionado: si se
        # desactivan, el atajo no llega a dispararse y DEL o Ctrl+C no hacen
        # nada ni dicen nada. Prefieren avisar en la barra de estado.
        self.act_delete.setEnabled(has_doc and not editing)
        # Mientras se escribe dentro de un texto, copiar y pegar son los del
        # editor: si las acciones siguieran activas robarian el atajo y no se
        # podria copiar una palabra.
        self.act_copy.setEnabled(has_doc and not editing)
        self.act_cut.setEnabled(has_doc and not editing)
        self.act_paste.setEnabled(has_doc and not editing)
        self._update_element_buttons()
        self.act_page_delete.setEnabled(has_doc and self.view.page_count > 1)
        self.act_select_all.setEnabled(has_doc and not editing)
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
        # Lo que se estuviera escribiendo en una celda se guarda antes de
        # preguntar nada: si no, se perderia sin avisar y ademas quedaria un
        # editor vivo colgando de la tabla mientras Qt desmonta la escena.
        self.view.finish_all_editing()
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
        if hasattr(self, "updater"):
            self.updater.cancel()
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
                data = fh.read()
        except OSError as exc:
            QMessageBox.warning(self, __app_name__, tr("image_unreadable", error=exc))
            return False
        view = self.view
        if window_pos is not None:
            point = view.viewport().mapFrom(self, window_pos)
            scene = view.mapToScene(point)
        else:
            scene = view.mapToScene(view.viewport().rect().center())
        page_item = view.nearest_page(scene)
        if page_item is None:
            return False
        view.place_image(os.path.basename(path), data, page_item.index, page_item.mapFromScene(scene))
        self.statusBar().showMessage(tr("status_image_placed", name=os.path.basename(path)), 4000)
        return True

    # ------------------------------------------------------------------ actualizaciones
    def _setup_updates(self) -> None:
        """Prepara el aviso de version nueva y lo lanza si toca."""
        from .update_check import UpdateChecker

        self._update_manual = False
        self.updater = UpdateChecker(self)
        self.updater.finished.connect(self._on_update_result)
        active = self.settings.value("updates/auto", True, type_=bool)
        self.act_update_auto.blockSignals(True)
        self.act_update_auto.setChecked(bool(active))
        self.act_update_auto.blockSignals(False)
        if active:
            # Se retrasa un poco: primero que arranque la ventana.
            QTimer.singleShot(2500, lambda: self.check_updates(manual=False))

    def _set_update_auto(self, active: bool) -> None:
        self.settings.set_value("updates/auto", bool(active))

    def check_updates(self, manual: bool = False) -> None:
        """Pregunta a la web oficial si hay una version mas nueva."""
        if self.updater.running:
            return
        self._update_manual = manual
        if manual:
            self.statusBar().showMessage(tr("update_checking"), 5000)
        self.updater.start()

    def _on_update_result(self, data) -> None:
        if not data:
            if self._update_manual:
                QMessageBox.information(
                    self, __app_name__, tr("update_none", version=__version__)
                )
            return
        nueva = str(data.get("version", ""))
        if not self._update_manual and nueva == self.settings.value("updates/skip", ""):
            return                       # el usuario dijo que no le avisaran
        self._ask_to_update(nueva, data)

    def _ask_to_update(self, nueva: str, data: dict) -> None:
        from .update_download import UpdateDialog

        dialogo = UpdateDialog(self, nueva, data, install_cb=self.install_update)
        dialogo.exec()
        if dialogo.skipped:
            self.settings.set_value("updates/skip", nueva)

    def install_update(self, path: str) -> bool:
        """Cierra el programa y arranca el instalador que se acaba de bajar.

        Devuelve False si el usuario cancela al cerrar (por ejemplo porque
        tenia un documento sin guardar): entonces no se instala nada.
        """
        from ..updates import launch_installer

        if not self.close():             # respeta el aviso de cambios sin guardar
            return False
        try:
            launch_installer(path)
        except Exception as exc:         # pragma: no cover - depende del sistema
            QMessageBox.warning(
                self, __app_name__, tr("update_download_failed", error=str(exc))
            )
            return False
        QApplication.quit()
        return True

    # ------------------------------------------------------------------ ayuda
    def show_about(self) -> None:
        AboutDialog(self).exec()

    def show_help(self) -> None:
        HelpDialog(self).exec()


__all__ = ["MainWindow", "AboutDialog", "HelpDialog", "LicencesDialog"]
