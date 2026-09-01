"""Graphics items that stand for the annotations on the page.

Every item lives inside a ``PageItem`` and works directly in **PDF points**,
so there are no zoom conversions: what is drawn is exactly what is written to
the file afterwards.
"""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QStyle,
)

from ..model import (
    SNAP_PIXELS,
    Align,
    Annotation,
    Font,
    Kind,
    arrow_head,
    arrow_line_end,
    snap_offset,
)

#: Size of the resize handle, in screen pixels.
HANDLE_PX = 9.0
MIN_SIZE = 4.0
SELECTION_COLOR = QColor("#1565c0")

_CURSORS: dict[str, Qt.CursorShape] = {
    "tl": Qt.SizeFDiagCursor,
    "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor,
    "bl": Qt.SizeBDiagCursor,
    "t": Qt.SizeVerCursor,
    "b": Qt.SizeVerCursor,
    "l": Qt.SizeHorCursor,
    "r": Qt.SizeHorCursor,
    "p1": Qt.SizeAllCursor,
    "p2": Qt.SizeAllCursor,
    "w": Qt.SizeHorCursor,
}


def annotation_font(ann: Annotation) -> QFont:
    """The QFont matching the style stored in the annotation."""
    font = QFont(Font(ann.font).qt_family)
    font.setPixelSize(max(1, int(round(ann.font_size))))
    font.setBold(bool(ann.bold))
    font.setItalic(bool(ann.italic))
    return font


ALIGN_FLAGS = {
    Align.LEFT: Qt.AlignLeft,
    Align.CENTER: Qt.AlignHCenter,
    Align.RIGHT: Qt.AlignRight,
}


def qcolor(rgb: tuple[float, float, float] | None, opacity: float = 1.0) -> QColor:
    """Turn a model colour (0..1) into a QColor."""
    if rgb is None:
        return QColor(Qt.transparent)
    color = QColor.fromRgbF(
        max(0.0, min(1.0, rgb[0])),
        max(0.0, min(1.0, rgb[1])),
        max(0.0, min(1.0, rgb[2])),
    )
    color.setAlphaF(max(0.0, min(1.0, opacity)))
    return color


def to_rgb(color: QColor) -> tuple[float, float, float]:
    return (color.redF(), color.greenF(), color.blueF())


class AnnotationItemMixin:
    """Comportamiento comun: seleccion, tiradores y sincronizacion del modelo."""

    ann: Annotation

    def _init_common(self, ann: Annotation) -> None:
        self.ann = ann
        # While the model is being poured into the item, the position changes
        # Qt emits must not write half-finished data back to the model.
        self._applying = False
        self._active_handle: str | None = None
        self._drag_origin = QPointF()
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    # -- utilidades ------------------------------------------------------
    def view_scale(self) -> float:
        scene = self.scene()
        if scene is not None:
            views = scene.views()
            if views:
                return max(0.05, abs(views[0].transform().m11()))
        return 1.0

    def handle_size(self) -> float:
        return HANDLE_PX / self.view_scale()

    def handles(self) -> dict[str, QPointF]:
        """Handles in the item's own coordinates."""
        return {}

    def handle_at(self, pos: QPointF) -> str | None:
        half = self.handle_size() / 2.0
        for name, point in self.handles().items():
            if QRectF(point.x() - half, point.y() - half, half * 2, half * 2).contains(pos):
                return name
        return None

    def resize_to(self, handle: str, pos: QPointF) -> None:  # pragma: no cover - UI
        """Apply a handle drag (local coordinates)."""

    def paint_handles(self, painter: QPainter) -> None:
        handles = self.handles()
        if not handles:
            return
        size = self.handle_size()
        pen = QPen(SELECTION_COLOR)
        pen.setWidthF(1.2 / self.view_scale())
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor("#ffffff")))
        for point in handles.values():
            painter.drawRect(
                QRectF(point.x() - size / 2, point.y() - size / 2, size, size)
            )

    def paint_selection(self, painter: QPainter, rect: QRectF) -> None:
        pen = QPen(SELECTION_COLOR)
        pen.setStyle(Qt.DashLine)
        pen.setWidthF(1.0 / self.view_scale())
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

    # -- modelo ----------------------------------------------------------
    def apply_model(self) -> None:
        """Pour the model into the item (model -> screen)."""
        self._applying = True
        try:
            self._apply_model()
        finally:
            self._applying = False

    def sync_model(self) -> None:
        """Pour the item into the model (screen -> model)."""
        if getattr(self, "_applying", False):
            return
        self._sync_model()

    def _apply_model(self) -> None:  # pragma: no cover - each item implements it
        """Geometry and style of the item, taken from ``self.ann``."""

    def _sync_model(self) -> None:  # pragma: no cover - each item implements it
        """Update ``self.ann`` with the item's current geometry."""

    def notify_scene(self, event: str) -> None:
        scene = self.scene()
        handler = getattr(scene, event, None)
        if callable(handler):
            handler(self)

    # -- eventos ---------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        self._active_handle = None
        if self.isSelected() and event.button() == Qt.LeftButton:
            handle = self.handle_at(event.pos())
            if handle:
                self._active_handle = handle
                self.notify_scene("begin_edit")
                event.accept()
                return
        self.notify_scene("begin_edit")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._active_handle:
            self.prepareGeometryChange()
            self.resize_to(self._active_handle, event.pos())
            self.sync_model()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._active_handle:
            self._active_handle = None
            self.sync_model()
            self.notify_scene("end_edit")
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.sync_model()
        self.notify_scene("end_edit")

    def hoverMoveEvent(self, event) -> None:
        cursor = Qt.SizeAllCursor
        if self.isSelected():
            handle = self.handle_at(event.pos())
            if handle:
                cursor = _CURSORS.get(handle, Qt.SizeAllCursor)
        self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            value = self._snap(value)
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.sync_model()
        return super().itemChange(change, value)

    # -- alignment -------------------------------------------------------
    def snap_candidates(self) -> tuple[list[float], list[float]]:
        """Lines to align against: the page and the other annotations."""
        page_item = self.parentItem()
        if page_item is None:
            return ([], [])
        box = page_item.boundingRect()
        # edges and centre of the sheet
        xs = [box.left(), box.center().x(), box.right()]
        ys = [box.top(), box.center().y(), box.bottom()]
        for other in page_item.childItems():
            if other is self or not isinstance(other, AnnotationItemMixin):
                continue
            x0, y0, x1, y1 = other.ann.bounds()
            xs += [x0, (x0 + x1) / 2.0, x1]
            ys += [y0, (y0 + y1) / 2.0, y1]
        # and the guides the user has pulled out of the rulers, which is
        # exactly what they put them there for
        view = self._view()
        if view is not None and hasattr(view, "page_guides"):
            own = view.page_guides(self.ann.page)
            xs += list(own["v"])
            ys += list(own["h"])
        return (xs, ys)

    def _snap(self, new_pos):
        """Adjust the proposed position so it lines up with a guide.

        It only acts while the user is dragging with the mouse. Otherwise it
        would also fire when creating or loading annotations, and would leave
        guides painted on the page with nobody moving anything.
        """
        scene = self.scene()
        if scene is None or scene.mouseGrabberItem() is not self:
            return new_pos
        return self.compute_snap(new_pos)

    def compute_snap(self, new_pos):
        """The snap calculation itself, without checking for a drag in progress."""
        view = self._view()
        if view is None or not getattr(view, "snap_enabled", False):
            return new_pos
        scale = max(view.transform().m11(), 1e-6)
        threshold = SNAP_PIXELS / scale

        # the edges are worked out on the model, which is always in page
        # coordinates whatever the kind of annotation
        dx = new_pos.x() - self.pos().x()
        dy = new_pos.y() - self.pos().y()
        x0, y0, x1, y1 = self.ann.bounds()
        x0, x1, y0, y1 = x0 + dx, x1 + dx, y0 + dy, y1 + dy

        xs, ys = self.snap_candidates()
        offset_x, guide_x = snap_offset([x0, (x0 + x1) / 2.0, x1], xs, threshold)
        offset_y, guide_y = snap_offset([y0, (y0 + y1) / 2.0, y1], ys, threshold)
        view.show_guides(guide_x, guide_y, self.parentItem())
        return QPointF(new_pos.x() + offset_x, new_pos.y() + offset_y)

    def _view(self):
        scene = self.scene()
        if scene is None:
            return None
        vistas = scene.views()
        return vistas[0] if vistas else None


class RectItem(AnnotationItemMixin, QGraphicsRectItem):
    """Cuadro o resaltado."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._init_common(ann)
        self.apply_model()

    # -- modelo ----------------------------------------------------------
    def _apply_model(self) -> None:
        ann = self.ann
        x0, y0, x1, y1 = ann.normalized_rect()
        self.setPos(x0, y0)
        self.setRect(0, 0, max(MIN_SIZE, x1 - x0), max(MIN_SIZE, y1 - y0))
        if ann.kind is Kind.HIGHLIGHT:
            fill = qcolor(ann.color, 0.45)
            self.setBrush(QBrush(fill))
            self.setPen(QPen(Qt.NoPen))
        else:
            pen = QPen(qcolor(ann.color))
            pen.setWidthF(max(0.1, ann.width))
            pen.setJoinStyle(Qt.MiterJoin)
            self.setPen(pen)
            self.setBrush(QBrush(qcolor(ann.fill)) if ann.fill else QBrush(Qt.NoBrush))
        self.setOpacity(ann.opacity if ann.kind is not Kind.HIGHLIGHT else 1.0)

    def _sync_model(self) -> None:
        rect = self.rect()
        origin = self.pos()
        self.ann.rect = (
            origin.x() + rect.x(),
            origin.y() + rect.y(),
            origin.x() + rect.x() + rect.width(),
            origin.y() + rect.y() + rect.height(),
        )

    # -- geometria -------------------------------------------------------
    def handles(self) -> dict[str, QPointF]:
        r = self.rect()
        return {
            "tl": r.topLeft(),
            "tr": r.topRight(),
            "bl": r.bottomLeft(),
            "br": r.bottomRight(),
            "t": QPointF(r.center().x(), r.top()),
            "b": QPointF(r.center().x(), r.bottom()),
            "l": QPointF(r.left(), r.center().y()),
            "r": QPointF(r.right(), r.center().y()),
        }

    def resize_to(self, handle: str, pos: QPointF) -> None:
        r = QRectF(self.rect())
        if "l" in handle:
            r.setLeft(pos.x())
        if "r" in handle:
            r.setRight(pos.x())
        if "t" in handle:
            r.setTop(pos.y())
        if "b" in handle:
            r.setBottom(pos.y())
        r = r.normalized()
        if r.width() < MIN_SIZE:
            r.setWidth(MIN_SIZE)
        if r.height() < MIN_SIZE:
            r.setHeight(MIN_SIZE)
        # The item is moved so the local rectangle starts at (0, 0).
        self.setPos(self.pos() + r.topLeft())
        self.setRect(0, 0, r.width(), r.height())

    def boundingRect(self) -> QRectF:
        margin = max(self.pen().widthF(), self.handle_size()) + 2.0
        return self.rect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        margin = self.handle_size()
        path.addRect(self.rect().adjusted(-margin, -margin, margin, margin))
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        option.state &= ~QStyle.State_Selected  # the default frame is not wanted
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())
        if self.isSelected():
            self.paint_selection(painter, self.rect())
            self.paint_handles(painter)


class LineItem(AnnotationItemMixin, QGraphicsLineItem):
    """Straight line, with or without an arrow head."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._init_common(ann)
        self.apply_model()

    def _apply_model(self) -> None:
        ann = self.ann
        self.setPos(0, 0)
        self.setLine(QLineF(QPointF(*ann.p1), QPointF(*ann.p2)))
        pen = QPen(qcolor(ann.color))
        pen.setWidthF(max(0.1, ann.width))
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
        self.setOpacity(ann.opacity)

    def _sync_model(self) -> None:
        line = self.line()
        offset = self.pos()
        self.ann.p1 = (line.x1() + offset.x(), line.y1() + offset.y())
        self.ann.p2 = (line.x2() + offset.x(), line.y2() + offset.y())

    def handles(self) -> dict[str, QPointF]:
        line = self.line()
        return {"p1": line.p1(), "p2": line.p2()}

    def resize_to(self, handle: str, pos: QPointF) -> None:
        line = QLineF(self.line())
        if handle == "p1":
            line.setP1(pos)
        else:
            line.setP2(pos)
        self.setLine(line)

    def _arrow_points(self):
        """Arrow head, with the same geometry that goes into the PDF."""
        line = self.line()
        p1 = (line.x1(), line.y1())
        p2 = (line.x2(), line.y2())
        _base, tip, left, right = arrow_head(p1, p2, self.ann.width)
        polygon = QPolygonF([QPointF(*tip), QPointF(*left), QPointF(*right)])
        return polygon, QPointF(*arrow_line_end(p1, p2, self.ann.width))

    def boundingRect(self) -> QRectF:
        margin = max(self.pen().widthF() * 3, self.handle_size()) + 4.0
        return QRectF(self.line().p1(), self.line().p2()).normalized().adjusted(
            -margin, -margin, margin, margin
        )

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        line = self.line()
        path.moveTo(line.p1())
        path.lineTo(line.p2())
        stroker_width = max(self.pen().widthF(), self.handle_size())
        pen = QPen(Qt.black, stroker_width)
        from PySide6.QtGui import QPainterPathStroker

        stroker = QPainterPathStroker(pen)
        result = stroker.createStroke(path)
        for point in self.handles().values():
            size = self.handle_size()
            result.addRect(
                QRectF(point.x() - size / 2, point.y() - size / 2, size, size)
            )
        return result

    def paint(self, painter: QPainter, option, widget=None) -> None:
        option.state &= ~QStyle.State_Selected
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        if self.ann.kind is Kind.ARROW:
            polygon, end = self._arrow_points()
            # The stroke ends inside the head so it does not poke out in front.
            painter.drawLine(QLineF(self.line().p1(), end))
            painter.setPen(QPen(Qt.NoPen))
            painter.setBrush(QBrush(qcolor(self.ann.color)))
            painter.drawPolygon(polygon)
        else:
            painter.drawLine(self.line())
        if self.isSelected():
            self.paint_handles(painter)


class InkItem(AnnotationItemMixin, QGraphicsPathItem):
    """Trazo a mano alzada."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._init_common(ann)
        self.apply_model()

    def _apply_model(self) -> None:
        ann = self.ann
        self.setPos(0, 0)
        # A copy of the strokes as the model holds them: while dragging, the
        # offset lives in the item position and is added on top of this base.
        self._base = [list(stroke) for stroke in ann.strokes]
        path = QPainterPath()
        for stroke in ann.strokes:
            if not stroke:
                continue
            path.moveTo(QPointF(*stroke[0]))
            for point in stroke[1:]:
                path.lineTo(QPointF(*point))
        self.setPath(path)
        pen = QPen(qcolor(ann.color))
        pen.setWidthF(max(0.1, ann.width))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setOpacity(ann.opacity)

    def append_point(self, point: QPointF, new_stroke: bool = False) -> None:
        """Add a point to the current stroke while drawing."""
        if new_stroke or not self.ann.strokes:
            self.ann.strokes.append([])
        self.ann.strokes[-1].append((point.x(), point.y()))
        self.prepareGeometryChange()
        self.apply_model()

    def _sync_model(self) -> None:
        # setPos() is never touched here: this is called from itemChange while
        # Qt is dragging the item, and moving the position mid-drag sent the
        # drawing flying off the screen.
        offset = self.pos()
        base = getattr(self, "_base", None) or self.ann.strokes
        self.ann.strokes = [
            [(x + offset.x(), y + offset.y()) for x, y in stroke] for stroke in base
        ]

    def boundingRect(self) -> QRectF:
        # The selection box is drawn right on the edge of the stroke, so that
        # margin has to be declared too or dragging leaves a trail.
        margin = self.pen().widthF() / 2.0 + 2.0 / self.view_scale()
        return self.path().boundingRect().adjusted(-margin, -margin, margin, margin)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        option.state &= ~QStyle.State_Selected
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        if self.isSelected():
            self.paint_selection(painter, self.path().boundingRect())


class TextItem(AnnotationItemMixin, QGraphicsTextItem):
    """Text box that can be edited on screen."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._init_common(ann)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.document().contentsChanged.connect(self._on_text_changed)
        self._editing = False
        self.apply_model()

    # -- modelo ----------------------------------------------------------
    def _apply_model(self) -> None:
        ann = self.ann
        x0, y0, x1, y1 = ann.normalized_rect()
        self.setPos(x0, y0)
        self.setFont(annotation_font(ann))
        self.setDefaultTextColor(qcolor(ann.color))
        options = self.document().defaultTextOption()
        options.setAlignment(ALIGN_FLAGS.get(Align(ann.align), Qt.AlignLeft))
        self.document().setDefaultTextOption(options)
        width = max(20.0, x1 - x0)
        self.setTextWidth(width)
        if self.toPlainText() != ann.text:
            blocked = self.document().blockSignals(True)
            self.setPlainText(ann.text)
            self.document().blockSignals(blocked)
        self.setOpacity(ann.opacity)

    def content_rect(self) -> QRectF:
        """The text box rectangle, without the selection margin."""
        return QGraphicsTextItem.boundingRect(self)

    def boundingRect(self) -> QRectF:
        """The area to repaint: the box plus its border and handles.

        QGraphicsTextItem only declares the text rectangle, but the width
        handle is drawn centred on the right side and sticks half way out.
        Without this margin, dragging the box left that half unpainted and a
        blue trail behind it.
        """
        margin = max(self.ann.width, self.handle_size()) + 2.0
        return self.content_rect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        margin = self.handle_size()
        path.addRect(self.content_rect().adjusted(-margin, -margin, margin, margin))
        return path

    def _sync_model(self) -> None:
        origin = self.pos()
        rect = self.content_rect()
        self.ann.text = self.toPlainText()
        self.ann.rect = (
            origin.x(),
            origin.y(),
            origin.x() + max(self.textWidth(), rect.width()),
            origin.y() + rect.height(),
        )

    def _on_text_changed(self) -> None:
        self.prepareGeometryChange()
        self.sync_model()
        self.update()

    # -- edicion ---------------------------------------------------------
    def start_editing(self) -> None:
        self._editing = True
        self.notify_scene("begin_edit")
        self.notify_scene("text_editing_started")
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFocus(Qt.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.setTextCursor(cursor)

    def stop_editing(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.sync_model()
        self.notify_scene("end_edit")
        self.notify_scene("text_editing_finished")

    def mouseDoubleClickEvent(self, event) -> None:
        self.start_editing()
        event.accept()

    def focusOutEvent(self, event) -> None:
        self.stop_editing()
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._editing and event.key() == Qt.Key_Escape:
            self.stop_editing()
            event.accept()
            return
        super().keyPressEvent(event)

    # -- geometria -------------------------------------------------------
    def handles(self) -> dict[str, QPointF]:
        if self._editing:
            return {}
        rect = self.content_rect()
        return {"w": QPointF(rect.right(), rect.center().y())}

    def resize_to(self, handle: str, pos: QPointF) -> None:
        if handle == "w":
            self.setTextWidth(max(24.0, pos.x()))

    def paint(self, painter: QPainter, option, widget=None) -> None:
        rect = self.content_rect()
        ann = self.ann
        if ann.fill:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(qcolor(ann.fill)))
            painter.drawRect(rect)
        if ann.width > 0:
            pen = QPen(qcolor(ann.color))
            pen.setWidthF(ann.width)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)
        if self.isSelected() or self._editing:
            self.paint_selection(painter, rect)
            self.paint_handles(painter)
        elif ann.width <= 0 and not ann.fill:
            # A faint guide to find the borderless box (it is not printed).
            pen = QPen(QColor(0, 0, 0, 40))
            pen.setStyle(Qt.DotLine)
            pen.setWidthF(0.8 / self.view_scale())
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)


class ImageItem(AnnotationItemMixin, QGraphicsRectItem):
    """Image placed on top of the page."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._init_common(ann)
        self.apply_model()

    # -- modelo ----------------------------------------------------------
    def _apply_model(self) -> None:
        ann = self.ann
        x0, y0, x1, y1 = ann.normalized_rect()
        self.setPos(x0, y0)
        self.setRect(0, 0, max(MIN_SIZE, x1 - x0), max(MIN_SIZE, y1 - y0))
        if self._pixmap.isNull() and ann.image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(ann.image_data)
            self._pixmap = pixmap
        self.setOpacity(ann.opacity)

    def _sync_model(self) -> None:
        rect = self.rect()
        origin = self.pos()
        self.ann.rect = (
            origin.x() + rect.x(),
            origin.y() + rect.y(),
            origin.x() + rect.x() + rect.width(),
            origin.y() + rect.y() + rect.height(),
        )

    @property
    def aspect(self) -> float:
        """Width to height ratio of the original image."""
        if self._pixmap.isNull() or self._pixmap.height() == 0:
            return 1.0
        return self._pixmap.width() / self._pixmap.height()

    # -- geometria -------------------------------------------------------
    def handles(self) -> dict[str, QPointF]:
        r = self.rect()
        return {
            "tl": r.topLeft(), "tr": r.topRight(),
            "bl": r.bottomLeft(), "br": r.bottomRight(),
            "t": QPointF(r.center().x(), r.top()),
            "b": QPointF(r.center().x(), r.bottom()),
            "l": QPointF(r.left(), r.center().y()),
            "r": QPointF(r.right(), r.center().y()),
        }

    def resize_to(self, handle: str, pos: QPointF) -> None:
        r = QRectF(self.rect())
        if "l" in handle:
            r.setLeft(pos.x())
        if "r" in handle:
            r.setRight(pos.x())
        if "t" in handle:
            r.setTop(pos.y())
        if "b" in handle:
            r.setBottom(pos.y())
        r = r.normalized()
        if r.width() < MIN_SIZE:
            r.setWidth(MIN_SIZE)
        if r.height() < MIN_SIZE:
            r.setHeight(MIN_SIZE)
        # Corners keep the ratio; the sides stretch freely.
        if handle in ("tl", "tr", "bl", "br") and self.aspect > 0:
            height = r.width() / self.aspect
            if "t" in handle:
                r.setTop(r.bottom() - height)
            else:
                r.setHeight(height)
        self.setPos(self.pos() + r.topLeft())
        self.setRect(0, 0, r.width(), r.height())

    def boundingRect(self) -> QRectF:
        margin = self.handle_size() + 2.0
        return self.rect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        option.state &= ~QStyle.State_Selected
        rect = self.rect()
        if self._pixmap.isNull():
            painter.setPen(QPen(QColor(0, 0, 0, 90)))
            painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
            painter.drawRect(rect)
        else:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))
        if self.isSelected():
            self.paint_selection(painter, rect)
            self.paint_handles(painter)


#: Padding of the text inside a cell, in PDF points. Painting, the editor and
#: what goes into the PDF all share it, so the text does not shift when moving
#: from one to the next.
CELL_PADDING = 2.5


class TableItem(AnnotationItemMixin, QGraphicsRectItem):
    """Table: a grid of rows and columns with text in the cells."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        # A long table takes milliseconds to draw (dozens of lines plus the
        # text of every cell), and Qt repaints it on every mouse move. With
        # the cache, dragging moves the image already drawn and only redraws
        # it when something really changes.
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self._init_common(ann)
        self._editor: QGraphicsTextItem | None = None
        self._editing_cell = -1
        self.apply_model()

    # -- modelo ----------------------------------------------------------
    def _apply_model(self) -> None:
        ann = self.ann
        x0, y0, x1, y1 = ann.normalized_rect()
        self.setPos(x0, y0)
        self.setRect(0, 0, max(MIN_SIZE, x1 - x0), max(MIN_SIZE, y1 - y0))
        pen = QPen(qcolor(ann.color))
        pen.setWidthF(max(0.1, ann.width))
        pen.setJoinStyle(Qt.MiterJoin)
        self.setPen(pen)
        self.setBrush(QBrush(qcolor(ann.fill)) if ann.fill else QBrush(Qt.NoBrush))
        self.setOpacity(ann.opacity)

    def _sync_model(self) -> None:
        rect = self.rect()
        origin = self.pos()
        self.ann.rect = (
            origin.x() + rect.x(),
            origin.y() + rect.y(),
            origin.x() + rect.x() + rect.width(),
            origin.y() + rect.y() + rect.height(),
        )

    # -- geometria -------------------------------------------------------
    def handles(self) -> dict[str, QPointF]:
        r = self.rect()
        return {
            "tl": r.topLeft(), "tr": r.topRight(),
            "bl": r.bottomLeft(), "br": r.bottomRight(),
            "t": QPointF(r.center().x(), r.top()),
            "b": QPointF(r.center().x(), r.bottom()),
            "l": QPointF(r.left(), r.center().y()),
            "r": QPointF(r.right(), r.center().y()),
        }

    def resize_to(self, handle: str, pos: QPointF) -> None:
        r = QRectF(self.rect())
        if "l" in handle:
            r.setLeft(pos.x())
        if "r" in handle:
            r.setRight(pos.x())
        if "t" in handle:
            r.setTop(pos.y())
        if "b" in handle:
            r.setBottom(pos.y())
        r = r.normalized()
        minimo = MIN_SIZE * max(1, self.ann.cols)
        if r.width() < minimo:
            r.setWidth(minimo)
        minimo = MIN_SIZE * max(1, self.ann.rows)
        if r.height() < minimo:
            r.setHeight(minimo)
        self.setPos(self.pos() + r.topLeft())
        self.setRect(0, 0, r.width(), r.height())
        self.finish_editing()

    def boundingRect(self) -> QRectF:
        margin = max(self.pen().widthF(), self.handle_size()) + 2.0
        return self.rect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        margin = self.handle_size()
        path.addRect(self.rect().adjusted(-margin, -margin, margin, margin))
        return path

    # -- cells -----------------------------------------------------------
    def _cached_font(self) -> QFont:
        """The table font, rebuilt only when its style changes."""
        ann = self.ann
        key = (ann.font, ann.font_size, ann.bold, ann.italic)
        if getattr(self, "_font_key", None) != key:
            self._font_cache = annotation_font(ann)
            self._font_key = key
        return self._font_cache

    def local_cell_rects(self) -> list[QRectF]:
        """Cell rectangles in the item's own coordinates.

        They are remembered: they used to be recomputed on every repaint, and
        with a table of many rows that showed while dragging it.
        """
        r = self.rect()
        rows, columns = max(1, self.ann.rows), max(1, self.ann.cols)
        key = (r.width(), r.height(), rows, columns)
        if getattr(self, "_rects_clave", None) != key:
            height = r.height() / rows
            width = r.width() / columns
            self._rects_cache = [
                QRectF(c * width, f * height, width, height)
                for f in range(rows)
                for c in range(columns)
            ]
            self._rects_clave = key
        return self._rects_cache

    def cell_at(self, pos: QPointF) -> int:
        for index, cell in enumerate(self.local_cell_rects()):
            if cell.contains(pos):
                return index
        return -1

    def edit_cell(self, index: int) -> None:
        """Open a text editor on top of the given cell."""
        cells = self.local_cell_rects()
        if not (0 <= index < len(cells)):
            return
        self.finish_editing()
        self.notify_scene("begin_edit")
        self.notify_scene("text_editing_started")
        texts = self.ann.normalized_cells()
        editor = QGraphicsTextItem(self)
        editor.setPlainText(texts[index])
        editor.setFont(annotation_font(self.ann))
        editor.setDefaultTextColor(qcolor(self.ann.color))
        cell = cells[index]
        # The same padding and alignment paint() uses: otherwise the text sits
        # in one place while typing and jumps elsewhere when finished.
        alignment = ALIGN_FLAGS.get(Align(self.ann.align), Qt.AlignLeft)
        options = editor.document().defaultTextOption()
        options.setAlignment(alignment)
        editor.document().setDefaultTextOption(options)
        editor.document().setDocumentMargin(0)
        # defaultTextOption does not re-align paragraphs that already exist,
        # and the text is drawn with the block's alignment, not the option's.
        # Replacing the content also creates a new block with the default
        # format, so it is set again every time the content changes.
        self._alignment = alignment
        self._realign()
        editor.document().contentsChanged.connect(self._realign)
        editor.setTextWidth(max(10.0, cell.width() - 2 * CELL_PADDING))
        editor.setPos(cell.topLeft() + QPointF(CELL_PADDING, CELL_PADDING))
        editor.setTextInteractionFlags(Qt.TextEditorInteraction)
        editor.setZValue(self.zValue() + 1)
        editor.setFlag(QGraphicsItem.ItemIsFocusable, True)
        editor.setFocus(Qt.MouseFocusReason)
        cursor = editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        editor.setTextCursor(cursor)
        self._editor = editor
        self._editing_cell = index
        self.update()

    def _realign(self) -> None:
        """Leave the editor's text with the table's alignment.

        A separate cursor is used so the user's own one does not move while
        they type.
        """
        from PySide6.QtGui import QTextCursor

        editor = self._editor
        if editor is None:
            return
        cursor = QTextCursor(editor.document())
        cursor.select(QTextCursor.SelectionType.Document)
        block = cursor.blockFormat()
        if block.alignment() == self._alignment:
            return                       # already right: nothing to touch
        block.setAlignment(self._alignment)
        cursor.mergeBlockFormat(block)

    def finish_editing(self) -> None:
        """Save what was typed and close the editor."""
        editor, index = self._editor, self._editing_cell
        self._editor, self._editing_cell = None, -1
        if editor is None:
            return
        texts = self.ann.normalized_cells()
        try:
            texts[index] = editor.toPlainText()
            editor.setParentItem(None)
            if editor.scene() is not None:
                editor.scene().removeItem(editor)
        except RuntimeError:
            # Qt had already destroyed it (on closing the window, say). What
            # was typed is lost, but the table is left in a sound state.
            pass
        self.ann.cells = texts
        self.update()
        self.notify_scene("end_edit")
        self.notify_scene("text_editing_finished")

    @property
    def is_editing(self) -> bool:
        return self._editor is not None

    # -- eventos ---------------------------------------------------------
    def mouseDoubleClickEvent(self, event) -> None:
        index = self.cell_at(event.pos())
        if index >= 0:
            self.edit_cell(index)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if self.is_editing and event.key() in (Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
            step = {Qt.Key_Tab: 1, Qt.Key_Backtab: -1}.get(event.key(), 0)
            target = self._editing_cell + step
            self.finish_editing()
            if step and 0 <= target < self.ann.cell_count():
                self.edit_cell(target)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        self.finish_editing()
        super().focusOutEvent(event)

    # -- pintado ---------------------------------------------------------
    def paint(self, painter: QPainter, option, widget=None) -> None:
        option.state &= ~QStyle.State_Selected
        rect = self.rect()
        if self.ann.fill:
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.brush())
            painter.drawRect(rect)

        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        rows, columns = max(1, self.ann.rows), max(1, self.ann.cols)
        painter.drawRect(rect)
        for f in range(1, rows):
            y = rect.top() + rect.height() * f / rows
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        for c in range(1, columns):
            x = rect.left() + rect.width() * c / columns
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        painter.setFont(self._cached_font())
        painter.setPen(QPen(qcolor(self.ann.color)))
        bandera = ALIGN_FLAGS.get(Align(self.ann.align), Qt.AlignLeft)
        visible = option.exposedRect if option is not None else None
        for index, (text, cell) in enumerate(
            zip(self.ann.normalized_cells(), self.local_cell_rects())
        ):
            if not text or index == self._editing_cell:
                continue
            # in a long table only the text of what is visible is drawn
            if visible is not None and not visible.isEmpty() and not visible.intersects(cell):
                continue
            painter.drawText(
                cell.adjusted(CELL_PADDING, CELL_PADDING, -CELL_PADDING, -CELL_PADDING),
                int(bandera | Qt.AlignTop | Qt.TextWordWrap),
                text,
            )

        if self.isSelected():
            self.paint_selection(painter, rect)
            self.paint_handles(painter)


#: Side of a note icon, in PDF points. Fixed: it is not resized.
NOTE_SIZE = 20.0


class NoteItem(AnnotationItemMixin, QGraphicsRectItem):
    """Sticky note: a fixed icon with a text behind it."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._init_common(ann)
        self.apply_model()

    def _apply_model(self) -> None:
        x0, y0, _x1, _y1 = self.ann.normalized_rect()
        self.setPos(x0, y0)
        self.setRect(0, 0, NOTE_SIZE, NOTE_SIZE)
        self.setToolTip(self.ann.text or "")
        self.setOpacity(self.ann.opacity)

    def _sync_model(self) -> None:
        source = self.pos()
        self.ann.rect = (
            source.x(), source.y(),
            source.x() + NOTE_SIZE, source.y() + NOTE_SIZE,
        )

    def handles(self) -> dict:
        return {}          # fixed size: it does not stretch

    def mouseDoubleClickEvent(self, event) -> None:
        """Open the note's text. Without this, clicking it did nothing."""
        view = self._view()
        if view is not None and hasattr(view, "noteCreated"):
            view.noteCreated.emit(self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def boundingRect(self) -> QRectF:
        margin = self.handle_size() + 2.0
        return self.rect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        option.state &= ~QStyle.State_Selected
        rect = self.rect()
        color = qcolor(self.ann.color)
        # the note body with its folded corner
        body = QPainterPath()
        fold_size = rect.width() * 0.34
        body.moveTo(rect.left(), rect.top())
        body.lineTo(rect.right(), rect.top())
        body.lineTo(rect.right(), rect.bottom() - fold_size)
        body.lineTo(rect.right() - fold_size, rect.bottom())
        body.lineTo(rect.left(), rect.bottom())
        body.closeSubpath()
        painter.setPen(QPen(color.darker(140), rect.width() * 0.06))
        painter.setBrush(QBrush(color))
        painter.drawPath(body)
        # la esquina doblada
        fold = QPainterPath()
        fold.moveTo(rect.right() - fold_size, rect.bottom())
        fold.lineTo(rect.right() - fold_size, rect.bottom() - fold_size)
        fold.lineTo(rect.right(), rect.bottom() - fold_size)
        painter.setBrush(QBrush(color.darker(125)))
        painter.drawPath(fold)
        # ruled lines, so it reads like a written note
        painter.setPen(QPen(color.darker(190), rect.width() * 0.05))
        for i in (0.34, 0.52, 0.70):
            y = rect.top() + rect.height() * i
            painter.drawLine(
                QPointF(rect.left() + rect.width() * 0.18, y),
                QPointF(rect.right() - rect.width() * 0.22, y),
            )
        if self.isSelected():
            self.paint_selection(painter, rect)


def create_item(ann: Annotation, parent: QGraphicsItem | None = None):
    """Create the right graphics item for an annotation."""
    if ann.kind in (Kind.RECT, Kind.HIGHLIGHT):
        return RectItem(ann, parent)
    if ann.kind in (Kind.LINE, Kind.ARROW):
        return LineItem(ann, parent)
    if ann.kind in (Kind.INK, Kind.ERASE):
        return InkItem(ann, parent)
    if ann.kind is Kind.TEXT:
        return TextItem(ann, parent)
    if ann.kind is Kind.TABLE:
        return TableItem(ann, parent)
    if ann.kind is Kind.IMAGE:
        return ImageItem(ann, parent)
    if ann.kind is Kind.NOTE:
        return NoteItem(ann, parent)
    raise ValueError(f"tipo de anotacion sin item grafico: {ann.kind!r}")


__all__ = [
    "NoteItem",
    "RectItem",
    "ImageItem",
    "TableItem",
    "annotation_font",
    "LineItem",
    "InkItem",
    "TextItem",
    "create_item",
    "qcolor",
    "to_rgb",
    "AnnotationItemMixin",
]
