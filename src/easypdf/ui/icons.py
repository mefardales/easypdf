"""Iconos dibujados con QPainter.

Se generan por codigo para que el ejecutable no dependa de archivos externos y
para que los iconos se adapten al tema claro u oscuro del sistema.
"""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication

SIZE = 64
_cache: dict[str, QIcon] = {}


def _ink_color() -> QColor:
    """Color de trazo legible sobre la barra de herramientas actual."""
    app = QApplication.instance()
    if app is not None:
        base = app.palette().window().color()
        if base.lightness() < 128:
            return QColor("#e6e6e6")
    return QColor("#303030")


def _pen(p: QPainter, width: float = 5.0, color: QColor | None = None) -> QPen:
    pen = QPen(color or _ink_color())
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    return pen


def _page_outline(p: QPainter, folded: bool = True) -> None:
    _pen(p, 4.5)
    path = QPainterPath()
    if folded:
        path.moveTo(16, 8)
        path.lineTo(38, 8)
        path.lineTo(48, 18)
        path.lineTo(48, 56)
        path.lineTo(16, 56)
        path.closeSubpath()
        p.drawPath(path)
        p.drawPolyline(QPolygonF([QPointF(38, 8), QPointF(38, 18), QPointF(48, 18)]))
    else:
        p.drawRect(QRectF(14, 8, 36, 48))


# ---------------------------------------------------------------- dibujos
def _draw_open(p: QPainter) -> None:
    _pen(p, 4.5)
    p.drawPolyline(QPolygonF([QPointF(8, 50), QPointF(8, 16), QPointF(26, 16),
                              QPointF(32, 24), QPointF(50, 24)]))
    path = QPainterPath()
    path.moveTo(8, 50)
    path.lineTo(18, 30)
    path.lineTo(58, 30)
    path.lineTo(48, 50)
    path.closeSubpath()
    p.drawPath(path)


def _draw_save(p: QPainter) -> None:
    _pen(p, 4.5)
    p.drawRect(QRectF(10, 10, 44, 44))
    p.drawRect(QRectF(20, 10, 24, 16))
    p.drawRect(QRectF(18, 34, 28, 20))


def _draw_save_as(p: QPainter) -> None:
    _draw_save(p)
    _pen(p, 4.5, QColor("#2e7d32"))
    p.drawLine(48, 44, 48, 60)
    p.drawLine(40, 52, 56, 52)


def _draw_print(p: QPainter) -> None:
    _pen(p, 4.5)
    p.drawRect(QRectF(18, 8, 28, 14))
    p.drawRect(QRectF(8, 22, 48, 22))
    p.drawRect(QRectF(18, 38, 28, 18))


def _draw_zoom(p: QPainter, plus: bool) -> None:
    _pen(p, 5)
    p.drawEllipse(QPointF(27, 27), 17, 17)
    p.drawLine(40, 40, 56, 56)
    p.drawLine(19, 27, 35, 27)
    if plus:
        p.drawLine(27, 19, 27, 35)


def _draw_fit_width(p: QPainter) -> None:
    _pen(p, 4.5)
    p.drawRect(QRectF(10, 14, 44, 36))
    _pen(p, 4.5, QColor("#1565c0"))
    p.drawLine(18, 32, 46, 32)
    p.drawPolyline(QPolygonF([QPointF(24, 26), QPointF(18, 32), QPointF(24, 38)]))
    p.drawPolyline(QPolygonF([QPointF(40, 26), QPointF(46, 32), QPointF(40, 38)]))


def _draw_fit_page(p: QPainter) -> None:
    _pen(p, 4.5)
    p.drawRect(QRectF(16, 8, 32, 48))
    _pen(p, 4.5, QColor("#1565c0"))
    p.drawLine(32, 16, 32, 48)
    p.drawPolyline(QPolygonF([QPointF(26, 22), QPointF(32, 16), QPointF(38, 22)]))
    p.drawPolyline(QPolygonF([QPointF(26, 42), QPointF(32, 48), QPointF(38, 42)]))


def _draw_select(p: QPainter) -> None:
    _pen(p, 4)
    path = QPainterPath()
    path.moveTo(18, 8)
    path.lineTo(18, 50)
    path.lineTo(29, 40)
    path.lineTo(36, 56)
    path.lineTo(44, 52)
    path.lineTo(37, 37)
    path.lineTo(50, 34)
    path.closeSubpath()
    p.drawPath(path)


def _draw_hand(p: QPainter) -> None:
    """Herramienta de desplazamiento: cruz de cuatro flechas."""
    _pen(p, 4.5)
    p.drawLine(32, 12, 32, 52)
    p.drawLine(12, 32, 52, 32)
    p.setBrush(_ink_color())
    p.setPen(Qt.NoPen)
    for pts in (
        [(32, 6), (25, 16), (39, 16)],
        [(32, 58), (25, 48), (39, 48)],
        [(6, 32), (16, 25), (16, 39)],
        [(58, 32), (48, 25), (48, 39)],
    ):
        p.drawPolygon(QPolygonF([QPointF(*pt) for pt in pts]))


def _draw_rect(p: QPainter) -> None:
    _pen(p, 5, QColor("#d81b1b"))
    p.drawRect(QRectF(10, 16, 44, 32))


def _draw_highlight(p: QPainter) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 212, 0, 220))
    p.drawRect(QRectF(8, 26, 48, 18))
    _pen(p, 4)
    p.drawLine(8, 50, 56, 50)


def _draw_line(p: QPainter) -> None:
    _pen(p, 5, QColor("#d81b1b"))
    p.drawLine(10, 50, 54, 14)


def _draw_arrow(p: QPainter) -> None:
    color = QColor("#d81b1b")
    _pen(p, 5, color)
    p.drawLine(10, 52, 46, 18)
    p.setBrush(color)
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(54, 10), QPointF(52, 30), QPointF(34, 28)]))


def _draw_text(p: QPainter) -> None:
    _pen(p, 3.5)
    p.drawRect(QRectF(8, 14, 48, 36))
    font = QFont()
    font.setPointSizeF(26)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(8, 14, 48, 36), Qt.AlignCenter, "A")


def _draw_ink(p: QPainter) -> None:
    _pen(p, 5, QColor("#d81b1b"))
    path = QPainterPath()
    path.moveTo(8, 44)
    path.cubicTo(20, 12, 30, 60, 40, 30)
    path.cubicTo(46, 14, 52, 30, 56, 22)
    p.drawPath(path)


def _draw_delete(p: QPainter) -> None:
    _pen(p, 4.5, QColor("#c62828"))
    p.drawLine(14, 18, 50, 18)
    p.drawLine(26, 18, 26, 12)
    p.drawLine(38, 18, 38, 12)
    p.drawPolyline(QPolygonF([QPointF(18, 18), QPointF(21, 54), QPointF(43, 54), QPointF(46, 18)]))


def _draw_undo(p: QPainter, mirrored: bool = False) -> None:
    if mirrored:
        p.translate(SIZE, 0)
        p.scale(-1, 1)
    _pen(p, 5)
    path = QPainterPath()
    path.moveTo(14, 34)
    path.cubicTo(20, 12, 52, 14, 50, 40)
    p.drawPath(path)
    p.setBrush(_ink_color())
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(6, 30), QPointF(26, 26), QPointF(16, 44)]))


def _draw_redo(p: QPainter) -> None:
    _draw_undo(p, mirrored=True)


def _draw_search(p: QPainter) -> None:
    _pen(p, 5)
    p.drawEllipse(QPointF(27, 27), 17, 17)
    p.drawLine(40, 40, 56, 56)


def _draw_prev(p: QPainter, up: bool = True) -> None:
    _pen(p, 6)
    if up:
        p.drawPolyline(QPolygonF([QPointF(16, 38), QPointF(32, 22), QPointF(48, 38)]))
    else:
        p.drawPolyline(QPolygonF([QPointF(16, 26), QPointF(32, 42), QPointF(48, 26)]))


def _draw_next(p: QPainter) -> None:
    _draw_prev(p, up=False)


def _pencil(p: QPainter, tip: QPointF, angle_deg: float, length: float, half: float) -> None:
    """Lapiz rojo con punta de madera y virola azul, apuntando a ``tip``."""
    angle = math.radians(angle_deg)
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = -dy * half, dx * half

    def along(distance: float) -> QPointF:
        return QPointF(tip.x() + dx * distance, tip.y() + dy * distance)

    def band(start: float, end: float, color: QColor) -> None:
        a, b = along(start), along(end)
        p.setBrush(color)
        p.drawPolygon(
            QPolygonF([
                QPointF(a.x() + px, a.y() + py),
                QPointF(b.x() + px, b.y() + py),
                QPointF(b.x() - px, b.y() - py),
                QPointF(a.x() - px, a.y() - py),
            ])
        )

    p.setPen(Qt.NoPen)
    wood = length * 0.22
    # Punta de grafito
    graphite = along(wood * 0.45)
    p.setBrush(QColor("#1f2d4d"))
    p.drawPolygon(
        QPolygonF([
            tip,
            QPointF(graphite.x() + px * 0.45, graphite.y() + py * 0.45),
            QPointF(graphite.x() - px * 0.45, graphite.y() - py * 0.45),
        ])
    )
    # Madera
    wood_end = along(wood)
    p.setBrush(QColor("#f3d3a2"))
    p.drawPolygon(
        QPolygonF([
            along(wood * 0.35),
            QPointF(wood_end.x() + px, wood_end.y() + py),
            QPointF(wood_end.x() - px, wood_end.y() - py),
        ])
    )
    band(wood, length * 0.74, QColor("#e5121a"))          # cuerpo
    band(length * 0.74, length * 0.86, QColor("#1f2d4d"))  # virola
    band(length * 0.86, length, QColor("#ff5a4d"))         # goma


def _draw_app(p: QPainter) -> None:
    """Icono de EasyPDF: hoja con esquina doblada, renglones y lapiz."""
    p.setPen(Qt.NoPen)
    # Placa roja de fondo, desplazada hacia abajo a la izquierda
    p.setBrush(QColor("#e5121a"))
    p.drawRoundedRect(QRectF(3, 12, 40, 48), 7, 7)

    # Hoja blanca con la esquina superior derecha doblada
    fold = 13.0
    sheet = QPainterPath()
    sheet.moveTo(19, 2)
    sheet.lineTo(56 - fold, 2)
    sheet.lineTo(56, 2 + fold)
    sheet.lineTo(56, 48)
    sheet.quadTo(56, 53, 51, 53)
    sheet.lineTo(24, 53)
    sheet.quadTo(19, 53, 19, 48)
    sheet.closeSubpath()
    p.setBrush(QColor("#f7f7f8"))
    p.drawPath(sheet)
    # La esquina recortada deja ver el reverso rojo de la hoja.
    p.setBrush(QColor("#e5121a"))
    p.drawPolygon(
        QPolygonF([QPointF(56 - fold, 2), QPointF(56, 2 + fold), QPointF(56, 2)])
    )

    # Renglones del documento
    p.setBrush(QColor("#e5121a"))
    for y, width in ((15, 28), (26, 24), (37, 26)):
        p.drawRoundedRect(QRectF(25, y, width, 6), 3, 3)

    _pencil(p, QPointF(30, 62), -45.0, 40.0, 5.5)


_DRAWINGS: dict[str, Callable[[QPainter], None]] = {
    "open": _draw_open,
    "save": _draw_save,
    "save_as": _draw_save_as,
    "print": _draw_print,
    "zoom_in": lambda p: _draw_zoom(p, True),
    "zoom_out": lambda p: _draw_zoom(p, False),
    "fit_width": _draw_fit_width,
    "fit_page": _draw_fit_page,
    "select": _draw_select,
    "hand": _draw_hand,
    "rect": _draw_rect,
    "highlight": _draw_highlight,
    "line": _draw_line,
    "arrow": _draw_arrow,
    "text": _draw_text,
    "ink": _draw_ink,
    "delete": _draw_delete,
    "undo": _draw_undo,
    "redo": _draw_redo,
    "search": _draw_search,
    "prev": _draw_prev,
    "next": _draw_next,
    "app": _draw_app,
}


def render(name: str, size: int = SIZE) -> QPixmap:
    """Dibuja el icono al tamano pedido (el trazo se escala, no se estira)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(Qt.NoBrush)
    painter.scale(size / SIZE, size / SIZE)
    drawing = _DRAWINGS.get(name)
    if drawing is not None:
        drawing(painter)
    painter.end()
    return pixmap


def icon(name: str) -> QIcon:
    """Devuelve (y memoriza) el icono con ese nombre."""
    if name in _cache:
        return _cache[name]
    result = QIcon()
    for size in (16, 24, 32, 48, 64):
        result.addPixmap(render(name, size))
    _cache[name] = result
    return result


#: Tamanos que se incrustan en el icono de la aplicacion y en el .ico.
APP_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def app_icon() -> QIcon:
    """Icono de la aplicacion en todos los tamanos que pide Windows."""
    result = QIcon()
    for size in APP_ICON_SIZES:
        result.addPixmap(render("app", size))
    return result


def clear_cache() -> None:
    """Vacia la cache (util al cambiar de tema)."""
    _cache.clear()
