"""Elementos graficos que representan las anotaciones sobre la pagina.

Cada item vive dentro de un ``PageItem`` y trabaja directamente en **puntos
PDF**, asi que no hay conversiones de zoom: lo que se dibuja es exactamente lo
que se escribe despues en el archivo.
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

#: Tamano del tirador de redimension, en pixeles de pantalla.
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
    """QFont equivalente al estilo guardado en la anotacion."""
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
    """Convierte un color del modelo (0..1) en QColor."""
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
        # Mientras se vuelca el modelo sobre el item, los cambios de posicion
        # que emite Qt no deben reescribir el modelo con datos a medias.
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
        """Tiradores en coordenadas locales del item."""
        return {}

    def handle_at(self, pos: QPointF) -> str | None:
        half = self.handle_size() / 2.0
        for name, point in self.handles().items():
            if QRectF(point.x() - half, point.y() - half, half * 2, half * 2).contains(pos):
                return name
        return None

    def resize_to(self, handle: str, pos: QPointF) -> None:  # pragma: no cover - UI
        """Aplica el arrastre de un tirador (coordenadas locales)."""

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
        """Vuelca el modelo sobre el item (modelo -> pantalla)."""
        self._applying = True
        try:
            self._apply_model()
        finally:
            self._applying = False

    def sync_model(self) -> None:
        """Vuelca el item sobre el modelo (pantalla -> modelo)."""
        if getattr(self, "_applying", False):
            return
        self._sync_model()

    def _apply_model(self) -> None:  # pragma: no cover - lo implementa cada item
        """Geometria y estilo del item a partir de ``self.ann``."""

    def _sync_model(self) -> None:  # pragma: no cover - lo implementa cada item
        """Actualiza ``self.ann`` con la geometria actual del item."""

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

    # -- alineacion ------------------------------------------------------
    def snap_candidates(self) -> tuple[list[float], list[float]]:
        """Lineas a las que se puede alinear: la pagina y las demas anotaciones."""
        pagina = self.parentItem()
        if pagina is None:
            return ([], [])
        caja = pagina.boundingRect()
        # bordes y centro de la hoja
        xs = [caja.left(), caja.center().x(), caja.right()]
        ys = [caja.top(), caja.center().y(), caja.bottom()]
        for otro in pagina.childItems():
            if otro is self or not isinstance(otro, AnnotationItemMixin):
                continue
            x0, y0, x1, y1 = otro.ann.bounds()
            xs += [x0, (x0 + x1) / 2.0, x1]
            ys += [y0, (y0 + y1) / 2.0, y1]
        return (xs, ys)

    def _snap(self, nueva_pos):
        """Ajusta la posicion propuesta para que encaje con alguna guia."""
        vista = self._view()
        if vista is None or not getattr(vista, "snap_enabled", False):
            return nueva_pos
        escala = max(vista.transform().m11(), 1e-6)
        umbral = SNAP_PIXELS / escala

        # los bordes se calculan sobre el modelo, que siempre esta en
        # coordenadas de la pagina, sea cual sea el tipo de anotacion
        dx = nueva_pos.x() - self.pos().x()
        dy = nueva_pos.y() - self.pos().y()
        x0, y0, x1, y1 = self.ann.bounds()
        x0, x1, y0, y1 = x0 + dx, x1 + dx, y0 + dy, y1 + dy

        xs, ys = self.snap_candidates()
        ajuste_x, guia_x = snap_offset([x0, (x0 + x1) / 2.0, x1], xs, umbral)
        ajuste_y, guia_y = snap_offset([y0, (y0 + y1) / 2.0, y1], ys, umbral)
        vista.show_guides(guia_x, guia_y, self.parentItem())
        return QPointF(nueva_pos.x() + ajuste_x, nueva_pos.y() + ajuste_y)

    def _view(self):
        escena = self.scene()
        if escena is None:
            return None
        vistas = escena.views()
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
        # Se reubica el item para que el rectangulo local empiece en (0, 0).
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
        option.state &= ~QStyle.State_Selected  # el marco por defecto sobra
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())
        if self.isSelected():
            self.paint_selection(painter, self.rect())
            self.paint_handles(painter)


class LineItem(AnnotationItemMixin, QGraphicsLineItem):
    """Linea recta, con o sin punta de flecha."""

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
        """Punta de flecha, con la misma geometria que se guarda en el PDF."""
        line = self.line()
        p1 = (line.x1(), line.y1())
        p2 = (line.x2(), line.y2())
        _base, punta, izquierda, derecha = arrow_head(p1, p2, self.ann.width)
        poligono = QPolygonF([QPointF(*punta), QPointF(*izquierda), QPointF(*derecha)])
        return poligono, QPointF(*arrow_line_end(p1, p2, self.ann.width))

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
            poligono, fin = self._arrow_points()
            # El trazo termina dentro de la punta para que no asome por delante.
            painter.drawLine(QLineF(self.line().p1(), fin))
            painter.setPen(QPen(Qt.NoPen))
            painter.setBrush(QBrush(qcolor(self.ann.color)))
            painter.drawPolygon(poligono)
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
        # Copia de los trazos tal y como estan en el modelo: al arrastrar, el
        # desplazamiento vive en la posicion del item y se suma sobre esta base.
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
        """Anade un punto al trazo actual mientras se dibuja."""
        if new_stroke or not self.ann.strokes:
            self.ann.strokes.append([])
        self.ann.strokes[-1].append((point.x(), point.y()))
        self.prepareGeometryChange()
        self.apply_model()

    def _sync_model(self) -> None:
        # Nunca se toca setPos() aqui: esto se llama desde itemChange mientras
        # Qt esta arrastrando el item, y mover la posicion en mitad del arrastre
        # hacia que el dibujo saliera disparado fuera de la pantalla.
        offset = self.pos()
        base = getattr(self, "_base", None) or self.ann.strokes
        self.ann.strokes = [
            [(x + offset.x(), y + offset.y()) for x, y in stroke] for stroke in base
        ]

    def boundingRect(self) -> QRectF:
        # El recuadro de seleccion se dibuja justo sobre el borde del trazo, asi
        # que hay que declarar tambien ese margen o deja rastro al arrastrar.
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
    """Cuadro de texto editable en pantalla."""

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
        opciones = self.document().defaultTextOption()
        opciones.setAlignment(ALIGN_FLAGS.get(Align(ann.align), Qt.AlignLeft))
        self.document().setDefaultTextOption(opciones)
        width = max(20.0, x1 - x0)
        self.setTextWidth(width)
        if self.toPlainText() != ann.text:
            blocked = self.document().blockSignals(True)
            self.setPlainText(ann.text)
            self.document().blockSignals(blocked)
        self.setOpacity(ann.opacity)

    def content_rect(self) -> QRectF:
        """Rectangulo del cuadro de texto, sin el margen de seleccion."""
        return QGraphicsTextItem.boundingRect(self)

    def boundingRect(self) -> QRectF:
        """Area a repintar: el cuadro mas el borde y los tiradores.

        QGraphicsTextItem solo declara el rectangulo del texto, pero el tirador
        de anchura se dibuja centrado en el lado derecho y sobresale la mitad.
        Sin este margen, al arrastrar el cuadro esa mitad no se borraba y
        quedaba un rastro azul detras.
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
            # Guia tenue para localizar el cuadro sin borde (no se imprime).
            pen = QPen(QColor(0, 0, 0, 40))
            pen.setStyle(Qt.DotLine)
            pen.setWidthF(0.8 / self.view_scale())
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)


class ImageItem(AnnotationItemMixin, QGraphicsRectItem):
    """Imagen colocada encima de la pagina."""

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
        """Proporcion ancho/alto de la imagen original."""
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
        # Las esquinas conservan la proporcion; los lados estiran libremente.
        if handle in ("tl", "tr", "bl", "br") and self.aspect > 0:
            alto = r.width() / self.aspect
            if "t" in handle:
                r.setTop(r.bottom() - alto)
            else:
                r.setHeight(alto)
        self.setPos(self.pos() + r.topLeft())
        self.setRect(0, 0, r.width(), r.height())

    def boundingRect(self) -> QRectF:
        margen = self.handle_size() + 2.0
        return self.rect().adjusted(-margen, -margen, margen, margen)

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


class TableItem(AnnotationItemMixin, QGraphicsRectItem):
    """Tabla: rejilla de filas y columnas con texto en las celdas."""

    def __init__(self, ann: Annotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
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
        margen = max(self.pen().widthF(), self.handle_size()) + 2.0
        return self.rect().adjusted(-margen, -margen, margen, margen)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        margen = self.handle_size()
        path.addRect(self.rect().adjusted(-margen, -margen, margen, margen))
        return path

    # -- celdas ----------------------------------------------------------
    def local_cell_rects(self) -> list[QRectF]:
        """Rectangulos de las celdas en coordenadas del propio item."""
        r = self.rect()
        filas, columnas = max(1, self.ann.rows), max(1, self.ann.cols)
        alto = r.height() / filas
        ancho = r.width() / columnas
        return [
            QRectF(c * ancho, f * alto, ancho, alto)
            for f in range(filas)
            for c in range(columnas)
        ]

    def cell_at(self, pos: QPointF) -> int:
        for indice, celda in enumerate(self.local_cell_rects()):
            if celda.contains(pos):
                return indice
        return -1

    def edit_cell(self, indice: int) -> None:
        """Abre un editor de texto encima de la celda indicada."""
        celdas = self.local_cell_rects()
        if not (0 <= indice < len(celdas)):
            return
        self.finish_editing()
        self.notify_scene("begin_edit")
        self.notify_scene("text_editing_started")
        textos = self.ann.normalized_cells()
        editor = QGraphicsTextItem(self)
        editor.setPlainText(textos[indice])
        editor.setFont(annotation_font(self.ann))
        editor.setDefaultTextColor(qcolor(self.ann.color))
        celda = celdas[indice]
        editor.setTextWidth(max(10.0, celda.width() - 4))
        editor.setPos(celda.topLeft() + QPointF(2, 2))
        editor.setTextInteractionFlags(Qt.TextEditorInteraction)
        editor.setZValue(self.zValue() + 1)
        editor.setFlag(QGraphicsItem.ItemIsFocusable, True)
        editor.setFocus(Qt.MouseFocusReason)
        cursor = editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        editor.setTextCursor(cursor)
        self._editor = editor
        self._editing_cell = indice
        self.update()

    def finish_editing(self) -> None:
        """Guarda lo escrito y cierra el editor."""
        editor, indice = self._editor, self._editing_cell
        self._editor, self._editing_cell = None, -1
        if editor is None:
            return
        textos = self.ann.normalized_cells()
        textos[indice] = editor.toPlainText()
        self.ann.cells = textos
        editor.setParentItem(None)
        if editor.scene() is not None:
            editor.scene().removeItem(editor)
        self.update()
        self.notify_scene("end_edit")
        self.notify_scene("text_editing_finished")

    @property
    def is_editing(self) -> bool:
        return self._editor is not None

    # -- eventos ---------------------------------------------------------
    def mouseDoubleClickEvent(self, event) -> None:
        indice = self.cell_at(event.pos())
        if indice >= 0:
            self.edit_cell(indice)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if self.is_editing and event.key() in (Qt.Key_Escape, Qt.Key_Tab):
            siguiente = self._editing_cell + 1
            self.finish_editing()
            if event.key() == Qt.Key_Tab and siguiente < self.ann.cell_count():
                self.edit_cell(siguiente)
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
        filas, columnas = max(1, self.ann.rows), max(1, self.ann.cols)
        painter.drawRect(rect)
        for f in range(1, filas):
            y = rect.top() + rect.height() * f / filas
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        for c in range(1, columnas):
            x = rect.left() + rect.width() * c / columnas
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        painter.setFont(annotation_font(self.ann))
        painter.setPen(QPen(qcolor(self.ann.color)))
        bandera = ALIGN_FLAGS.get(Align(self.ann.align), Qt.AlignLeft)
        for indice, (texto, celda) in enumerate(
            zip(self.ann.normalized_cells(), self.local_cell_rects())
        ):
            if not texto or indice == self._editing_cell:
                continue
            painter.drawText(
                celda.adjusted(2.5, 2.5, -2.5, -2.5),
                int(bandera | Qt.AlignTop | Qt.TextWordWrap),
                texto,
            )

        if self.isSelected():
            self.paint_selection(painter, rect)
            self.paint_handles(painter)


#: Lado del icono de una nota, en puntos PDF. Fijo: no se redimensiona.
NOTE_SIZE = 20.0


class NoteItem(AnnotationItemMixin, QGraphicsRectItem):
    """Nota adhesiva: un icono fijo que guarda un texto detras."""

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
        origen = self.pos()
        self.ann.rect = (
            origen.x(), origen.y(),
            origen.x() + NOTE_SIZE, origen.y() + NOTE_SIZE,
        )

    def handles(self) -> dict:
        return {}          # tamano fijo: no se estira

    def boundingRect(self) -> QRectF:
        margen = self.handle_size() + 2.0
        return self.rect().adjusted(-margen, -margen, margen, margen)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        option.state &= ~QStyle.State_Selected
        rect = self.rect()
        color = qcolor(self.ann.color)
        # cuerpo de la nota con la esquina doblada
        cuerpo = QPainterPath()
        pliegue = rect.width() * 0.34
        cuerpo.moveTo(rect.left(), rect.top())
        cuerpo.lineTo(rect.right(), rect.top())
        cuerpo.lineTo(rect.right(), rect.bottom() - pliegue)
        cuerpo.lineTo(rect.right() - pliegue, rect.bottom())
        cuerpo.lineTo(rect.left(), rect.bottom())
        cuerpo.closeSubpath()
        painter.setPen(QPen(color.darker(140), rect.width() * 0.06))
        painter.setBrush(QBrush(color))
        painter.drawPath(cuerpo)
        # la esquina doblada
        doblez = QPainterPath()
        doblez.moveTo(rect.right() - pliegue, rect.bottom())
        doblez.lineTo(rect.right() - pliegue, rect.bottom() - pliegue)
        doblez.lineTo(rect.right(), rect.bottom() - pliegue)
        painter.setBrush(QBrush(color.darker(125)))
        painter.drawPath(doblez)
        # renglones, para que se lea como una nota escrita
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
    """Crea el item grafico adecuado para una anotacion."""
    if ann.kind in (Kind.RECT, Kind.HIGHLIGHT):
        return RectItem(ann, parent)
    if ann.kind in (Kind.LINE, Kind.ARROW):
        return LineItem(ann, parent)
    if ann.kind is Kind.INK:
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
