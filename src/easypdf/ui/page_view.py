"""Vista del documento: paginas, herramientas de anotacion y navegacion."""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
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
    QGraphicsView,
)

from ..config import MAX_ZOOM, MIN_ZOOM
from ..document import PdfDocument, SearchHit
from ..model import Annotation, AnnotationStore, Kind
from .commands import (
    AddAnnotationCommand,
    ChangeAnnotationsCommand,
    DeleteAnnotationsCommand,
)
from .items import AnnotationItemMixin, TextItem, create_item

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

    @property
    def kind(self) -> Kind | None:
        mapping = {
            Tool.RECT: Kind.RECT,
            Tool.HIGHLIGHT: Kind.HIGHLIGHT,
            Tool.LINE: Kind.LINE,
            Tool.ARROW: Kind.ARROW,
            Tool.TEXT: Kind.TEXT,
            Tool.INK: Kind.INK,
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
        self._draft_item = None
        self._draft_origin = QPointF()
        self._draft_page = 0
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
        y = PAGE_MARGIN
        max_width = max((w for w, _ in doc.page_sizes()), default=0.0)
        for index, (width, height) in enumerate(doc.page_sizes()):
            item = PageItem(index, width, height)
            item.setPos(PAGE_MARGIN + (max_width - width) / 2.0, y)
            self._scene.addItem(item)
            self._page_items.append(item)
            y += height + PAGE_GAP
        total_height = y - PAGE_GAP + PAGE_MARGIN
        self._scene.setSceneRect(
            0, 0, max_width + 2 * PAGE_MARGIN, max(total_height, 1.0)
        )
        self.verticalScrollBar().setValue(0)
        self.apply_fit()
        self._render_visible_pages()
        self.pageChanged.emit(0)

    @property
    def page_count(self) -> int:
        return len(self._page_items)

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
        if tool is Tool.PAN:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().setCursor(Qt.OpenHandCursor)
        elif tool is Tool.SELECT:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        editable = tool is Tool.SELECT
        for item in self._annotation_items():
            item.setFlag(QGraphicsItem.ItemIsMovable, editable)
            item.setFlag(QGraphicsItem.ItemIsSelectable, editable)
        if not editable:
            self._scene.clearSelection()

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
        )
        if kind in (Kind.LINE, Kind.ARROW):
            ann.p1 = (point.x(), point.y())
            ann.p2 = (point.x(), point.y())
        elif kind is Kind.INK:
            ann.strokes = [[(point.x(), point.y())]]
        else:
            ann.rect = (point.x(), point.y(), point.x(), point.y())
        if kind is Kind.TEXT and ann.fill is None:
            ann.width = 0.0
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
        if ann.kind is Kind.TEXT:
            x0, y0, x1, y1 = ann.normalized_rect()
            if (x1 - x0) < 24 or (y1 - y0) < ann.font_size:
                ann.rect = (x0, y0, x0 + 220.0, y0 + ann.font_size * 1.8)
            item.apply_model()
        if ann.is_empty() and ann.kind is not Kind.TEXT:
            self.detach_item(item)
            return
        item.sync_model()
        self._items[ann.id] = item
        self.undo_stack.push(AddAnnotationCommand(self, ann, item))
        self.set_tool(Tool.SELECT)
        item.setSelected(True)
        if isinstance(item, TextItem):
            item.start_editing()
        self.toolFinished.emit()

    # ------------------------------------------------------------------ raton
    def mousePressEvent(self, event) -> None:
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
            if event.modifiers() & Qt.ShiftModifier:
                side = max(abs(x1 - x0), abs(y1 - y0))
                x1 = x0 + side * (1 if x1 >= x0 else -1)
                y1 = y0 + side * (1 if y1 >= y0 else -1)
            ann.rect = (x0, y0, x1, y1)
        self._draft_item.apply_model()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
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
            self._scene.clearSelection()
            self.set_tool(Tool.SELECT)
            self.toolFinished.emit()
            event.accept()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            focus = self._scene.focusItem()
            if not isinstance(focus, TextItem) or not focus.hasFocus():
                if self.delete_selected():
                    event.accept()
                    return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ edicion
    def delete_selected(self) -> bool:
        items = self.selected_items()
        if not items:
            return False
        self.undo_stack.push(DeleteAnnotationsCommand(self, items))
        return True

    def select_all_annotations(self) -> None:
        for item in self._annotation_items():
            item.setSelected(True)

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
        command = ChangeAnnotationsCommand(self, payload, "Cambiar estilo")
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
