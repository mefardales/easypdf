"""Comandos de deshacer/rehacer (QUndoStack)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtGui import QUndoCommand

from ..i18n import tr
from ..model import Annotation, Kind, rotate_annotation


class AddAnnotationCommand(QUndoCommand):
    """Anade una anotacion (y su item) al documento."""

    def __init__(self, view, ann: Annotation, item, text: str | None = None) -> None:
        super().__init__(text or tr("cmd_add", kind=tr(f"kind_{Kind(ann.kind).value}")))
        self._view = view
        self._ann = ann
        self._item = item
        self._first_redo = True

    def redo(self) -> None:
        if self._first_redo:
            # El item ya esta en la escena al crearse con el raton.
            self._first_redo = False
        else:
            self._view.attach_item(self._item, self._ann)
        self._view.store.add(self._ann)
        self._view.notify_modified()

    def undo(self) -> None:
        self._view.detach_item(self._item)
        try:
            self._view.store.remove(self._ann)
        except ValueError:  # pragma: no cover - defensivo
            pass
        self._view.notify_modified()


class DeleteAnnotationsCommand(QUndoCommand):
    """Elimina una o varias anotaciones."""

    def __init__(self, view, items: Sequence) -> None:
        label = (
            tr("cmd_delete_one") if len(items) == 1
            else tr("cmd_delete_many", count=len(items))
        )
        super().__init__(label)
        self._view = view
        self._items = list(items)

    def redo(self) -> None:
        for item in self._items:
            self._view.detach_item(item)
            try:
                self._view.store.remove(item.ann)
            except ValueError:  # pragma: no cover - defensivo
                pass
        self._view.notify_modified()

    def undo(self) -> None:
        for item in self._items:
            self._view.attach_item(item, item.ann)
            self._view.store.add(item.ann)
        self._view.notify_modified()


class EraseCommand(QUndoCommand):
    """Un pasada de goma: recorta trazos y quita lo que se borro entero.

    Todo el arrastre es un solo paso de deshacer, no uno por punto.
    """

    def __init__(self, view, changes: Sequence, removed: Sequence) -> None:
        super().__init__(tr("cmd_erase"))
        self._view = view
        # (item, trazos antes, trazos despues)
        self._changes = [(i, [list(t) for t in a], [list(t) for t in d])
                         for i, a, d in changes]
        self._removed = list(removed)
        self._skip_first_redo = True     # la goma ya lo hizo al arrastrar

    def _poner_trazos(self, item, strokes) -> None:
        item.ann.strokes = [list(t) for t in strokes]
        item.prepareGeometryChange()
        item.apply_model()
        item.update()

    def redo(self) -> None:
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        for item, _antes, despues in self._changes:
            self._poner_trazos(item, despues)
        for item in self._removed:
            self._view.detach_item(item)
            try:
                self._view.store.remove(item.ann)
            except ValueError:  # pragma: no cover - defensivo
                pass
        self._view.notify_modified()

    def undo(self) -> None:
        for item in self._removed:
            self._view.attach_item(item, item.ann)
            self._view.store.add(item.ann)
        for item, antes, _despues in self._changes:
            self._poner_trazos(item, antes)
        self._view.notify_modified()


class ChangeAnnotationsCommand(QUndoCommand):
    """Cambia geometria o estilo de anotaciones ya existentes."""

    def __init__(
        self,
        view,
        changes: Sequence[tuple[object, Annotation, Annotation]],
        text: str = "",
    ) -> None:
        super().__init__(text or tr("cmd_change"))
        self._view = view
        self._changes: list[tuple[object, Annotation, Annotation]] = list(changes)
        self._skip_first_redo = True

    def _apply(self, index: int) -> None:
        for item, before, after in self._changes:
            source = (before, after)[index]
            target = item.ann
            for field in (
                "rect", "p1", "p2", "strokes", "text", "font_size",
                "color", "fill", "width", "opacity", "page",
            ):
                setattr(target, field, getattr(source.copy(), field))
            item.prepareGeometryChange()
            item.apply_model()
            item.update()
        self._view.notify_modified()

    def redo(self) -> None:
        if self._skip_first_redo:
            # El cambio ya esta hecho por la interaccion del usuario.
            self._skip_first_redo = False
            self._view.notify_modified()
            return
        self._apply(1)

    def undo(self) -> None:
        self._apply(0)


__all__ = [
    "AddAnnotationCommand",
    "DeleteAnnotationsCommand",
    "ChangeAnnotationsCommand",
]


class AddPageCommand(QUndoCommand):
    """Anade (o duplica) una pagina del documento."""

    def __init__(self, view, index: int, size=None, duplicate: bool = False) -> None:
        super().__init__(tr("cmd_page_duplicate") if duplicate else tr("cmd_page_add"))
        self._view = view
        self._index = index
        self._size = size
        self._duplicate = duplicate

    def redo(self) -> None:
        documento = self._view.document
        if self._duplicate:
            self._index = documento.duplicate_page(self._index - 1)
        else:
            self._index = documento.add_blank_page(self._index, self._size)
        self._view.shift_annotation_pages(self._index, 1)
        self._view.refresh_pages()

    def undo(self) -> None:
        self._view.document.delete_page(self._index)
        self._view.shift_annotation_pages(self._index + 1, -1)
        self._view.refresh_pages()


class DeletePageCommand(QUndoCommand):
    """Borra una pagina y todo lo que hubiera anotado en ella."""

    def __init__(self, view, index: int) -> None:
        super().__init__(tr("cmd_page_delete", page=index + 1))
        self._view = view
        self._index = index
        self._page_data: bytes = b""
        self._items: list = []

    def redo(self) -> None:
        documento = self._view.document
        self._page_data = documento.extract_page(self._index)
        self._items = self._view.items_on_page(self._index)
        for item in self._items:
            self._view.detach_item(item)
            try:
                self._view.store.remove(item.ann)
            except ValueError:  # pragma: no cover - defensivo
                pass
        documento.delete_page(self._index)
        self._view.shift_annotation_pages(self._index + 1, -1)
        self._view.refresh_pages()

    def undo(self) -> None:
        self._view.document.insert_page_bytes(self._page_data, self._index)
        self._view.shift_annotation_pages(self._index, 1)
        for item in self._items:
            item.ann.page = self._index
            self._view.store.add(item.ann)
            self._view.attach_item(item, item.ann)
        self._view.refresh_pages()


class RotatePageCommand(QUndoCommand):
    """Gira una pagina y lleva consigo lo que hubiera anotado en ella."""

    def __init__(self, view, index: int, delta: int) -> None:
        super().__init__(tr("cmd_page_rotate", page=index + 1))
        self._view = view
        self._index = index
        self._delta = int(delta) % 360

    def _girar(self, delta: int) -> None:
        documento = self._view.document
        # El tamano de antes del giro es el que necesita la conversion de
        # coordenadas, asi que se toma primero.
        ancho, alto = documento.page_size(self._index)
        documento.set_page_rotation(
            self._index, documento.page_rotation(self._index) + delta
        )
        for ann in self._view.store:
            if ann.page == self._index:
                rotate_annotation(ann, delta, ancho, alto)
        self._view.refresh_pages()

    def redo(self) -> None:
        self._girar(self._delta)

    def undo(self) -> None:
        self._girar(-self._delta % 360)


class MovePageCommand(QUndoCommand):
    """Cambia una pagina de sitio."""

    def __init__(self, view, index: int, destino: int) -> None:
        super().__init__(tr("cmd_page_move", page=index + 1))
        self._view = view
        self._index = index
        self._destino = destino

    def _mover(self, desde: int, hasta: int) -> None:
        self._view.document.move_page(desde, hasta)
        for ann in self._view.store:
            if ann.page == desde:
                ann.page = hasta
            elif desde < ann.page <= hasta:
                ann.page -= 1
            elif hasta <= ann.page < desde:
                ann.page += 1
        self._view.refresh_pages()

    def redo(self) -> None:
        self._mover(self._index, self._destino)

    def undo(self) -> None:
        self._mover(self._destino, self._index)


__all__ += ["AddPageCommand", "DeletePageCommand", "MovePageCommand"]
