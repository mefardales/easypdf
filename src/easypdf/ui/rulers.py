"""Reglas de medida alrededor de la vista del documento.

Miden desde la esquina superior izquierda de la pagina en la que se esta
trabajando, no desde el borde de la ventana, que es lo que le interesa a quien
va a colocar algo dentro de la hoja.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

#: Grosor de la regla, en pixeles de pantalla.
RULER_SIZE = 22

#: Un punto PDF es 1/72 de pulgada.
PT_PER_MM = 72.0 / 25.4
PT_PER_IN = 72.0


class Ruler(QWidget):
    """Regla graduada, horizontal o vertical, pegada a la vista."""

    def __init__(self, view, horizontal: bool, parent=None) -> None:
        super().__init__(parent)
        self._view = view
        self._horizontal = horizontal
        self._mouse = -1.0          # posicion del raton, en pixeles de la regla
        self._unit = "mm"
        if horizontal:
            self.setFixedHeight(RULER_SIZE)
        else:
            self.setFixedWidth(RULER_SIZE)
        self.setCursor(Qt.SplitVCursor if horizontal else Qt.SplitHCursor)
        self._arrastrando = False

    # -- unidades --------------------------------------------------------
    @property
    def unit(self) -> str:
        return self._unit

    def set_unit(self, unit: str) -> None:
        if unit in ("mm", "cm", "in", "pt") and unit != self._unit:
            self._unit = unit
            self.update()

    def _step_pt(self) -> tuple[float, float, float]:
        """Devuelve (paso menor, paso con numero, puntos por unidad)."""
        if self._unit == "mm":
            return (PT_PER_MM, PT_PER_MM * 10, PT_PER_MM)
        if self._unit == "cm":
            return (PT_PER_MM, PT_PER_MM * 10, PT_PER_MM * 10)
        if self._unit == "in":
            return (PT_PER_IN / 8, PT_PER_IN, PT_PER_IN)
        return (10.0, 50.0, 1.0)          # puntos

    # -- seguimiento del raton -------------------------------------------
    def set_mouse(self, pos: float) -> None:
        if pos != self._mouse:
            self._mouse = pos
            self.update()

    # -- origen ----------------------------------------------------------
    def _origin_scene(self) -> float | None:
        """Coordenada de escena del cero: la esquina de la pagina actual."""
        pagina = self._view.current_page_item()
        if pagina is None:
            return None
        punto = pagina.scenePos()
        return punto.x() if self._horizontal else punto.y()

    def value_at(self, pixel: float) -> float | None:
        """Medida (en la unidad activa) que corresponde a un pixel de la regla."""
        origen = self._origin_scene()
        if origen is None:
            return None
        if self._horizontal:
            escena = self._view.mapToScene(int(pixel), 0).x()
        else:
            escena = self._view.mapToScene(0, int(pixel)).y()
        _menor, _mayor, por_unidad = self._step_pt()
        return (escena - origen) / por_unidad

    # -- sacar guias -----------------------------------------------------
    def _valor_en_pagina(self, pos_global):
        """Coordenada de pagina que corresponde a un punto de la pantalla."""
        vista = self._view
        pagina = vista.current_page_item()
        if pagina is None:
            return None
        en_vista = vista.viewport().mapFromGlobal(pos_global)
        escena = vista.mapToScene(en_vista)
        local = pagina.mapFromScene(escena)
        return local.y() if self._horizontal else local.x()

    def mousePressEvent(self, event) -> None:  # pragma: no cover - gesto de raton
        if event.button() != Qt.LeftButton:
            return
        valor = self._valor_en_pagina(event.globalPosition().toPoint())
        if valor is None:
            return
        self._arrastrando = True
        self._view.start_guide("h" if self._horizontal else "v", valor)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - gesto de raton
        if not self._arrastrando:
            return
        valor = self._valor_en_pagina(event.globalPosition().toPoint())
        if valor is not None:
            self._view.move_guide(valor)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - gesto de raton
        if not self._arrastrando:
            return
        self._arrastrando = False
        self._view.drop_guide(self._valor_en_pagina(event.globalPosition().toPoint()))
        event.accept()

    # -- pintado ---------------------------------------------------------
    def paintEvent(self, event) -> None:  # pragma: no cover - dibujo
        painter = QPainter(self)
        fondo = self.palette().window().color()
        texto = self.palette().windowText().color()
        painter.fillRect(self.rect(), fondo.lighter(104))
        painter.setPen(QPen(fondo.darker(160), 1))
        if self._horizontal:
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        origen = self._origin_scene()
        if origen is None:
            painter.end()
            return

        escala = self._view.transform().m11()
        if escala <= 0:
            painter.end()
            return
        menor, mayor, por_unidad = self._step_pt()
        largo = self.width() if self._horizontal else self.height()

        # primer y ultimo valor visibles, en puntos PDF desde el origen
        desde = (self._view.mapToScene(0, 0).x() if self._horizontal
                 else self._view.mapToScene(0, 0).y()) - origen
        hasta = desde + largo / escala

        fuente = QFont(painter.font())
        fuente.setPointSizeF(7.0)
        painter.setFont(fuente)

        # si las marcas menores quedarian pegadas, solo se dibujan las mayores
        pintar_menores = menor * escala >= 3.0
        paso = menor if pintar_menores else mayor
        primera = int(desde // paso) - 1
        ultima = int(hasta // paso) + 1
        for i in range(primera, ultima + 1):
            valor_pt = i * paso
            pixel = (valor_pt + origen)
            pixel = (self._view.mapFromScene(QPointF(pixel, 0)).x() if self._horizontal
                     else self._view.mapFromScene(QPointF(0, pixel)).y())
            if pixel < -20 or pixel > largo + 20:
                continue
            es_mayor = abs((valor_pt / mayor) - round(valor_pt / mayor)) < 1e-6
            alto = (self.height() if self._horizontal else self.width())
            largo_marca = alto * (0.55 if es_mayor else 0.28)
            painter.setPen(QPen(texto if es_mayor else texto.lighter(160), 1))
            if self._horizontal:
                painter.drawLine(int(pixel), int(alto - largo_marca), int(pixel), alto - 1)
            else:
                painter.drawLine(int(alto - largo_marca), int(pixel), alto - 1, int(pixel))
            if es_mayor:
                etiqueta = f"{round(valor_pt / por_unidad):g}"
                painter.setPen(QPen(texto, 1))
                if self._horizontal:
                    painter.drawText(QRectF(pixel + 2, 0, 40, alto * 0.6),
                                     Qt.AlignLeft | Qt.AlignVCenter, etiqueta)
                else:
                    painter.save()
                    painter.translate(0, pixel - 2)
                    painter.rotate(-90)
                    painter.drawText(QRectF(0, 0, 40, alto * 0.6),
                                     Qt.AlignLeft | Qt.AlignVCenter, etiqueta)
                    painter.restore()

        # marca de donde esta el raton
        if self._mouse >= 0:
            painter.setPen(QPen(QColor("#d81b1b"), 1))
            if self._horizontal:
                painter.drawLine(int(self._mouse), 0, int(self._mouse), self.height())
            else:
                painter.drawLine(0, int(self._mouse), self.width(), int(self._mouse))
        painter.end()


__all__ = ["Ruler", "RULER_SIZE", "PT_PER_MM", "PT_PER_IN"]
