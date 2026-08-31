"""Vista del documento: paginas, herramientas de anotacion y navegacion."""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from ..config import MAX_ZOOM, MIN_ZOOM
from ..document import PdfDocument, SearchHit
from ..i18n import tr
from ..model import (
    ERASER_DEFAULT,
    ERASER_SIZES,
    Align,
    Annotation,
    AnnotationStore,
    Font,
    Kind,
    move_annotation,
)
from .commands import (
    AddAnnotationCommand,
    AddPageCommand,
    ChangeAnnotationsCommand,
    DeleteAnnotationsCommand,
    DeletePageCommand,
    MovePageCommand,
    RotatePageCommand,
)
from .items import (
    AnnotationItemMixin,
    TableItem,
    TextItem,
    create_item,
)

PAGE_GAP = 16.0        # separacion entre paginas, en puntos
PAGE_MARGIN = 16.0     # margen alrededor del documento
MAX_RENDER_SCALE = 4.0
KEEP_RENDERED = 8      # paginas rasterizadas que se mantienen en memoria


class Tool(str, Enum):
    """Herramienta activa del puntero."""

    SELECT = "select"
    PAN = "hand"
    RECT = "rect"
    HIGHLIGHT = "highlight"
    LINE = "line"
    ARROW = "arrow"
    TEXT = "text"
    INK = "ink"
    TABLE = "table"
    IMAGE = "image"
    NOTE = "note"
    ERASER = "eraser"

    @property
    def kind(self) -> Kind | None:
        mapping = {
            Tool.RECT: Kind.RECT,
            Tool.HIGHLIGHT: Kind.HIGHLIGHT,
            Tool.LINE: Kind.LINE,
            Tool.ARROW: Kind.ARROW,
            Tool.TEXT: Kind.TEXT,
            Tool.INK: Kind.INK,
            Tool.TABLE: Kind.TABLE,
            Tool.IMAGE: Kind.IMAGE,
            Tool.NOTE: Kind.NOTE,
        }
        return mapping.get(self)


class PageItem(QGraphicsItem):
    """Una pagina del PDF. Sus coordenadas locales son puntos PDF."""

    def __init__(self, index: int, width: float, height: float) -> None:
        super().__init__()
        self.index = index
        self._size = (width, height)
        self._pixmap: QPixmap | None = None
        self._pixmap_scale = 0.0
        self.setFlag(QGraphicsItem.ItemUsesExtendedStyleOption, True)
        # Las anotaciones son hijas de la pagina y no pueden pintar fuera de
        # ella: la goma es blanca y opaca, asi que al salirse de la hoja se
        # comia el fondo gris. Lo que se sale tampoco saldria impreso, asi que
        # recortarlo aqui es ademas lo que hace que la pantalla y el papel
        # coincidan.
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
        self.setZValue(0)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._size[0], self._size[1])

    def set_pixmap(self, pixmap: QPixmap | None, scale: float) -> None:
        self._pixmap = pixmap
        self._pixmap_scale = scale
        self.update()

    @property
    def rendered_scale(self) -> float:
        return self._pixmap_scale

    def has_pixmap(self) -> bool:
        return self._pixmap is not None

    def paint(self, painter: QPainter, option, widget=None) -> None:
        rect = self.boundingRect()
        painter.fillRect(rect, QBrush(QColor("#ffffff")))
        if self._pixmap is not None:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))
        pen = QPen(QColor(0, 0, 0, 60))
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)


class AnnotationScene(QGraphicsScene):
    """Escena que avisa cuando una anotacion empieza y termina de editarse."""

    annotationEdited = Signal(object, object, object)  # item, antes, despues
    textEditing = Signal(bool)                        # hay un texto en edicion

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._snapshots: dict[int, Annotation] = {}

    def begin_edit(self, item) -> None:
        self._snapshots[id(item)] = item.ann.copy()

    def text_editing_started(self, item) -> None:
        self.textEditing.emit(True)

    def text_editing_finished(self, item) -> None:
        self.textEditing.emit(False)

    def end_edit(self, item) -> None:
        before = self._snapshots.pop(id(item), None)
        if before is None:
            return
        after = item.ann.copy()
        if _same_geometry(before, after):
            return
        self.annotationEdited.emit(item, before, after)


def _same_geometry(a: Annotation, b: Annotation) -> bool:
    return (
        a.rect == b.rect
        and a.p1 == b.p1
        and a.p2 == b.p2
        and a.strokes == b.strokes
        and a.text == b.text
    )


class PdfView(QGraphicsView):
    """Visor con desplazamiento continuo y herramientas de anotacion."""

    pageChanged = Signal(int)
    zoomChanged = Signal(float)
    modified = Signal()
    toolFinished = Signal()
    eraserSizeChanged = Signal(float)
    noteCreated = Signal(object)
    mouseMovedOnPage = Signal(object)   # posicion en el viewport
    guidesChanged = Signal()            # hay que repintar las reglas
    selectionChanged = Signal()
    textEditing = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = AnnotationScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.setBackgroundBrush(QBrush(QColor("#525659")))
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setFocusPolicy(Qt.StrongFocus)

        self.document: PdfDocument | None = None
        self.store = AnnotationStore()
        self.undo_stack = QUndoStack(self)

        self._page_items: list[PageItem] = []
        # Los items viven en la escena (propiedad de C++), pero hay que
        # conservar la referencia de Python o el recolector se lleva la parte
        # Python del objeto y deja de pintarse con su clase.
        self._items: dict[str, AnnotationItemMixin] = {}
        self._zoom = 1.0
        self._fit_mode: str | None = "width"
        self._current_page = 0
        self._tool = Tool.SELECT
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._draft_item = None
        self._draft_origin = QPointF()
        self._draft_page = 0
        self.snap_enabled = True
        self._guides = (None, None, None)
        # Guias del usuario, en coordenadas de pagina: {pagina: {"h": [...], "v": [...]}}
        self.rulers_guides: dict[int, dict[str, list[float]]] = {}
        self._guide_drag = None      # ("h"|"v", pagina, valor, indice o None)
        self._eraser_size = ERASER_DEFAULT
        # Cuantas veces se ha pegado lo mismo: cada pegada se separa un poco
        # mas para que no se apilen unas encima de otras sin verse.
        self._paste_count = 0
        self._erasing = False
        self._erase_item = None
        self._eraser_color = (1.0, 1.0, 1.0)   # blanco, el color del papel
        self._search_items: list[QGraphicsRectItem] = []
        self._hits: list[SearchHit] = []
        self._hit_index = -1
        self._text_editing = False

        self.style_defaults: dict[str, object] = {
            "color": (0.85, 0.10, 0.10),
            "fill": None,
            "width": 2.0,
            "opacity": 1.0,
            "font_size": 12.0,
            "highlight_color": (1.0, 0.83, 0.0),
            "font": Font.SANS,
            "bold": False,
            "italic": False,
            "align": Align.LEFT,
            "rows": 3,
            "cols": 3,
            "image": None,      # (nombre, bytes) de la imagen elegida
        }

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(20)
        self._render_timer.timeout.connect(self._render_visible_pages)

        self.verticalScrollBar().valueChanged.connect(self._on_scrolled)
        self.horizontalScrollBar().valueChanged.connect(self._schedule_render)
        self._scene.annotationEdited.connect(self._on_annotation_edited)
        self._scene.selectionChanged.connect(self.selectionChanged)
        self._scene.textEditing.connect(self._on_text_editing)

    def _on_text_editing(self, editing: bool) -> None:
        """Mientras se escribe, el texto manda: nada de atajos globales."""
        self._text_editing = editing
        self.textEditing.emit(editing)

    @property
    def is_editing_text(self) -> bool:
        return self._text_editing

    # ------------------------------------------------------------------ documento
    def set_document(self, doc: PdfDocument | None) -> None:
        """Carga (o descarga) un documento y reconstruye la escena."""
        self.document = doc
        self.store = AnnotationStore()
        self._items = {}
        self.undo_stack.clear()
        self.clear_search()
        self._scene.clear()
        self._page_items = []
        self._current_page = 0
        if doc is None:
            self._scene.setSceneRect(QRectF())
            return
        self._build_page_items()
        self._load_existing_notes(doc)
        self.verticalScrollBar().setValue(0)
        self.apply_fit()
        self._render_visible_pages()
        self.pageChanged.emit(0)

    def _load_existing_notes(self, doc: PdfDocument) -> None:
        """Recoge las notas que ya trae el PDF para poder verlas y editarlas.

        Se sacan del documento y pasan a la lista de anotaciones, que es desde
        donde se vuelven a escribir al guardar. Asi no se duplican.
        """
        from .items import NOTE_SIZE

        for pagina, x, y, texto in doc.take_notes():
            if not (0 <= pagina < len(self._page_items)):
                continue
            ann = Annotation(
                kind=Kind.NOTE,
                page=pagina,
                rect=(x, y, x + NOTE_SIZE, y + NOTE_SIZE),
                text=texto,
                color=(0.98, 0.80, 0.20),
            )
            self.store.add(ann)
            self.attach_item(create_item(ann, self._page_items[pagina]), ann)

    def _build_page_items(self) -> None:
        """Crea un item por pagina y ajusta el tamano de la escena."""
        doc = self.document
        if doc is None:
            return
        y = PAGE_MARGIN
        tamanos = doc.page_sizes()
        max_width = max((w for w, _ in tamanos), default=0.0)
        for index, (width, height) in enumerate(tamanos):
            item = PageItem(index, width, height)
            item.setPos(PAGE_MARGIN + (max_width - width) / 2.0, y)
            self._scene.addItem(item)
            self._page_items.append(item)
            y += height + PAGE_GAP
        total_height = y - PAGE_GAP + PAGE_MARGIN
        self._scene.setSceneRect(
            0, 0, max_width + 2 * PAGE_MARGIN, max(total_height, 1.0)
        )

    def refresh_pages(self) -> None:
        """Rehace la disposicion tras anadir, duplicar o borrar paginas."""
        if self.document is None:
            return
        self.clear_search()
        for item in self._items.values():
            item.setParentItem(None)
            if item.scene() is not None:
                self._scene.removeItem(item)
        for pagina in self._page_items:
            self._scene.removeItem(pagina)
        self._page_items = []
        self._build_page_items()
        for item in list(self._items.values()):
            if 0 <= item.ann.page < len(self._page_items):
                item.setParentItem(self._page_items[item.ann.page])
                item.apply_model()
            else:  # pragma: no cover - defensivo
                self._items.pop(item.ann.id, None)
        self._current_page = min(self._current_page, max(0, len(self._page_items) - 1))
        self.apply_fit()
        self._render_visible_pages()
        self.pageChanged.emit(self._current_page)
        self.notify_modified()

    # -- operaciones sobre paginas ---------------------------------------
    def add_page(self, index: int | None = None, size=None) -> None:
        """Inserta una pagina en blanco (al final si no se indica donde)."""
        if self.document is None:
            return
        destino = self.document.page_count if index is None else index
        self.undo_stack.push(AddPageCommand(self, destino, size))

    def duplicate_page(self, index: int) -> None:
        if self.document is None:
            return
        self.undo_stack.push(AddPageCommand(self, index + 1, duplicate=True))

    def delete_page(self, index: int) -> None:
        if self.document is None or self.document.page_count <= 1:
            return
        self.undo_stack.push(DeletePageCommand(self, index))

    def rotate_page(self, index: int, delta: int) -> None:
        """Gira una pagina (delta en grados horarios: 90, 180 o -90)."""
        if self.document is None or delta % 360 == 0:
            return
        self.undo_stack.push(RotatePageCommand(self, index, delta))

    def move_page(self, index: int, destino: int) -> None:
        if self.document is None or index == destino:
            return
        self.undo_stack.push(MovePageCommand(self, index, destino))

    def shift_annotation_pages(self, desde: int, delta: int) -> None:
        """Recoloca las anotaciones cuando se insertan o quitan paginas."""
        for ann in self.store:
            if ann.page >= desde:
                ann.page += delta

    def items_on_page(self, index: int) -> list:
        return [item for item in self._items.values() if item.ann.page == index]

    @property
    def page_count(self) -> int:
        return len(self._page_items)

    def current_page_item(self):
        """PageItem de la pagina en la que se esta trabajando (o None)."""
        if 0 <= self._current_page < len(self._page_items):
            return self._page_items[self._current_page]
        return None

    @property
    def current_page(self) -> int:
        return self._current_page

    def has_document(self) -> bool:
        return self.document is not None

    def notify_modified(self) -> None:
        self.modified.emit()

    # ------------------------------------------------------------------ render
    def _device_scale(self) -> float:
        return float(self.devicePixelRatioF() or 1.0)

    def _render_scale(self) -> float:
        scale = abs(self.transform().m11()) * self._device_scale()
        return max(0.15, min(MAX_RENDER_SCALE, scale))

    def _schedule_render(self) -> None:
        self._render_timer.start()

    def _visible_scene_rect(self) -> QRectF:
        rect = self.mapToScene(self.viewport().rect()).boundingRect()
        margin = rect.height() * 0.5
        return rect.adjusted(0, -margin, 0, margin)

    def _render_visible_pages(self) -> None:
        if self.document is None:
            return
        visible = self._visible_scene_rect()
        scale = self._render_scale()
        rendered: list[int] = []
        for item in self._page_items:
            if not item.sceneBoundingRect().intersects(visible):
                continue
            rendered.append(item.index)
            if item.has_pixmap() and abs(item.rendered_scale - scale) < 0.01:
                continue
            try:
                page = self.document.render_page(item.index, scale)
            except Exception:  # pragma: no cover - PDF danado
                continue
            image = QImage(
                page.samples, page.width, page.height, page.stride, QImage.Format_RGB888
            )
            pixmap = QPixmap.fromImage(image.copy())
            pixmap.setDevicePixelRatio(1.0)
            item.set_pixmap(pixmap, scale)
        # Libera memoria de las paginas lejanas.
        if len(rendered) and len(self._page_items) > KEEP_RENDERED:
            keep = set(rendered)
            low, high = min(keep), max(keep)
            keep.update(range(max(0, low - 2), min(len(self._page_items), high + 3)))
            for item in self._page_items:
                if item.index not in keep and item.has_pixmap():
                    item.set_pixmap(None, 0.0)

    def _on_scrolled(self) -> None:
        self._schedule_render()
        self._update_current_page()

    def _update_current_page(self) -> None:
        """La pagina actual es la que ocupa mas alto de la ventana."""
        if not self._page_items:
            return
        view_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        best, best_overlap = self._current_page, -1.0
        for item in self._page_items:
            rect = item.sceneBoundingRect()
            overlap = min(rect.bottom(), view_rect.bottom()) - max(rect.top(), view_rect.top())
            if overlap > best_overlap:
                best, best_overlap = item.index, overlap
        if best != self._current_page:
            self._current_page = best
            self.pageChanged.emit(best)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode:
            self.apply_fit()
        self._schedule_render()

    # ------------------------------------------------------------------ zoom
    @property
    def zoom(self) -> float:
        return self._zoom

    def _dpi_factor(self) -> float:
        return max(1.0, float(self.logicalDpiX())) / 72.0

    def set_zoom(self, zoom: float, fit_mode: str | None = None) -> None:
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, float(zoom)))
        self._fit_mode = fit_mode
        self._zoom = zoom
        scale = zoom * self._dpi_factor()
        self.setTransform(QTransform.fromScale(scale, scale))
        self.zoomChanged.emit(zoom)
        self._schedule_render()

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / 1.25)

    def reset_zoom(self) -> None:
        self.set_zoom(1.0)

    def fit_width(self) -> None:
        self._fit_mode = "width"
        self.apply_fit()

    def fit_page(self) -> None:
        self._fit_mode = "page"
        self.apply_fit()

    def apply_fit(self) -> None:
        """Recalcula el zoom para el modo de ajuste activo."""
        if not self._page_items or not self._fit_mode:
            return
        page = self._page_items[min(self._current_page, len(self._page_items) - 1)]
        rect = page.boundingRect()
        viewport = self.viewport().size()
        scrollbar = self.verticalScrollBar().sizeHint().width() + 4
        dpi = self._dpi_factor()
        if self._fit_mode == "width":
            available = max(50, viewport.width() - scrollbar - 2 * PAGE_MARGIN)
            zoom = available / (rect.width() * dpi)
        else:
            available_w = max(50, viewport.width() - scrollbar - 2 * PAGE_MARGIN)
            available_h = max(50, viewport.height() - 2 * PAGE_MARGIN)
            zoom = min(available_w / (rect.width() * dpi), available_h / (rect.height() * dpi))
        mode = self._fit_mode
        self.set_zoom(zoom, fit_mode=mode)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.set_zoom(self._zoom * (1.15 if delta > 0 else 1 / 1.15))
            event.accept()
            return
        super().wheelEvent(event)

    # ------------------------------------------------------------------ navegacion
    def go_to_page(self, index: int) -> None:
        if not self._page_items:
            return
        index = max(0, min(len(self._page_items) - 1, index))
        rect = self._page_items[index].sceneBoundingRect()
        view_height = self.mapToScene(self.viewport().rect()).boundingRect().height()
        # Deja el borde superior de la pagina justo arriba del area visible.
        self.centerOn(rect.center().x(), rect.top() + view_height / 2 - PAGE_GAP / 2)
        self._current_page = index
        self.pageChanged.emit(index)
        self._schedule_render()

    def next_page(self) -> None:
        self.go_to_page(self._current_page + 1)

    def previous_page(self) -> None:
        self.go_to_page(self._current_page - 1)

    # ------------------------------------------------------------------ herramientas
    @property
    def tool(self) -> Tool:
        return self._tool

    def set_tool(self, tool: Tool) -> None:
        self._tool = tool
        self._update_cursor()
        editable = tool is Tool.SELECT
        for item in self._annotation_items():
            item.setFlag(QGraphicsItem.ItemIsMovable, editable)
            item.setFlag(QGraphicsItem.ItemIsSelectable, editable)
        if not editable:
            self._scene.clearSelection()

    def _update_cursor(self) -> None:
        """Pone el cursor de la herramienta activa."""
        tool = self._tool
        if tool is Tool.PAN:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().setCursor(Qt.OpenHandCursor)
        elif tool is Tool.SELECT:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
        elif tool is Tool.ERASER:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(self._eraser_cursor())
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)

    def _eraser_cursor(self) -> QCursor:
        """Circulo del tamano real de la goma, para ver que se va a borrar."""
        lado = max(8, min(128, int(self._eraser_size * self._zoom)))
        pixmap = QPixmap(lado + 2, lado + 2)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # doble trazo para que se vea sobre fondo claro y sobre fondo oscuro
        r, g, b = self._eraser_color
        relleno = QColor(int(r * 255), int(g * 255), int(b * 255))
        relleno.setAlpha(150)
        painter.setBrush(relleno)                 # el color con el que tapa
        painter.setPen(QPen(QColor(255, 255, 255, 220), 3))
        painter.drawEllipse(1, 1, lado, lado)
        painter.setPen(QPen(QColor(20, 20, 20, 230), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(1, 1, lado, lado)
        painter.end()
        return QCursor(pixmap, lado // 2, lado // 2)

    def _annotation_items(self) -> list[AnnotationItemMixin]:
        return [item for item in self._items.values() if item.scene() is not None]

    def selected_items(self) -> list[AnnotationItemMixin]:
        return [i for i in self._scene.selectedItems() if isinstance(i, AnnotationItemMixin)]

    def page_at(self, scene_pos: QPointF) -> PageItem | None:
        for item in self._page_items:
            if item.sceneBoundingRect().contains(scene_pos):
                return item
        return None

    def nearest_page(self, scene_pos: QPointF) -> PageItem | None:
        if not self._page_items:
            return None
        page = self.page_at(scene_pos)
        if page is not None:
            return page
        return min(
            self._page_items,
            key=lambda it: abs(it.sceneBoundingRect().center().y() - scene_pos.y()),
        )

    # -- creacion de anotaciones ----------------------------------------
    def _new_annotation(self, kind: Kind, page: int, point: QPointF) -> Annotation:
        style = self.style_defaults
        color = style["highlight_color"] if kind is Kind.HIGHLIGHT else style["color"]
        ann = Annotation(
            kind=kind,
            page=page,
            color=tuple(color),
            width=float(style["width"]),
            opacity=float(style["opacity"]),
            font_size=float(style["font_size"]),
            fill=tuple(style["fill"]) if style["fill"] else None,
            font=Font(style["font"]),
            bold=bool(style["bold"]),
            italic=bool(style["italic"]),
            align=Align(style["align"]),
            rows=int(style["rows"]),
            cols=int(style["cols"]),
        )
        if kind is Kind.IMAGE:
            imagen = style.get("image") or ("", b"")
            ann.image_name, ann.image_data = imagen[0], imagen[1]
        if kind is Kind.NOTE:
            from .items import NOTE_SIZE
            ann.rect = (point.x(), point.y(),
                        point.x() + NOTE_SIZE, point.y() + NOTE_SIZE)
        if kind in (Kind.LINE, Kind.ARROW):
            ann.p1 = (point.x(), point.y())
            ann.p2 = (point.x(), point.y())
        elif kind is Kind.INK:
            ann.strokes = [[(point.x(), point.y())]]
        else:
            ann.rect = (point.x(), point.y(), point.x(), point.y())
        if kind is Kind.TEXT and ann.fill is None:
            ann.width = 0.0
        if kind is Kind.TABLE:
            # La rejilla siempre se ve, aunque el trazo elegido sea 0.
            ann.width = max(0.5, ann.width)
        return ann

    def attach_item(self, item, ann: Annotation) -> None:
        """Cuelga un item de su pagina y lo registra (usado tambien al rehacer)."""
        page = self._page_items[ann.page] if 0 <= ann.page < len(self._page_items) else None
        if page is not None:
            item.setParentItem(page)
        elif item.scene() is None:  # pragma: no cover - defensivo
            self._scene.addItem(item)
        item.setVisible(True)
        self._items[ann.id] = item

    def place_image(self, name: str, data: bytes, page: int, point: QPointF):
        """Coloca una imagen en la pagina indicada (coordenadas de la pagina)."""
        ann = Annotation(kind=Kind.IMAGE, page=page, image_name=name, image_data=data)
        ann.rect = (point.x(), point.y(), point.x(), point.y())
        item = create_item(ann, self._page_items[page])
        proporcion = getattr(item, "aspect", 1.0) or 1.0
        ancho = min(self._page_items[page].boundingRect().width() * 0.4, 260.0)
        ann.rect = (point.x(), point.y(), point.x() + ancho, point.y() + ancho / proporcion)
        item.apply_model()
        self._items[ann.id] = item
        self.undo_stack.push(AddAnnotationCommand(self, ann, item))
        item.setSelected(True)
        return item

    def apply_template(self, annotations, first_page: int | None = None) -> int:
        """Anade las anotaciones de una plantilla. Devuelve cuantas ha colocado."""
        if self.document is None:
            return 0
        from ..templates import shift_to_page

        inicio = self.current_page if first_page is None else first_page
        colocadas = shift_to_page(annotations, inicio, self.page_count)
        if not colocadas:
            return 0
        self.undo_stack.beginMacro(tr("cmd_template", count=len(colocadas)))
        for ann in colocadas:
            self.add_annotation(ann)
        self.undo_stack.endMacro()
        return len(colocadas)

    #: Margen minimo al soltar un grupo de anotaciones, en puntos PDF.
    DROP_MARGIN = 24.0

    def insert_annotations(self, annotations, label: str | None = None) -> int:
        """Suelta un grupo de anotaciones donde este mirando el usuario.

        Se usa para las piezas de formulario: llegan colocadas unas respecto a
        otras y aqui se mueven en bloque al centro de lo que se ve, sin que se
        salgan del papel. Todo el grupo es un solo paso de deshacer.
        """
        if self.document is None:
            return 0
        piezas = [ann.copy() for ann in annotations]
        if not piezas:
            return 0
        for ann in piezas:
            ann.id = Annotation(kind=ann.kind, page=0).id   # identidad nueva

        pagina = self.current_page
        item = self._page_items[pagina]
        limites = [ann.bounds() for ann in piezas]
        x0 = min(min(b[0], b[2]) for b in limites)
        y0 = min(min(b[1], b[3]) for b in limites)
        ancho = max(max(b[0], b[2]) for b in limites) - x0
        alto = max(max(b[1], b[3]) for b in limites) - y0

        centro = item.mapFromScene(self.mapToScene(self.viewport().rect().center()))
        hoja = item.boundingRect()
        margen = self.DROP_MARGIN
        destino_x = min(max(margen, centro.x() - ancho / 2),
                        max(margen, hoja.width() - ancho - margen))
        destino_y = min(max(margen, centro.y() - alto / 2),
                        max(margen, hoja.height() - alto - margen))

        self._scene.clearSelection()
        self.undo_stack.beginMacro(label or tr("cmd_paste", count=len(piezas)))
        for ann in piezas:
            ann.page = pagina
            move_annotation(ann, destino_x - x0, destino_y - y0)
            self.add_annotation(ann).setSelected(True)
        self.undo_stack.endMacro()
        return len(piezas)

    def add_annotation(self, ann: Annotation, undoable: bool = True):
        """Anade al documento una anotacion ya definida y devuelve su item.

        Es la via publica para crear anotaciones sin raton (guiones, pruebas o
        futuras funciones como sellos o firmas).
        """
        if not (0 <= ann.page < len(self._page_items)):
            raise IndexError(f"la pagina {ann.page} no existe en el documento")
        item = create_item(ann, self._page_items[ann.page])
        self._items[ann.id] = item
        if undoable:
            self.undo_stack.push(AddAnnotationCommand(self, ann, item))
        else:
            self.store.add(ann)
            self.notify_modified()
        return item

    def detach_item(self, item) -> None:
        self._items.pop(item.ann.id, None)
        item.setSelected(False)
        item.setParentItem(None)
        if item.scene() is not None:
            self._scene.removeItem(item)

    def _finish_draft(self) -> None:
        item = self._draft_item
        self._draft_item = None
        if item is None:
            return
        ann = item.ann
        if ann.kind is Kind.IMAGE:
            x0, y0, x1, y1 = ann.normalized_rect()
            if (x1 - x0) < 20 or (y1 - y0) < 20:
                # Un clic sencillo coloca la imagen a un tamano comodo.
                proporcion = getattr(item, "aspect", 1.0) or 1.0
                pagina = self._page_items[ann.page].boundingRect()
                ancho = min(pagina.width() * 0.4, 260.0)
                ann.rect = (x0, y0, x0 + ancho, y0 + ancho / proporcion)
            item.apply_model()
        if ann.kind is Kind.TABLE:
            x0, y0, x1, y1 = ann.normalized_rect()
            if (x1 - x0) < 40 or (y1 - y0) < 24:
                ann.rect = (x0, y0, x0 + 90.0 * ann.cols, y0 + 26.0 * ann.rows)
            item.apply_model()
        if ann.kind is Kind.TEXT:
            x0, y0, x1, y1 = ann.normalized_rect()
            if (x1 - x0) < 24 or (y1 - y0) < ann.font_size:
                ann.rect = (x0, y0, x0 + 220.0, y0 + ann.font_size * 1.8)
            item.apply_model()
        if ann.is_empty() and ann.kind not in (Kind.TEXT, Kind.TABLE):
            self.detach_item(item)
            return
        item.sync_model()
        self._items[ann.id] = item
        self.undo_stack.push(AddAnnotationCommand(self, ann, item))
        self.set_tool(Tool.SELECT)
        item.setSelected(True)
        if isinstance(item, TextItem):
            item.start_editing()
        elif isinstance(item, TableItem):
            item.edit_cell(0)
        elif ann.kind is Kind.NOTE:
            self.noteCreated.emit(item)   # la ventana pide el texto
        self.toolFinished.emit()

    def _draw_ruler_guides(self, painter) -> None:  # pragma: no cover - dibujo
        """Pinta las guias sacadas de las reglas."""
        lapiz = QPen(QColor("#00a3c4"))
        lapiz.setWidthF(1.0)
        lapiz.setCosmetic(True)
        for pagina, item in enumerate(self._page_items):
            guias = self.rulers_guides.get(pagina)
            if not guias:
                continue
            caja = item.sceneBoundingRect()
            painter.setPen(lapiz)
            for y in guias["h"]:
                sy = item.mapToScene(QPointF(0, y)).y()
                painter.drawLine(QPointF(caja.left(), sy), QPointF(caja.right(), sy))
            for x in guias["v"]:
                sx = item.mapToScene(QPointF(x, 0)).x()
                painter.drawLine(QPointF(sx, caja.top()), QPointF(sx, caja.bottom()))

        # la que se esta arrastrando, discontinua para distinguirla
        if self._guide_drag is not None:
            orientacion, pagina, valor, _indice = self._guide_drag
            if 0 <= pagina < len(self._page_items):
                item = self._page_items[pagina]
                caja = item.sceneBoundingRect()
                arrastre = QPen(QColor("#00a3c4"))
                arrastre.setStyle(Qt.DashLine)
                arrastre.setWidthF(1.0)
                arrastre.setCosmetic(True)
                painter.setPen(arrastre)
                if orientacion == "h":
                    sy = item.mapToScene(QPointF(0, valor)).y()
                    painter.drawLine(QPointF(caja.left(), sy), QPointF(caja.right(), sy))
                else:
                    sx = item.mapToScene(QPointF(valor, 0)).x()
                    painter.drawLine(QPointF(sx, caja.top()), QPointF(sx, caja.bottom()))

    # ------------------------------------------------------------------ guias del usuario
    def page_guides(self, page: int) -> dict[str, list[float]]:
        return self.rulers_guides.setdefault(page, {"h": [], "v": []})

    def start_guide(self, orientacion: str, valor: float) -> None:
        """Empieza a sacar una guia nueva desde la regla."""
        pagina = self._current_page
        self._guide_drag = (orientacion, pagina, valor, None)
        self._guides_changed()

    def grab_guide(self, orientacion: str, pagina: int, indice: int, valor: float) -> None:
        """Coge una guia que ya existe para moverla."""
        self._guide_drag = (orientacion, pagina, valor, indice)
        self._guides_changed()

    def move_guide(self, valor: float) -> None:
        if self._guide_drag is None or valor is None:
            return
        orientacion, pagina, _viejo, indice = self._guide_drag
        self._guide_drag = (orientacion, pagina, valor, indice)
        self._guides_changed()

    def drop_guide(self, valor) -> None:
        """Suelta la guia. Fuera de la pagina, se borra."""
        if self._guide_drag is None:
            return
        orientacion, pagina, ultimo, indice = self._guide_drag
        self._guide_drag = None
        if valor is None:
            valor = ultimo
        guias = self.page_guides(pagina)[orientacion]
        dentro = self._guide_inside(pagina, orientacion, valor)
        if indice is None:
            if dentro:
                guias.append(float(valor))
        elif 0 <= indice < len(guias):
            if dentro:
                guias[indice] = float(valor)
            else:
                del guias[indice]        # sacada fuera del margen: se borra
        self._guides_changed()

    def _guide_inside(self, pagina: int, orientacion: str, valor) -> bool:
        if valor is None or not (0 <= pagina < len(self._page_items)):
            return False
        caja = self._page_items[pagina].boundingRect()
        limite = caja.height() if orientacion == "h" else caja.width()
        return 0 <= valor <= limite

    def guide_at(self, escena_pos):
        """Guia que hay bajo un punto de la escena, si la hay."""
        margen = 4.0 / max(self._zoom, 1e-6)
        for pagina, item in enumerate(self._page_items):
            local = item.mapFromScene(escena_pos)
            caja = item.boundingRect()
            if not caja.adjusted(-margen, -margen, margen, margen).contains(local):
                continue
            guias = self.page_guides(pagina)
            for i, y in enumerate(guias["h"]):
                if abs(local.y() - y) <= margen:
                    return ("h", pagina, i, y)
            for i, x in enumerate(guias["v"]):
                if abs(local.x() - x) <= margen:
                    return ("v", pagina, i, x)
        return None

    def clear_guides_of_page(self, pagina: int) -> None:
        self.rulers_guides.pop(pagina, None)
        self._guides_changed()

    def clear_all_guides(self) -> None:
        self.rulers_guides.clear()
        self._guides_changed()

    def _guides_changed(self) -> None:
        """Repinta la pagina y avisa a las reglas."""
        self.viewport().update()
        self.guidesChanged.emit()

    # ------------------------------------------------------------------ guias
    def show_guides(self, x, y, page) -> None:
        """Marca las guias a las que se esta alineando (None = ninguna)."""
        nuevas = (x, y, page)
        if nuevas != self._guides:
            self._guides = nuevas
            self.viewport().update()

    def clear_guides(self) -> None:
        self.show_guides(None, None, None)

    def set_snap(self, enabled: bool) -> None:
        self.snap_enabled = bool(enabled)
        if not enabled:
            self.clear_guides()

    def drawForeground(self, painter, rect) -> None:  # pragma: no cover - dibujo
        super().drawForeground(painter, rect)
        self._draw_ruler_guides(painter)
        x, y, page = self._guides
        if page is None or (x is None and y is None):
            return
        caja = page.sceneBoundingRect()
        lapiz = QPen(QColor("#e91e63"))
        lapiz.setStyle(Qt.DashLine)
        lapiz.setWidthF(1.0 / max(self._zoom, 1e-6))
        lapiz.setCosmetic(True)
        painter.setPen(lapiz)
        if x is not None:
            escena_x = page.mapToScene(QPointF(x, 0)).x()
            painter.drawLine(QPointF(escena_x, caja.top()), QPointF(escena_x, caja.bottom()))
        if y is not None:
            escena_y = page.mapToScene(QPointF(0, y)).y()
            painter.drawLine(QPointF(caja.left(), escena_y), QPointF(caja.right(), escena_y))

    # ------------------------------------------------------------------ goma
    @property
    def eraser_size(self) -> float:
        """Diametro de la goma, en puntos PDF."""
        return self._eraser_size

    def set_eraser_size(self, size: float) -> None:
        menor, mayor = ERASER_SIZES[0], ERASER_SIZES[-1]
        nuevo = max(menor, min(float(size), mayor))
        if nuevo != self._eraser_size:
            self._eraser_size = nuevo
            self.eraserSizeChanged.emit(nuevo)
            self._update_cursor()

    @property
    def eraser_color(self):
        """Color con el que la goma tapa el documento."""
        return self._eraser_color

    def set_eraser_color(self, rgb) -> None:
        self._eraser_color = tuple(rgb)
        self._update_cursor()

    def step_eraser_size(self, delta: int) -> None:
        """Pasa al tamano siguiente o anterior de la lista (Ctrl+ / Ctrl-)."""
        actual = min(ERASER_SIZES, key=lambda t: abs(t - self._eraser_size))
        posicion = ERASER_SIZES.index(actual) + (1 if delta > 0 else -1)
        posicion = max(0, min(posicion, len(ERASER_SIZES) - 1))
        self.set_eraser_size(ERASER_SIZES[posicion])

    def erase_at(self, page_index: int, point: QPointF) -> bool:
        """Anade un punto al trazo con el que la goma tapa el documento."""
        if self._erase_item is None:
            return False
        self._erase_item.append_point(point)
        return True

    def _finish_erase(self) -> None:
        """Cierra el trazo de la goma y lo deja como una anotacion mas.

        No es un borrado destructivo: es pintura opaca encima, asi que se
        deshace, se mueve y se elimina como cualquier otra anotacion.
        """
        self._erasing = False
        item = self._erase_item
        self._erase_item = None
        if item is None:
            return
        if item.ann.is_empty():
            self.detach_item(item)
            return
        item.sync_model()
        self._items[item.ann.id] = item
        # Se apunta como "borrar con la goma" y no como "anadir dibujo":
        # por dentro es un trazo, pero el usuario ha borrado.
        self.undo_stack.push(
            AddAnnotationCommand(self, item.ann, item, tr("cmd_erase"))
        )

    # ------------------------------------------------------------------ raton
    def mousePressEvent(self, event) -> None:
        if (self._tool is Tool.SELECT and event.button() == Qt.LeftButton
                and self._guide_drag is None):
            escena = self.mapToScene(event.position().toPoint())
            encontrada = self.guide_at(escena)
            if encontrada is not None:
                orientacion, pagina, indice, valor = encontrada
                self.grab_guide(orientacion, pagina, indice, valor)
                event.accept()
                return
        if self._tool is Tool.ERASER and event.button() == Qt.LeftButton:
            if self.document is None:
                return
            scene_pos = self.mapToScene(event.position().toPoint())
            page = self.nearest_page(scene_pos)
            if page is None:
                return
            ann = Annotation(
                kind=Kind.INK,
                page=page.index,
                color=tuple(self._eraser_color),
                width=self._eraser_size,
                opacity=1.0,            # opaca: tiene que tapar lo de debajo
            )
            self._erase_item = create_item(ann, page)
            self._erasing = True
            self.erase_at(page.index, page.mapFromScene(scene_pos))
            event.accept()
            return
        kind = self._tool.kind
        if kind is None or event.button() != Qt.LeftButton or self.document is None:
            super().mousePressEvent(event)
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        page = self.nearest_page(scene_pos)
        if page is None:
            return
        local = page.mapFromScene(scene_pos)
        ann = self._new_annotation(kind, page.index, local)
        self._draft_item = create_item(ann, page)
        self._items[ann.id] = self._draft_item
        self._draft_origin = local
        self._draft_page = page.index
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self.mouseMovedOnPage.emit(event.position().toPoint())
        if self._guide_drag is not None:
            orientacion, pagina, _v, _i = self._guide_drag
            if 0 <= pagina < len(self._page_items):
                local = self._page_items[pagina].mapFromScene(
                    self.mapToScene(event.position().toPoint())
                )
                self.move_guide(local.y() if orientacion == "h" else local.x())
            event.accept()
            return
        if self._erasing and self._erase_item is not None:
            # se sigue pintando en la misma pagina en la que se empezo
            page = self._page_items[self._erase_item.ann.page]
            self.erase_at(page.index,
                          page.mapFromScene(self.mapToScene(event.position().toPoint())))
            event.accept()
            return
        if self._draft_item is None:
            super().mouseMoveEvent(event)
            return
        page = self._page_items[self._draft_page]
        local = page.mapFromScene(self.mapToScene(event.position().toPoint()))
        ann = self._draft_item.ann
        self._draft_item.prepareGeometryChange()
        if ann.kind in (Kind.LINE, Kind.ARROW):
            if event.modifiers() & Qt.ShiftModifier:
                local = _constrain_angle(self._draft_origin, local)
            ann.p2 = (local.x(), local.y())
        elif ann.kind is Kind.INK:
            self._draft_item.append_point(local)
        else:
            x0, y0 = self._draft_origin.x(), self._draft_origin.y()
            x1, y1 = local.x(), local.y()
            if ann.kind is Kind.IMAGE:
                # La imagen conserva su proporcion mientras se coloca.
                proporcion = getattr(self._draft_item, "aspect", 1.0) or 1.0
                ancho = abs(x1 - x0)
                alto = ancho / proporcion
                x1 = x0 + ancho * (1 if x1 >= x0 else -1)
                y1 = y0 + alto * (1 if y1 >= y0 else -1)
            elif event.modifiers() & Qt.ShiftModifier:
                side = max(abs(x1 - x0), abs(y1 - y0))
                x1 = x0 + side * (1 if x1 >= x0 else -1)
                y1 = y0 + side * (1 if y1 >= y0 else -1)
            ann.rect = (x0, y0, x1, y1)
        self._draft_item.apply_model()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._guide_drag is not None:
            orientacion, pagina, valor, _i = self._guide_drag
            if 0 <= pagina < len(self._page_items):
                local = self._page_items[pagina].mapFromScene(
                    self.mapToScene(event.position().toPoint())
                )
                valor = local.y() if orientacion == "h" else local.x()
            self.drop_guide(valor)
            event.accept()
            return
        self.clear_guides()
        if self._erasing and event.button() == Qt.LeftButton:
            self._finish_erase()
            event.accept()
            return
        if self._draft_item is not None and event.button() == Qt.LeftButton:
            self._finish_draft()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            if self._draft_item is not None:
                self.detach_item(self._draft_item)
                self._draft_item = None
            # Cerrar los editores abiertos: si no, el editor de una celda se
            # queda vivo con el foco y luego DEL no llega a borrar la tabla.
            self.finish_all_editing()
            self._scene.clearSelection()
            self.clear_search()
            self.set_tool(Tool.SELECT)
            self.toolFinished.emit()
            event.accept()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            focus = self._scene.focusItem()
            editando = self._text_editing or isinstance(focus, QGraphicsTextItem)
            if not editando and (not isinstance(focus, TextItem) or not focus.hasFocus()):
                if self.delete_selected():
                    event.accept()
                    return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ edicion
    def finish_all_editing(self) -> None:
        """Cierra cualquier celda o texto que se este editando."""
        for item in self._annotation_items():
            terminar = getattr(item, "finish_editing", None)
            if callable(terminar) and getattr(item, "is_editing", False):
                terminar()
            detener = getattr(item, "stop_editing", None)
            if callable(detener) and getattr(item, "_editing", False):
                detener()
        foco = self._scene.focusItem()
        if isinstance(foco, QGraphicsTextItem):
            foco.clearFocus()

    def delete_selected(self) -> bool:
        items = self.selected_items()
        if not items:
            return False
        self.undo_stack.push(DeleteAnnotationsCommand(self, items))
        return True

    def select_all_annotations(self) -> None:
        for item in self._annotation_items():
            item.setSelected(True)

    # ------------------------------------------------------- copiar y pegar
    #: Cuanto se separa lo pegado de su original, en puntos PDF. Lo justo
    #: para verlo encima y poder arrastrarlo, como en cualquier editor.
    PASTE_OFFSET = 12.0

    def copy_selected(self) -> int:
        """Copia lo seleccionado al portapapeles. Devuelve cuantas copio."""
        from .clipboard import copy_annotations

        items = self.selected_items()
        if not items:
            return 0
        cuantas = copy_annotations(item.ann for item in items)
        if cuantas:
            self._paste_count = 0        # la primera pegada va al lado
        return cuantas

    def cut_selected(self) -> int:
        """Copia y elimina. El borrado se deshace como cualquier otro."""
        cuantas = self.copy_selected()
        if cuantas:
            self.delete_selected()
        return cuantas

    def paste_clipboard(self, page: int | None = None) -> int:
        """Pega en la pagina indicada (por omision, la que se esta viendo)."""
        from ..templates import shift_to_page
        from .clipboard import clipboard_annotations

        if self.document is None:
            return 0
        copiadas = clipboard_annotations()
        if not copiadas:
            return 0
        destino = self.current_page if page is None else page
        # shift_to_page da identidad nueva a cada copia y conserva la
        # distancia entre paginas, para poder pegar lo copiado de varias.
        colocadas = shift_to_page(copiadas, destino, self.page_count)
        if not colocadas:
            return 0
        self._paste_count += 1
        salto = self.PASTE_OFFSET * self._paste_count
        for ann in colocadas:
            move_annotation(ann, salto, salto)
        self._scene.clearSelection()
        self.undo_stack.beginMacro(tr("cmd_paste", count=len(colocadas)))
        for ann in colocadas:
            item = self.add_annotation(ann)
            item.setSelected(True)       # queda listo para moverlo
        self.undo_stack.endMacro()
        return len(colocadas)

    def _on_annotation_edited(self, item, before, after) -> None:
        self.undo_stack.push(ChangeAnnotationsCommand(self, [(item, before, after)]))

    def apply_style_to_selection(self, **changes) -> bool:
        """Cambia color, grosor, opacidad o tamano de letra de lo seleccionado."""
        items = self.selected_items()
        if not items:
            return False
        payload: list[tuple[object, Annotation, Annotation]] = []
        for item in items:
            before = item.ann.copy()
            for key, value in changes.items():
                if key == "color" and item.ann.kind is Kind.HIGHLIGHT and value is None:
                    continue
                setattr(item.ann, key, value)
            after = item.ann.copy()
            if before != after:
                item.prepareGeometryChange()
                item.apply_model()
                item.update()
                payload.append((item, before, after))
        if not payload:
            return False
        command = ChangeAnnotationsCommand(self, payload, tr("cmd_style"))
        self.undo_stack.push(command)
        return True

    def annotations(self) -> Sequence[Annotation]:
        return self.store.items

    def annotation_count(self) -> int:
        return len(self.store)

    # ------------------------------------------------------------------ busqueda
    def clear_search(self) -> None:
        for item in self._search_items:
            if item.scene() is not None:
                item.scene().removeItem(item)
        self._search_items = []
        self._hits = []
        self._hit_index = -1

    def set_search_hits(self, hits: Sequence[SearchHit]) -> None:
        self.clear_search()
        self._hits = list(hits)
        for hit in self._hits:
            if not (0 <= hit.page < len(self._page_items)):
                continue
            page = self._page_items[hit.page]
            x0, y0, x1, y1 = hit.rect
            item = QGraphicsRectItem(QRectF(x0, y0, x1 - x0, y1 - y0), page)
            item.setPen(QPen(Qt.NoPen))
            item.setBrush(QBrush(QColor(255, 210, 0, 110)))
            item.setZValue(5)
            item.setAcceptedMouseButtons(Qt.NoButton)
            self._search_items.append(item)
        if self._hits:
            self.go_to_hit(0)

    @property
    def hit_count(self) -> int:
        return len(self._hits)

    @property
    def hit_index(self) -> int:
        return self._hit_index

    def go_to_hit(self, index: int) -> None:
        if not self._hits:
            return
        index %= len(self._hits)
        for i, item in enumerate(self._search_items):
            item.setBrush(
                QBrush(QColor(255, 140, 0, 160) if i == index else QColor(255, 210, 0, 110))
            )
        self._hit_index = index
        hit = self._hits[index]
        page = self._page_items[hit.page]
        x0, y0, x1, y1 = hit.rect
        center = page.mapToScene(QPointF((x0 + x1) / 2, (y0 + y1) / 2))
        self.centerOn(center)
        self._current_page = hit.page
        self.pageChanged.emit(hit.page)
        self._schedule_render()

    def next_hit(self) -> None:
        if self._hits:
            self.go_to_hit(self._hit_index + 1)

    def previous_hit(self) -> None:
        if self._hits:
            self.go_to_hit(self._hit_index - 1)


def _constrain_angle(origin: QPointF, point: QPointF) -> QPointF:
    """Ajusta el punto al multiplo de 45 grados mas cercano (tecla Mayus)."""
    dx = point.x() - origin.x()
    dy = point.y() - origin.y()
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return point
    angle = math.atan2(dy, dx)
    step = math.pi / 4
    angle = round(angle / step) * step
    length = math.hypot(dx, dy)
    return QPointF(origin.x() + length * math.cos(angle), origin.y() + length * math.sin(angle))


__all__ = ["PdfView", "Tool", "PageItem", "AnnotationScene"]
