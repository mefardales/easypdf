"""Measuring rulers around the document view.

They measure from the top-left corner of the page being worked on, not from
the edge of the window, which is what matters to whoever is about to place
something inside the sheet.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

#: Ruler thickness, in screen pixels.
RULER_SIZE = 22

#: One PDF point is 1/72 inch.
PT_PER_MM = 72.0 / 25.4
PT_PER_IN = 72.0


class Ruler(QWidget):
    """Graduated ruler, horizontal or vertical, attached to the view."""

    def __init__(self, view, horizontal: bool, parent=None) -> None:
        super().__init__(parent)
        self._view = view
        self._horizontal = horizontal
        self._mouse = -1.0          # mouse position, in ruler pixels
        self._unit = "mm"
        if horizontal:
            self.setFixedHeight(RULER_SIZE)
        else:
            self.setFixedWidth(RULER_SIZE)
        self.setCursor(Qt.SplitVCursor if horizontal else Qt.SplitHCursor)
        self._dragging = False

    # -- units -----------------------------------------------------------
    @property
    def unit(self) -> str:
        return self._unit

    def set_unit(self, unit: str) -> None:
        if unit in ("mm", "cm", "in", "pt") and unit != self._unit:
            self._unit = unit
            self.update()

    def _step_pt(self) -> tuple[float, float, float]:
        """Return (minor step, numbered step, points per unit)."""
        if self._unit == "mm":
            return (PT_PER_MM, PT_PER_MM * 10, PT_PER_MM)
        if self._unit == "cm":
            return (PT_PER_MM, PT_PER_MM * 10, PT_PER_MM * 10)
        if self._unit == "in":
            return (PT_PER_IN / 8, PT_PER_IN, PT_PER_IN)
        return (10.0, 50.0, 1.0)          # points

    # -- mouse tracking --------------------------------------------------
    def set_mouse(self, pos: float) -> None:
        if pos != self._mouse:
            self._mouse = pos
            self.update()

    # -- origin ----------------------------------------------------------
    def _origin_scene(self) -> float | None:
        """Scene coordinate of zero: the corner of the current page."""
        page_item = self._view.current_page_item()
        if page_item is None:
            return None
        point = page_item.scenePos()
        return point.x() if self._horizontal else point.y()

    def value_at(self, pixel: float) -> float | None:
        """Measurement (in the active unit) for a pixel of the ruler."""
        source = self._origin_scene()
        if source is None:
            return None
        if self._horizontal:
            scene = self._view.mapToScene(int(pixel), 0).x()
        else:
            scene = self._view.mapToScene(0, int(pixel)).y()
        _minor, _major, per_unit = self._step_pt()
        return (scene - source) / per_unit

    # -- pulling out guides ----------------------------------------------
    def _page_value(self, global_pos):
        """Page coordinate matching a point on the screen."""
        view = self._view
        page_item = view.current_page_item()
        if page_item is None:
            return None
        in_view = view.viewport().mapFromGlobal(global_pos)
        scene = view.mapToScene(in_view)
        local = page_item.mapFromScene(scene)
        return local.y() if self._horizontal else local.x()

    def mousePressEvent(self, event) -> None:  # pragma: no cover - mouse gesture
        if event.button() != Qt.LeftButton:
            return
        value = self._page_value(event.globalPosition().toPoint())
        if value is None:
            return
        self._dragging = True
        self._view.start_guide("h" if self._horizontal else "v", value)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - mouse gesture
        if not self._dragging:
            return
        value = self._page_value(event.globalPosition().toPoint())
        if value is not None:
            self._view.move_guide(value)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - mouse gesture
        if not self._dragging:
            return
        self._dragging = False
        self._view.drop_guide(self._page_value(event.globalPosition().toPoint()))
        event.accept()

    # -- painting --------------------------------------------------------
    def paintEvent(self, event) -> None:  # pragma: no cover - drawing
        painter = QPainter(self)
        background = self.palette().window().color()
        text = self.palette().windowText().color()
        painter.fillRect(self.rect(), background.lighter(104))
        painter.setPen(QPen(background.darker(160), 1))
        if self._horizontal:
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        source = self._origin_scene()
        if source is None:
            painter.end()
            return

        pixels_per_pt = self._view.transform().m11()
        if pixels_per_pt <= 0:
            painter.end()
            return
        minor, major, per_unit = self._step_pt()
        length = self.width() if self._horizontal else self.height()

        # first and last visible value, in PDF points from the origin
        start = (self._view.mapToScene(0, 0).x() if self._horizontal
                 else self._view.mapToScene(0, 0).y()) - source
        end = start + length / pixels_per_pt

        font = QFont(painter.font())
        font.setPointSizeF(7.0)
        painter.setFont(font)

        # if the minor ticks would touch, only the major ones are drawn
        pintar_menores = minor * pixels_per_pt >= 3.0
        step = minor if pintar_menores else major
        first_tick = int(start // step) - 1
        last_tick = int(end // step) + 1
        for i in range(first_tick, last_tick + 1):
            value_pt = i * step
            pixel = (value_pt + source)
            pixel = (self._view.mapFromScene(QPointF(pixel, 0)).x() if self._horizontal
                     else self._view.mapFromScene(QPointF(0, pixel)).y())
            if pixel < -20 or pixel > length + 20:
                continue
            is_major = abs((value_pt / major) - round(value_pt / major)) < 1e-6
            height = (self.height() if self._horizontal else self.width())
            tick = height * (0.55 if is_major else 0.28)
            painter.setPen(QPen(text if is_major else text.lighter(160), 1))
            if self._horizontal:
                painter.drawLine(int(pixel), int(height - tick), int(pixel), height - 1)
            else:
                painter.drawLine(int(height - tick), int(pixel), height - 1, int(pixel))
            if is_major:
                label = f"{round(value_pt / per_unit):g}"
                painter.setPen(QPen(text, 1))
                if self._horizontal:
                    painter.drawText(QRectF(pixel + 2, 0, 40, height * 0.6),
                                     Qt.AlignLeft | Qt.AlignVCenter, label)
                else:
                    painter.save()
                    painter.translate(0, pixel - 2)
                    painter.rotate(-90)
                    painter.drawText(QRectF(0, 0, 40, height * 0.6),
                                     Qt.AlignLeft | Qt.AlignVCenter, label)
                    painter.restore()

        # Marks for the guides already placed, so you know where they are
        # without having to look at the page.
        self._paint_guides(painter, source, pixels_per_pt, length, per_unit)

        # mark showing where the mouse is
        if self._mouse >= 0:
            painter.setPen(QPen(QColor("#d81b1b"), 1))
            if self._horizontal:
                painter.drawLine(int(self._mouse), 0, int(self._mouse), self.height())
            else:
                painter.drawLine(0, int(self._mouse), self.width(), int(self._mouse))
        painter.end()

    def _guide_pixel(self, value: float, source: float) -> float:
        """Ruler pixel matching a page coordinate."""
        scene = source + value
        point = QPointF(scene, 0) if self._horizontal else QPointF(0, scene)
        p = self._view.mapFromScene(point)
        return p.x() if self._horizontal else p.y()

    def _paint_guides(self, painter, source, pixels_per_pt, length, per_unit) -> None:
        """Draw where each guide falls, and the measure of the dragged one."""
        view = self._view
        page_item = view.current_page_item()
        if page_item is None:
            return
        number = view.current_page
        # A horizontal guide ("h") is a line running across: its position is
        # read on the vertical ruler. And the other way round: hence the
        # crossed axis.
        axis = "v" if self._horizontal else "h"
        # Guides belong to the whole document: they show on any page.
        placed = list(view.rulers_guides.get(axis, []))

        dragging = None
        drag = getattr(view, "_guide_drag", None)
        if drag is not None and drag[0] == axis and drag[1] == number:
            dragging = drag[2]
            index = drag[3]
            if index is not None and 0 <= index < len(placed):
                placed.pop(index)      # it is drawn at its new place

        thickness = self.height() if self._horizontal else self.width()
        for value in placed:
            pixel = self._guide_pixel(value, source)
            if -4 <= pixel <= length + 4:
                painter.setPen(QPen(QColor("#00a3c4"), 2))
                if self._horizontal:
                    painter.drawLine(int(pixel), 2, int(pixel), thickness - 2)
                else:
                    painter.drawLine(2, int(pixel), thickness - 2, int(pixel))

        if dragging is None:
            return
        # The one being moved: a bolder mark with its measure beside it, so
        # it can be placed where it belongs without guessing.
        pixel = self._guide_pixel(dragging, source)
        painter.setPen(QPen(QColor("#d81b1b"), 2))
        if self._horizontal:
            painter.drawLine(int(pixel), 0, int(pixel), thickness)
        else:
            painter.drawLine(0, int(pixel), thickness, int(pixel))

        label = f"{dragging / per_unit:.1f}"
        background = QColor("#d81b1b")
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        if self._horizontal:
            box = QRectF(min(pixel + 3, length - 34), 1, 32, thickness - 2)
        else:
            box = QRectF(1, min(pixel + 3, length - 16), thickness - 2, 14)
        painter.drawRect(box)
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(box, Qt.AlignCenter, label)


__all__ = ["Ruler", "RULER_SIZE", "PT_PER_MM", "PT_PER_IN"]
