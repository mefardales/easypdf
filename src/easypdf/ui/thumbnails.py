"""Panel de miniaturas con reordenacion por arrastre.

La lista no mueve nunca sus propios elementos: cuando se suelta un arrastre
avisa con ``page_moved`` y es la ventana quien mueve la pagina de verdad, a
traves de la pila de deshacer. Asi las miniaturas y el documento no se pueden
desincronizar, y el arrastre se deshace con Ctrl+Z como cualquier otro cambio.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem


class ThumbnailList(QListWidget):
    """Lista de miniaturas que se pueden reordenar arrastrando."""

    #: Se emite al soltar un arrastre: (posicion de origen, posicion de destino).
    page_moved = Signal(int, int)

    def __init__(self, ancho: int, parent=None) -> None:
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(ancho, int(ancho * 1.5)))
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Snap)
        self.setSpacing(6)
        self.setUniformItemSizes(False)
        self.setWordWrap(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        # Arrastre interno para reordenar las paginas.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    # -- arrastre --------------------------------------------------------
    def drop_row(self, pos) -> int:
        """Posicion en la que caeria un arrastre soltado en ``pos``."""
        if self.count() == 0:
            return 0
        indice = self.indexAt(pos)
        # Entre dos miniaturas hay un hueco de separacion, y soltar justo ahi
        # es el gesto natural para decir "ponla aqui". Ahi indexAt no devuelve
        # nada, asi que se busca la miniatura mas cercana en vez de dar la
        # posicion por perdida: antes se mandaba la pagina al final de todas.
        fila = indice.row() if indice.isValid() else self.nearest_row(pos)
        rect = self.visualRect(self.model().index(fila, 0))
        # Soltar en la mitad de abajo (o derecha) de una miniatura coloca la
        # pagina detras de ella, que es lo que espera quien la esta arrastrando.
        if self.stacked_vertically():
            despues = pos.y() > rect.center().y()
        else:
            despues = pos.x() > rect.center().x()
        return fila + 1 if despues else fila

    def nearest_row(self, pos) -> int:
        """Miniatura mas cercana a un punto, aunque el punto caiga en un hueco."""
        vertical = self.stacked_vertically()
        mejor, mejor_distancia = 0, None
        for fila in range(self.count()):
            rect = self.visualRect(self.model().index(fila, 0))
            if vertical:
                inicio, fin, punto = rect.top(), rect.bottom(), pos.y()
            else:
                inicio, fin, punto = rect.left(), rect.right(), pos.x()
            if punto < inicio:
                distancia = inicio - punto
            elif punto > fin:
                distancia = punto - fin
            else:
                distancia = 0
            if mejor_distancia is None or distancia < mejor_distancia:
                mejor, mejor_distancia = fila, distancia
                if distancia == 0:
                    break
        return mejor

    def stacked_vertically(self) -> bool:
        """True si las miniaturas van una debajo de otra.

        El modo icono declara un flujo horizontal, pero en un panel estrecho
        solo cabe una miniatura por fila y se apilan en vertical, que es como
        el usuario las arrastra. Se mira la separacion real entre las dos
        primeras en vez de fiarse de flow().
        """
        if self.count() < 2:
            return True
        r0 = self.visualRect(self.model().index(0, 0))
        r1 = self.visualRect(self.model().index(1, 0))
        return abs(r1.top() - r0.top()) >= abs(r1.left() - r0.left())

    def dropEvent(self, event) -> None:  # pragma: no cover - gesto de raton
        origen = self.currentRow()
        destino = self.drop_row(event.position().toPoint())
        # Qt no toca la lista: se reconstruye entera tras mover la pagina.
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        if origen < 0:
            return
        if destino > origen:
            destino -= 1                     # la propia pagina deja su hueco
        destino = max(0, min(destino, self.count() - 1))
        if destino != origen:
            self.page_moved.emit(origen, destino)

    # -- utilidades ------------------------------------------------------
    def add_page_item(self, numero: int, icono) -> QListWidgetItem:
        item = QListWidgetItem(icono, str(numero))
        item.setTextAlignment(Qt.AlignHCenter)
        self.addItem(item)
        return item


__all__ = ["ThumbnailList"]
