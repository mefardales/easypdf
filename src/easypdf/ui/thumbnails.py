"""Thumbnail panel with drag-to-reorder.

The list never moves its own items: when a drag is dropped it reports it with
``page_moved`` and the window is the one that really moves the page, through
the undo stack. That way the thumbnails and the document cannot drift apart,
and the drag is undone with Ctrl+Z like any other change.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem


class ThumbnailList(QListWidget):
    """List of thumbnails that can be reordered by dragging."""

    #: Emitted when a drag is dropped: (source position, target position).
    page_moved = Signal(int, int)

    def __init__(self, width: int, parent=None) -> None:
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(width, int(width * 1.5)))
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Snap)
        self.setSpacing(6)
        self.setUniformItemSizes(False)
        self.setWordWrap(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        # Internal drag, used to reorder the pages.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    # -- dragging --------------------------------------------------------
    def drop_row(self, pos) -> int:
        """Position a drag dropped at ``pos`` would land on."""
        if self.count() == 0:
            return 0
        index = self.indexAt(pos)
        # There is a gap between two thumbnails, and dropping right there is
        # the natural gesture for "put it here". indexAt returns nothing in
        # that gap, so the nearest thumbnail is looked up instead of giving
        # the position up for lost: the page used to be sent to the very end.
        row = index.row() if index.isValid() else self.nearest_row(pos)
        rect = self.visualRect(self.model().index(row, 0))
        # Dropping on the bottom (or right) half of a thumbnail puts the page
        # after it, which is what whoever is dragging expects.
        if self.stacked_vertically():
            after = pos.y() > rect.center().y()
        else:
            after = pos.x() > rect.center().x()
        return row + 1 if after else row

    def nearest_row(self, pos) -> int:
        """Thumbnail closest to a point, even if the point falls in a gap."""
        vertical = self.stacked_vertically()
        best, best_distance = 0, None
        for row in range(self.count()):
            rect = self.visualRect(self.model().index(row, 0))
            if vertical:
                start, end, point = rect.top(), rect.bottom(), pos.y()
            else:
                start, end, point = rect.left(), rect.right(), pos.x()
            if point < start:
                distance = start - point
            elif point > end:
                distance = point - end
            else:
                distance = 0
            if best_distance is None or distance < best_distance:
                best, best_distance = row, distance
                if distance == 0:
                    break
        return best

    def stacked_vertically(self) -> bool:
        """True if the thumbnails run one below the other.

        Icon mode declares a horizontal flow, but in a narrow panel only one
        thumbnail fits per row and they stack vertically, which is how the
        user drags them. The real spacing between the first two is measured
        instead of trusting flow().
        """
        if self.count() < 2:
            return True
        first = self.visualRect(self.model().index(0, 0))
        second = self.visualRect(self.model().index(1, 0))
        return abs(second.top() - first.top()) >= abs(second.left() - first.left())

    def dropEvent(self, event) -> None:  # pragma: no cover - mouse gesture
        source = self.currentRow()
        target = self.drop_row(event.position().toPoint())
        # Qt does not touch the list: it is rebuilt after moving the page.
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        if source < 0:
            return
        if target > source:
            target -= 1                      # the page itself frees its slot
        target = max(0, min(target, self.count() - 1))
        if target != source:
            self.page_moved.emit(source, target)

    # -- helpers ---------------------------------------------------------
    def add_page_item(self, number: int, icon) -> QListWidgetItem:
        item = QListWidgetItem(icon, str(number))
        item.setTextAlignment(Qt.AlignHCenter)
        self.addItem(item)
        return item


__all__ = ["ThumbnailList"]
