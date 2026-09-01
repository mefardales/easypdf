"""The document view: pages, annotation tools and navigation."""

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
    stroke_touches,
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

PAGE_GAP = 16.0        # gap between pages, in points
PAGE_MARGIN = 16.0     # margin around the document
MAX_RENDER_SCALE = 4.0
KEEP_RENDERED = 8      # rasterised pages kept in memory


class Tool(str, Enum):
    """The pointer's active tool."""

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
    """One page of the PDF. Its local coordinates are PDF points."""

    def __init__(self, index: int, width: float, height: float) -> None:
        super().__init__()
        self.index = index
        self._size = (width, height)
        self._pixmap: QPixmap | None = None
        self._pixmap_scale = 0.0
        self.setFlag(QGraphicsItem.ItemUsesExtendedStyleOption, True)
        # Annotations are children of the page and must not paint outside it:
        # the eraser is white and opaque, so running off the sheet ate into the
        # grey background. What runs off would not print either, so clipping it
        # here is also what makes screen and paper agree.
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
    """Scene that reports when an annotation starts and stops being edited."""

    annotationEdited = Signal(object, object, object)  # item, before, after
    textEditing = Signal(bool)                        # a text is being edited

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
    """Viewer with continuous scrolling and annotation tools."""

    pageChanged = Signal(int)
    zoomChanged = Signal(float)
    modified = Signal()
    toolFinished = Signal()
    eraserSizeChanged = Signal(float)
    noteCreated = Signal(object)
    erased = Signal()          # an eraser pass has finished
    mouseMovedOnPage = Signal(object)   # position within the viewport
    guidesChanged = Signal()            # the rulers need repainting
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
        # The items live in the scene (owned by C++), but the Python reference
        # has to be kept or the collector takes the Python half of the object
        # and it stops being painted by its own class.
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
        # The user's guides, in page coordinates. They belong to the whole
        # document, not to one page: a guide lines the same thing up on every
        # sheet, which is exactly what it is put there for.
        self.rulers_guides: dict[str, list[float]] = {"h": [], "v": []}
        self._guide_drag = None      # ("h"|"v", page, value, index or None)
        self._eraser_size = ERASER_DEFAULT
        # How many times the same thing has been pasted: each paste is shifted
        # a little further so they do not pile up invisibly on each other.
        self._paste_count = 0
        self._erasing = False
        self._erase_item = None
        self._eraser_color = (1.0, 1.0, 1.0)   # white, the colour of paper
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
            "image": None,      # (name, bytes) of the chosen image
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
        """While typing, the text wins: no global shortcuts."""
        self._text_editing = editing
        self.textEditing.emit(editing)

    @property
    def is_editing_text(self) -> bool:
        return self._text_editing

    # ------------------------------------------------------------------ documento
    def set_document(self, doc: PdfDocument | None) -> None:
        """Load (or unload) a document and rebuild the scene."""
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
        """Pick up the notes the PDF already carries so they can be seen and edited.

        They are taken out of the document and moved into the annotation list,
        which is what gets written back on save. That way they are not doubled.
        """
        from .items import NOTE_SIZE

        for page_item, x, y, text in doc.take_notes():
            if not (0 <= page_item < len(self._page_items)):
                continue
            ann = Annotation(
                kind=Kind.NOTE,
                page=page_item,
                rect=(x, y, x + NOTE_SIZE, y + NOTE_SIZE),
                text=text,
                color=(0.98, 0.80, 0.20),
            )
            self.store.add(ann)
            self.attach_item(create_item(ann, self._page_items[page_item]), ann)

    def _build_page_items(self) -> None:
        """Create one item per page and size the scene accordingly."""
        doc = self.document
        if doc is None:
            return
        y = PAGE_MARGIN
        sizes = doc.page_sizes()
        max_width = max((w for w, _ in sizes), default=0.0)
        for index, (width, height) in enumerate(sizes):
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
        for page_item in self._page_items:
            self._scene.removeItem(page_item)
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
        """Insert a blank page (at the end if no position is given)."""
        if self.document is None:
            return
        target = self.document.page_count if index is None else index
        self.undo_stack.push(AddPageCommand(self, target, size))

    def duplicate_page(self, index: int) -> None:
        if self.document is None:
            return
        self.undo_stack.push(AddPageCommand(self, index + 1, duplicate=True))

    def delete_page(self, index: int) -> None:
        if self.document is None or self.document.page_count <= 1:
            return
        self.undo_stack.push(DeletePageCommand(self, index))

    def rotate_page(self, index: int, delta: int) -> None:
        """Rotate a page (delta in clockwise degrees: 90, 180 or -90)."""
        if self.document is None or delta % 360 == 0:
            return
        self.undo_stack.push(RotatePageCommand(self, index, delta))

    def move_page(self, index: int, target: int) -> None:
        if self.document is None or index == target:
            return
        self.undo_stack.push(MovePageCommand(self, index, target))

    def shift_annotation_pages(self, start: int, delta: int) -> None:
        """Move the annotations along when pages are inserted or removed."""
        for ann in self.store:
            if ann.page >= start:
                ann.page += delta

    def items_on_page(self, index: int) -> list:
        return [item for item in self._items.values() if item.ann.page == index]

    @property
    def page_count(self) -> int:
        return len(self._page_items)

    def current_page_item(self):
        """The PageItem of the page being worked on (or None)."""
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
        # Free the memory of pages that are far away.
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
        """The current page is the one filling most of the window."""
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
        """Work the zoom out again for the active fit mode."""
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
        # Leave the top edge of the page right at the top of the visible area.
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
        """Set the cursor of the active tool."""
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
        """A circle the eraser's real size, so you can see what will go."""
        side = max(8, min(128, int(self._eraser_size * self._zoom)))
        pixmap = QPixmap(side + 2, side + 2)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # a double stroke so it shows on a light and on a dark background
        r, g, b = self._eraser_color
        fill = QColor(int(r * 255), int(g * 255), int(b * 255))
        fill.setAlpha(150)
        painter.setBrush(fill)                 # the colour it covers with
        painter.setPen(QPen(QColor(255, 255, 255, 220), 3))
        painter.drawEllipse(1, 1, side, side)
        painter.setPen(QPen(QColor(20, 20, 20, 230), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(1, 1, side, side)
        painter.end()
        return QCursor(pixmap, side // 2, side // 2)

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
            image = style.get("image") or ("", b"")
            ann.image_name, ann.image_data = image[0], image[1]
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
            # The grid is always visible, even if the chosen stroke is 0.
            ann.width = max(0.5, ann.width)
        return ann

    def attach_item(self, item, ann: Annotation) -> None:
        """Hang an item off its page and register it (also used when redoing)."""
        page = self._page_items[ann.page] if 0 <= ann.page < len(self._page_items) else None
        if page is not None:
            item.setParentItem(page)
        elif item.scene() is None:  # pragma: no cover - defensive
            self._scene.addItem(item)
        item.setVisible(True)
        self._items[ann.id] = item

    def place_image(self, name: str, data: bytes, page: int, point: QPointF):
        """Place an image on the given page (in page coordinates)."""
        ann = Annotation(kind=Kind.IMAGE, page=page, image_name=name, image_data=data)
        ann.rect = (point.x(), point.y(), point.x(), point.y())
        item = create_item(ann, self._page_items[page])
        aspect = getattr(item, "aspect", 1.0) or 1.0
        width = min(self._page_items[page].boundingRect().width() * 0.4, 260.0)
        ann.rect = (point.x(), point.y(), point.x() + width, point.y() + width / aspect)
        item.apply_model()
        self._items[ann.id] = item
        self.undo_stack.push(AddAnnotationCommand(self, ann, item))
        item.setSelected(True)
        return item

    def apply_template(self, annotations, first_page: int | None = None) -> int:
        """Add a template's annotations. Returns how many were placed."""
        if self.document is None:
            return 0
        from ..templates import shift_to_page

        start = self.current_page if first_page is None else first_page
        placed = shift_to_page(annotations, start, self.page_count)
        if not placed:
            return 0
        self.undo_stack.beginMacro(tr("cmd_template", count=len(placed)))
        for ann in placed:
            self.add_annotation(ann)
        self.undo_stack.endMacro()
        return len(placed)

    #: Smallest margin when dropping a group of annotations, in PDF points.
    DROP_MARGIN = 24.0

    def insert_annotations(self, annotations, label: str | None = None) -> int:
        """Drop a group of annotations wherever the user is looking.

        This is what the form pieces use: they arrive placed relative to one
        another and here they are moved as a block to the centre of what is on
        screen, without running off the paper. The whole group is one undo step.
        """
        if self.document is None:
            return 0
        pieces = [ann.copy() for ann in annotations]
        if not pieces:
            return 0
        for ann in pieces:
            ann.id = Annotation(kind=ann.kind, page=0).id   # identidad nueva

        page_item = self.current_page
        item = self._page_items[page_item]
        limits = [ann.bounds() for ann in pieces]
        x0 = min(min(b[0], b[2]) for b in limits)
        y0 = min(min(b[1], b[3]) for b in limits)
        width = max(max(b[0], b[2]) for b in limits) - x0
        height = max(max(b[1], b[3]) for b in limits) - y0

        centro = item.mapFromScene(self.mapToScene(self.viewport().rect().center()))
        sheet = item.boundingRect()
        margin = self.DROP_MARGIN
        destino_x = min(max(margin, centro.x() - width / 2),
                        max(margin, sheet.width() - width - margin))
        destino_y = min(max(margin, centro.y() - height / 2),
                        max(margin, sheet.height() - height - margin))

        self._scene.clearSelection()
        self.undo_stack.beginMacro(label or tr("cmd_paste", count=len(pieces)))
        for ann in pieces:
            ann.page = page_item
            move_annotation(ann, destino_x - x0, destino_y - y0)
            self.add_annotation(ann).setSelected(True)
        self.undo_stack.endMacro()
        return len(pieces)

    def add_annotation(self, ann: Annotation, undoable: bool = True):
        """Add an already defined annotation to the document and return its item.

        This is the public way to create annotations without a mouse (scripts,
        tests, or future features such as stamps or signatures).
        """
        if not (0 <= ann.page < len(self._page_items)):
            raise IndexError(f"page {ann.page} does not exist in the document")
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
                # A single click drops the image at a comfortable size.
                aspect = getattr(item, "aspect", 1.0) or 1.0
                page_item = self._page_items[ann.page].boundingRect()
                width = min(page_item.width() * 0.4, 260.0)
                ann.rect = (x0, y0, x0 + width, y0 + width / aspect)
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
            self.noteCreated.emit(item)   # the window asks for the text
        self.toolFinished.emit()

    def _draw_ruler_guides(self, painter) -> None:  # pragma: no cover - drawing
        """Paint the guides pulled out of the rulers."""
        pen = QPen(QColor("#00a3c4"))
        pen.setWidthF(1.0)
        pen.setCosmetic(True)
        guides = self.rulers_guides
        if not (guides["h"] or guides["v"]):
            return
        for item in self._page_items:
            box = item.sceneBoundingRect()
            painter.setPen(pen)
            for y in guides["h"]:
                sy = item.mapToScene(QPointF(0, y)).y()
                painter.drawLine(QPointF(box.left(), sy), QPointF(box.right(), sy))
            for x in guides["v"]:
                sx = item.mapToScene(QPointF(x, 0)).x()
                painter.drawLine(QPointF(sx, box.top()), QPointF(sx, box.bottom()))

        # the one being dragged, dashed so it stands out
        if self._guide_drag is not None:
            orientation, page_item, value, _index = self._guide_drag
            if 0 <= page_item < len(self._page_items):
                item = self._page_items[page_item]
                box = item.sceneBoundingRect()
                drag = QPen(QColor("#00a3c4"))
                drag.setStyle(Qt.DashLine)
                drag.setWidthF(1.0)
                drag.setCosmetic(True)
                painter.setPen(drag)
                if orientation == "h":
                    sy = item.mapToScene(QPointF(0, value)).y()
                    painter.drawLine(QPointF(box.left(), sy), QPointF(box.right(), sy))
                else:
                    sx = item.mapToScene(QPointF(value, 0)).x()
                    painter.drawLine(QPointF(sx, box.top()), QPointF(sx, box.bottom()))

    # ------------------------------------------------------------ the user's guides
    def page_guides(self, page: int = 0) -> dict[str, list[float]]:
        """The document's guides. The page number no longer changes anything:
        they show on every page and align on every page."""
        return self.rulers_guides

    def start_guide(self, orientation: str, value: float) -> None:
        """Start pulling a new guide out of the ruler."""
        page_item = self._current_page
        self._guide_drag = (orientation, page_item, value, None)
        self._guides_changed()

    def grab_guide(self, orientation: str, page_item: int, index: int, value: float) -> None:
        """Grab a guide that already exists in order to move it."""
        self._guide_drag = (orientation, page_item, value, index)
        self._guides_changed()

    def move_guide(self, value: float) -> None:
        if self._guide_drag is None or value is None:
            return
        orientation, page_item, _viejo, index = self._guide_drag
        self._guide_drag = (orientation, page_item, value, index)
        self._guides_changed()

    def drop_guide(self, value) -> None:
        """Drop the guide. Off the page, it goes away."""
        if self._guide_drag is None:
            return
        orientation, page_item, last, index = self._guide_drag
        self._guide_drag = None
        if value is None:
            value = last
        guides = self.page_guides(page_item)[orientation]
        inside = self._guide_inside(page_item, orientation, value)
        if index is None:
            if inside:
                guides.append(float(value))
        elif 0 <= index < len(guides):
            if inside:
                guides[index] = float(value)
            else:
                del guides[index]        # dragged off the margin: it goes
        self._guides_changed()

    def _guide_inside(self, page_item: int, orientation: str, value) -> bool:
        if value is None or not (0 <= page_item < len(self._page_items)):
            return False
        box = self._page_items[page_item].boundingRect()
        limit = box.height() if orientation == "h" else box.width()
        return 0 <= value <= limit

    def guide_at(self, scene_pos):
        """The guide under a scene point, if there is one."""
        margin = 4.0 / max(self._zoom, 1e-6)
        for page_item, item in enumerate(self._page_items):
            local = item.mapFromScene(scene_pos)
            box = item.boundingRect()
            if not box.adjusted(-margin, -margin, margin, margin).contains(local):
                continue
            guides = self.page_guides(page_item)
            for i, y in enumerate(guides["h"]):
                if abs(local.y() - y) <= margin:
                    return ("h", page_item, i, y)
            for i, x in enumerate(guides["v"]):
                if abs(local.x() - x) <= margin:
                    return ("v", page_item, i, x)
        return None

    def clear_all_guides(self) -> None:
        self.rulers_guides = {"h": [], "v": []}
        self._guides_changed()

    def _guides_changed(self) -> None:
        """Repaint the page and tell the rulers."""
        self.viewport().update()
        self.guidesChanged.emit()

    # ----------------------------------------------------------- snap guides
    def show_guides(self, x, y, page) -> None:
        """Mark the guides being snapped to (None = none)."""
        new_ones = (x, y, page)
        if new_ones != self._guides:
            self._guides = new_ones
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
        box = page.sceneBoundingRect()
        lapiz = QPen(QColor("#e91e63"))
        lapiz.setStyle(Qt.DashLine)
        lapiz.setWidthF(1.0 / max(self._zoom, 1e-6))
        lapiz.setCosmetic(True)
        painter.setPen(lapiz)
        if x is not None:
            escena_x = page.mapToScene(QPointF(x, 0)).x()
            painter.drawLine(QPointF(escena_x, box.top()), QPointF(escena_x, box.bottom()))
        if y is not None:
            escena_y = page.mapToScene(QPointF(0, y)).y()
            painter.drawLine(QPointF(box.left(), escena_y), QPointF(box.right(), escena_y))

    # ------------------------------------------------------------------ goma
    @property
    def eraser_size(self) -> float:
        """Diameter of the eraser, in PDF points."""
        return self._eraser_size

    def set_eraser_size(self, size: float) -> None:
        smallest, largest = ERASER_SIZES[0], ERASER_SIZES[-1]
        new_one = max(smallest, min(float(size), largest))
        if new_one != self._eraser_size:
            self._eraser_size = new_one
            self.eraserSizeChanged.emit(new_one)
            self._update_cursor()

    @property
    def eraser_color(self):
        """The colour the eraser covers the document with."""
        return self._eraser_color

    def set_eraser_color(self, rgb) -> None:
        self._eraser_color = tuple(rgb)
        self._update_cursor()

    def step_eraser_size(self, delta: int) -> None:
        """Step to the next or previous size in the list (Ctrl+ / Ctrl-)."""
        current = min(ERASER_SIZES, key=lambda t: abs(t - self._eraser_size))
        position = ERASER_SIZES.index(current) + (1 if delta > 0 else -1)
        position = max(0, min(position, len(ERASER_SIZES) - 1))
        self.set_eraser_size(ERASER_SIZES[position])

    def erase_at(self, page_index: int, point: QPointF) -> bool:
        """Add a point to the stroke the eraser covers the document with."""
        if self._erase_item is None:
            return False
        self._erase_item.append_point(point)
        return True

    def annotations_under(self, erasure: Annotation) -> list:
        """The items the eraser has run over, on its own page."""
        found = []
        for item in self._annotation_items():
            ann = item.ann
            if ann is erasure or ann.page != erasure.page or ann.kind is Kind.ERASE:
                continue
            if stroke_touches(erasure.strokes, erasure.width, ann.bounds()):
                found.append(item)
        return found

    def _finish_erase(self) -> None:
        """Close the eraser pass and remove whatever went under it.

        It really erases: it takes the annotations it runs over with it, and on
        save it also strips the original content it covers. Covering was not
        enough: text painted white can still be selected and copied out of a
        PDF, so anyone rubbing out a confidential figure believed they were
        safe when they were not.

        Until the file is saved it undoes with Ctrl+Z like anything else.
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
        covered = self.annotations_under(item.ann)
        self.undo_stack.beginMacro(tr("cmd_erase"))
        self.undo_stack.push(
            AddAnnotationCommand(self, item.ann, item, tr("cmd_erase"))
        )
        if covered:
            self.undo_stack.push(DeleteAnnotationsCommand(self, covered))
        self.undo_stack.endMacro()
        self.erased.emit()

    # ------------------------------------------------------------------ raton
    def _leave_editing(self, event) -> bool:
        """Close the text or cell being edited when clicking outside it.

        A cell editor is a child of the table, so on a click outside it is the
        editor that loses the focus and the table never finds out: it stayed in
        editing mode forever, and with it DEL, Ctrl+C and Ctrl+V stayed off.

        If the click lands on an empty spot, that first click only leaves the
        box and the element stays selected: that way it can be copied or
        deleted right afterwards, which is what one expects. The next click on
        empty space does drop the selection.

        This is checked here and not with the scene's focusItemChanged: that
        signal also fires while Qt tears the scene down on close, with the
        items half freed, and that used to crash the program.

        Returns True if it keeps the click.
        """
        if not self._text_editing:
            return False
        touched = self._scene.itemAt(
            self.mapToScene(event.position().toPoint()), self.transform()
        )
        being_edited = self._items_being_edited()
        if any(touched is getattr(item, "_editor", None) is not None
               for item in being_edited):
            return False                 # typing carries on in that cell
        self.finish_all_editing()
        if touched is None or not isinstance(touched, AnnotationItemMixin):
            self._scene.clearSelection()
            for item in being_edited:
                item.setSelected(True)
            event.accept()
            return True                  # the click is spent leaving the box
        return False

    def mousePressEvent(self, event) -> None:
        if self._leave_editing(event):
            return
        if (self._tool is Tool.SELECT and event.button() == Qt.LeftButton
                and self._guide_drag is None):
            scene = self.mapToScene(event.position().toPoint())
            found = self.guide_at(scene)
            if found is not None:
                orientation, page_item, index, value = found
                self.grab_guide(orientation, page_item, index, value)
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
                kind=Kind.ERASE,
                page=page.index,
                color=tuple(self._eraser_color),
                width=self._eraser_size,
                opacity=1.0,            # opaque: it has to cover what is under it
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
            orientation, page_item, _v, _i = self._guide_drag
            if 0 <= page_item < len(self._page_items):
                local = self._page_items[page_item].mapFromScene(
                    self.mapToScene(event.position().toPoint())
                )
                self.move_guide(local.y() if orientation == "h" else local.x())
            event.accept()
            return
        if self._erasing and self._erase_item is not None:
            # painting carries on over the page it started on
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
                # The image keeps its ratio while it is being placed.
                aspect = getattr(self._draft_item, "aspect", 1.0) or 1.0
                width = abs(x1 - x0)
                height = width / aspect
                x1 = x0 + width * (1 if x1 >= x0 else -1)
                y1 = y0 + height * (1 if y1 >= y0 else -1)
            elif event.modifiers() & Qt.ShiftModifier:
                side = max(abs(x1 - x0), abs(y1 - y0))
                x1 = x0 + side * (1 if x1 >= x0 else -1)
                y1 = y0 + side * (1 if y1 >= y0 else -1)
            ann.rect = (x0, y0, x1, y1)
        self._draft_item.apply_model()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._guide_drag is not None:
            orientation, page_item, value, _i = self._guide_drag
            if 0 <= page_item < len(self._page_items):
                local = self._page_items[page_item].mapFromScene(
                    self.mapToScene(event.position().toPoint())
                )
                value = local.y() if orientation == "h" else local.x()
            self.drop_guide(value)
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

    def event(self, event) -> bool:
        """Take the Tab key before anyone else does.

        Tab reaches neither keyPressEvent nor the table: first the widget uses
        it to move the focus to the next control, and then the scene to move it
        to the next item. That is why Tab between cells, which the help has
        always promised, never worked.
        """
        if self._is_tab_key(event) and self._tab_between_cells(event):
            return True
        return super().event(event)

    def viewportEvent(self, event) -> bool:
        # Depending on where the key press comes from it reaches the view or
        # its viewport, so Tab is looked for in both places.
        if self._is_tab_key(event) and self._tab_between_cells(event):
            return True
        return super().viewportEvent(event)

    @staticmethod
    def _is_tab_key(event) -> bool:
        from PySide6.QtCore import QEvent

        return (event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key_Tab, Qt.Key_Backtab))

    def _tab_between_cells(self, event) -> bool:
        """Move to the next (or previous) cell if one is being edited."""
        focused = self._scene.focusItem()
        table = focused.parentItem() if focused is not None else None
        if table is None or not getattr(table, "is_editing", False):
            return False
        table.keyPressEvent(event)
        return bool(event.isAccepted())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            if self._draft_item is not None:
                self.detach_item(self._draft_item)
                self._draft_item = None
            # Esc leaves the box and goes back to the select tool, but does
            # NOT drop the selection: the usual thing after finishing something
            # is to copy it, move it or delete it, and before there was nothing
            # left to apply that to. To deselect you click on an empty spot,
            # like in any other program.
            being_edited = self._items_being_edited()
            # Close any open editors: otherwise a cell editor stays alive with
            # the focus and DEL then never reaches the table.
            self.finish_all_editing()
            for item in being_edited:
                item.setSelected(True)
            self.clear_search()
            self.set_tool(Tool.SELECT)
            self.toolFinished.emit()
            event.accept()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            focus = self._scene.focusItem()
            editing = self._text_editing or isinstance(focus, QGraphicsTextItem)
            if not editing and (not isinstance(focus, TextItem) or not focus.hasFocus()):
                if self.delete_selected():
                    event.accept()
                    return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ edicion
    def _items_being_edited(self) -> list:
        """The items with a text or a cell open right now."""
        return [
            item for item in self._annotation_items()
            if getattr(item, "is_editing", False) or getattr(item, "_editing", False)
        ]

    def finish_all_editing(self) -> None:
        """Close any cell or text that is being edited."""
        for item in self._annotation_items():
            finish = getattr(item, "finish_editing", None)
            if callable(finish) and getattr(item, "is_editing", False):
                finish()
            stop_it = getattr(item, "stop_editing", None)
            if callable(stop_it) and getattr(item, "_editing", False):
                stop_it()
        focused = self._scene.focusItem()
        if isinstance(focused, QGraphicsTextItem):
            focused.clearFocus()

    def delete_selected(self) -> bool:
        items = self.selected_items()
        if not items:
            return False
        self.undo_stack.push(DeleteAnnotationsCommand(self, items))
        return True

    def select_all_annotations(self) -> None:
        for item in self._annotation_items():
            item.setSelected(True)

    # -------------------------------------------------------- copy and paste
    #: How far a paste is offset from its original, in PDF points. Just enough
    #: to see it on top and be able to drag it, as in any editor.
    PASTE_OFFSET = 12.0

    def copy_selected(self) -> int:
        """Copy the selection to the clipboard. Returns how many were copied."""
        from .clipboard import copy_annotations

        items = self.selected_items()
        if not items:
            return 0
        how_many = copy_annotations(item.ann for item in items)
        if how_many:
            self._paste_count = 0        # the first paste goes alongside
        return how_many

    def cut_selected(self) -> int:
        """Copy and remove. The deletion undoes like any other."""
        how_many = self.copy_selected()
        if how_many:
            self.delete_selected()
        return how_many

    def paste_clipboard(self, page: int | None = None) -> int:
        """Paste into the given page (by default, the one on screen)."""
        from ..templates import shift_to_page
        from .clipboard import clipboard_annotations

        if self.document is None:
            return 0
        copied = clipboard_annotations()
        if not copied:
            return 0
        target = self.current_page if page is None else page
        # shift_to_page gives every copy a new identity and keeps the distance
        # between pages, so what was copied from several pages can be pasted.
        placed = shift_to_page(copied, target, self.page_count)
        if not placed:
            return 0
        self._paste_count += 1
        offset = self.PASTE_OFFSET * self._paste_count
        for ann in placed:
            move_annotation(ann, offset, offset)
        self._scene.clearSelection()
        self.undo_stack.beginMacro(tr("cmd_paste", count=len(placed)))
        for ann in placed:
            item = self.add_annotation(ann)
            item.setSelected(True)       # queda listo para moverlo
        self.undo_stack.endMacro()
        return len(placed)

    def _on_annotation_edited(self, item, before, after) -> None:
        self.undo_stack.push(ChangeAnnotationsCommand(self, [(item, before, after)]))

    def apply_style_to_selection(self, **changes) -> bool:
        """Change colour, width, opacity or font size of the selection."""
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
    """Snap the point to the nearest multiple of 45 degrees (the Shift key)."""
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
