"""Iconos dibujados con QPainter.

Se generan por codigo para que el ejecutable no dependa de archivos externos y
para que los iconos se adapten al tema claro u oscuro del sistema.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
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


def _draw_eraser(p: QPainter) -> None:
    """Goma inclinada, con la parte de borrar en rosa y el cuerpo en gris."""
    # cuerpo (la mitad que se agarra)
    cuerpo = QPolygonF([QPointF(30, 12), QPointF(52, 34), QPointF(40, 46), QPointF(18, 24)])
    p.setPen(_pen(p, 3.5))
    p.setBrush(QBrush(QColor("#b0bec5")))
    p.drawPolygon(cuerpo)
    # punta que borra
    punta = QPolygonF([QPointF(18, 24), QPointF(40, 46), QPointF(28, 58), QPointF(6, 36)])
    p.setBrush(QBrush(QColor("#ef9a9a")))
    p.drawPolygon(punta)
    p.setBrush(Qt.NoBrush)
    # restos de lo borrado
    _pen(p, 3, QColor("#90a4ae"))
    p.drawLine(46, 54, 58, 54)
    p.drawLine(48, 46, 58, 46)


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


def _draw_new(p: QPainter) -> None:
    _page_outline(p)
    _pen(p, 4.5, QColor("#2e7d32"))
    p.drawLine(32, 26, 32, 44)
    p.drawLine(23, 35, 41, 35)


def _draw_image(p: QPainter) -> None:
    _pen(p, 4)
    p.drawRect(QRectF(8, 14, 48, 36))
    p.setBrush(_ink_color())
    p.drawEllipse(QPointF(21, 25), 4, 4)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(10, 48)
    path.lineTo(24, 34)
    path.lineTo(33, 43)
    path.lineTo(42, 30)
    path.lineTo(54, 48)
    p.drawPath(path)


def _draw_table(p: QPainter) -> None:
    _pen(p, 4)
    p.drawRect(QRectF(8, 12, 48, 40))
    p.drawLine(8, 26, 56, 26)
    p.drawLine(8, 39, 56, 39)
    p.drawLine(24, 12, 24, 52)
    p.drawLine(40, 12, 40, 52)


def _draw_bold(p: QPainter) -> None:
    font = QFont("Times New Roman")
    font.setPixelSize(46)
    font.setBold(True)
    p.setFont(font)
    p.setPen(_ink_color())
    p.drawText(QRectF(0, 0, SIZE, SIZE), Qt.AlignCenter, "B")


def _draw_italic(p: QPainter) -> None:
    font = QFont("Times New Roman")
    font.setPixelSize(46)
    font.setItalic(True)
    p.setFont(font)
    p.setPen(_ink_color())
    p.drawText(QRectF(0, 0, SIZE, SIZE), Qt.AlignCenter, "I")


def _draw_align(p: QPainter, modo: str) -> None:
    _pen(p, 5)
    anchos = (44, 30, 44, 26)
    for fila, ancho in enumerate(anchos):
        y = 16 + fila * 11
        if modo == "left":
            x = 10
        elif modo == "center":
            x = 10 + (44 - ancho) / 2
        else:
            x = 10 + (44 - ancho)
        p.drawLine(QPointF(x, y), QPointF(x + ancho, y))


def _draw_app(p: QPainter) -> None:
    """Icono de easypdf.surf: hoja de PDF, ola y lapiz.

    La ola es el guino al nombre; el lapiz, a que se puede escribir encima.
    """
    p.setPen(Qt.NoPen)

    # --- Hoja con la esquina superior derecha doblada ---------------------
    doblez = 15.0
    hoja = QPainterPath()
    hoja.moveTo(19, 2)
    hoja.lineTo(54 - doblez, 2)
    hoja.lineTo(54, 2 + doblez)
    hoja.lineTo(54, 47)
    hoja.quadTo(54, 53, 48, 53)
    hoja.lineTo(25, 53)
    hoja.quadTo(19, 53, 19, 47)
    hoja.closeSubpath()
    p.setBrush(QColor("#f2f3f5"))
    p.drawPath(hoja)
    p.setBrush(QColor("#ef3b26"))
    p.drawPolygon(
        QPolygonF([QPointF(54 - doblez, 2), QPointF(54, 2 + doblez), QPointF(54, 2)])
    )

    # Renglones del documento
    p.setBrush(QColor("#ccd1d9"))
    for y, ancho in ((26, 15), (33, 12)):
        p.drawRoundedRect(QRectF(37, y, ancho, 4.2), 2.1, 2.1)

    # --- Ola: masa de agua que barre la parte de abajo --------------------
    fondo = QPainterPath()
    fondo.moveTo(3, 42)
    fondo.cubicTo(12, 36, 22, 54, 34, 50)
    fondo.cubicTo(46, 46, 52, 38, 59, 43)
    fondo.cubicTo(63, 52, 55, 62, 42, 62)
    fondo.lineTo(15, 62)
    fondo.cubicTo(4, 62, -1, 52, 3, 42)
    fondo.closeSubpath()
    p.setBrush(QColor("#0d47a1"))
    p.drawPath(fondo)

    medio = QPainterPath()
    medio.moveTo(3, 48)
    medio.cubicTo(14, 42, 24, 58, 36, 54)
    medio.cubicTo(48, 50, 53, 45, 59, 49)
    medio.cubicTo(61, 56, 53, 62, 42, 62)
    medio.lineTo(15, 62)
    medio.cubicTo(5, 62, 1, 55, 3, 48)
    medio.closeSubpath()
    p.setBrush(QColor("#1e88e5"))
    p.drawPath(medio)

    # --- Cresta que se enrosca sobre si misma ----------------------------
    cresta = QPainterPath()
    cresta.moveTo(3, 50)
    cresta.cubicTo(-1, 28, 16, 18, 28, 26)
    cresta.cubicTo(38, 33, 34, 50, 22, 50)
    cresta.cubicTo(13, 50, 10, 42, 16, 38)
    cresta.cubicTo(21, 35, 26, 39, 24, 44)
    cresta.cubicTo(22, 47, 19, 46, 18, 44)
    cresta.cubicTo(21, 45, 23, 42, 21, 40)
    cresta.cubicTo(17, 37, 12, 42, 15, 46)
    cresta.cubicTo(19, 51, 30, 48, 30, 38)
    cresta.cubicTo(30, 28, 18, 23, 10, 30)
    cresta.cubicTo(5, 34, 4, 42, 6, 50)
    cresta.closeSubpath()
    p.setBrush(QColor("#29b6f6"))
    p.drawPath(cresta)

    # Espuma blanca en lo alto de la cresta
    espuma = QPainterPath()
    espuma.moveTo(9, 27)
    espuma.cubicTo(16, 19, 28, 21, 32, 29)
    espuma.cubicTo(27, 25, 18, 24, 13, 30)
    espuma.closeSubpath()
    p.setBrush(QColor("#ffffff"))
    p.drawPath(espuma)

    # Gotas que saltan
    p.setBrush(QColor("#29b6f6"))
    for cx, cy, r in ((17, 16, 2.2), (34, 21, 1.7), (35, 41, 1.5)):
        p.drawEllipse(QPointF(cx, cy), r, r)

    # --- Lapiz ------------------------------------------------------------
    _pencil(p, QPointF(41, 47), -45.0, 27.0, 4.4)


_DRAWINGS: dict[str, Callable[[QPainter], None]] = {
    "new": _draw_new,
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
    "eraser": _draw_eraser,
    "delete": _draw_delete,
    "undo": _draw_undo,
    "redo": _draw_redo,
    "search": _draw_search,
    "prev": _draw_prev,
    "next": _draw_next,
    "image": _draw_image,
    "table": _draw_table,
    "bold": _draw_bold,
    "italic": _draw_italic,
    "align_left": lambda p: _draw_align(p, "left"),
    "align_center": lambda p: _draw_align(p, "center"),
    "align_right": lambda p: _draw_align(p, "right"),
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


def asset_path(*parts: str) -> str | None:
    """Ruta a un archivo de assets/, tanto en el repo como dentro del .exe."""
    roots = []
    bundle = getattr(sys, "_MEIPASS", None)      # ejecutable de PyInstaller
    if bundle:
        roots.append(bundle)
    roots.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    for root in roots:
        candidate = os.path.join(root, "assets", *parts)
        if os.path.exists(candidate):
            return candidate
    return None


def app_icon() -> QIcon:
    """Icono de la aplicacion en todos los tamanos que pide Windows.

    Si hay un icono en ``assets/`` (por ejemplo uno propio generado con
    ``tools/make_icon.py``) se usa ese; si no, se dibuja por codigo.
    """
    for nombre in ("easypdf.ico", "easypdf.png"):
        ruta = asset_path(nombre)
        if ruta:
            candidato = QIcon(ruta)
            if not candidato.isNull():
                return candidato
    result = QIcon()
    for size in APP_ICON_SIZES:
        result.addPixmap(render("app", size))
    return result


def clear_cache() -> None:
    """Vacia la cache (util al cambiar de tema)."""
    _cache.clear()
