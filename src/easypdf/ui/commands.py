"""Comandos de deshacer/rehacer (QUndoStack)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtGui import QUndoCommand

from ..model import Annotation


class AddAnnotationCommand(QUndoCommand):
    """Anade una anotacion (y su item) al documento."""

    def __init__(self, view, ann: Annotation, item, text: str | None = None) -> None:
        super().__init__(text or f"Anadir {ann.kind.label.lower()}")
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
        label = "Eliminar anotacion" if len(items) == 1 else f"Eliminar {len(items)} anotaciones"
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


class ChangeAnnotationsCommand(QUndoCommand):
    """Cambia geometria o estilo de anotaciones ya existentes."""

    def __init__(
        self,
        view,
        changes: Sequence[tuple[object, Annotation, Annotation]],
        text: str = "Modificar anotacion",
    ) -> None:
        super().__init__(text)
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
        super().__init__("Duplicar pagina" if duplicate else "Anadir pagina")
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
        super().__init__(f"Eliminar la pagina {index + 1}")
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


class MovePageCommand(QUndoCommand):
    """Cambia una pagina de sitio."""

    def __init__(self, view, index: int, destino: int) -> None:
        super().__init__(f"Mover la pagina {index + 1}")
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
