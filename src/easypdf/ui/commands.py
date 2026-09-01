"""Undo/redo commands (QUndoStack)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtGui import QUndoCommand

from ..i18n import tr
from ..model import Annotation, Kind, rotate_annotation


class AddAnnotationCommand(QUndoCommand):
    """Add an annotation (and its item) to the document."""

    def __init__(self, view, ann: Annotation, item, text: str | None = None) -> None:
        super().__init__(text or tr("cmd_add", kind=tr(f"kind_{Kind(ann.kind).value}")))
        self._view = view
        self._ann = ann
        self._item = item
        self._first_redo = True

    def redo(self) -> None:
        if self._first_redo:
            # The item is already in the scene, created with the mouse.
            self._first_redo = False
        else:
            self._view.attach_item(self._item, self._ann)
        self._view.store.add(self._ann)
        self._view.notify_modified()

    def undo(self) -> None:
        self._view.detach_item(self._item)
        try:
            self._view.store.remove(self._ann)
        except ValueError:  # pragma: no cover - defensive
            pass
        self._view.notify_modified()


class DeleteAnnotationsCommand(QUndoCommand):
    """Delete one or several annotations."""

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
            except ValueError:  # pragma: no cover - defensive
                pass
        self._view.notify_modified()

    def undo(self) -> None:
        for item in self._items:
            self._view.attach_item(item, item.ann)
            self._view.store.add(item.ann)
        self._view.notify_modified()


class ChangeAnnotationsCommand(QUndoCommand):
    """Change the geometry or style of existing annotations."""

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
            # The change is already done by the user's interaction.
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
    """Add (or duplicate) a page of the document."""

    def __init__(self, view, index: int, size=None, duplicate: bool = False) -> None:
        super().__init__(tr("cmd_page_duplicate") if duplicate else tr("cmd_page_add"))
        self._view = view
        self._index = index
        self._size = size
        self._duplicate = duplicate

    def redo(self) -> None:
        document = self._view.document
        if self._duplicate:
            self._index = document.duplicate_page(self._index - 1)
        else:
            self._index = document.add_blank_page(self._index, self._size)
        self._view.shift_annotation_pages(self._index, 1)
        self._view.refresh_pages()

    def undo(self) -> None:
        self._view.document.delete_page(self._index)
        self._view.shift_annotation_pages(self._index + 1, -1)
        self._view.refresh_pages()


class DeletePageCommand(QUndoCommand):
    """Delete a page and everything annotated on it."""

    def __init__(self, view, index: int) -> None:
        super().__init__(tr("cmd_page_delete", page=index + 1))
        self._view = view
        self._index = index
        self._page_data: bytes = b""
        self._items: list = []

    def redo(self) -> None:
        document = self._view.document
        self._page_data = document.extract_page(self._index)
        self._items = self._view.items_on_page(self._index)
        for item in self._items:
            self._view.detach_item(item)
            try:
                self._view.store.remove(item.ann)
            except ValueError:  # pragma: no cover - defensive
                pass
        document.delete_page(self._index)
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
    """Rotate a page, taking whatever is annotated on it along."""

    def __init__(self, view, index: int, delta: int) -> None:
        super().__init__(tr("cmd_page_rotate", page=index + 1))
        self._view = view
        self._index = index
        self._delta = int(delta) % 360

    def _rotate(self, delta: int) -> None:
        document = self._view.document
        # The size from before the rotation is what the coordinate
        # conversion needs, so it is read first.
        width, height = document.page_size(self._index)
        document.set_page_rotation(
            self._index, document.page_rotation(self._index) + delta
        )
        for ann in self._view.store:
            if ann.page == self._index:
                rotate_annotation(ann, delta, width, height)
        self._view.refresh_pages()

    def redo(self) -> None:
        self._rotate(self._delta)

    def undo(self) -> None:
        self._rotate(-self._delta % 360)


class MovePageCommand(QUndoCommand):
    """Move a page somewhere else."""

    def __init__(self, view, index: int, target: int) -> None:
        super().__init__(tr("cmd_page_move", page=index + 1))
        self._view = view
        self._index = index
        self._target = target

    def _move(self, source: int, target: int) -> None:
        self._view.document.move_page(source, target)
        for ann in self._view.store:
            if ann.page == source:
                ann.page = target
            elif source < ann.page <= target:
                ann.page -= 1
            elif target <= ann.page < source:
                ann.page += 1
        self._view.refresh_pages()

    def redo(self) -> None:
        self._move(self._index, self._target)

    def undo(self) -> None:
        self._move(self._target, self._index)


__all__ += ["AddPageCommand", "DeletePageCommand", "MovePageCommand"]
