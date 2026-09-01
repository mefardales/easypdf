"""Annotation data model.

This module is plain Python: it depends on neither Qt nor PyMuPDF, so the
logic can be tested without a graphical interface.

Coordinate system
-----------------
Every coordinate is stored in **PDF points** (1 pt = 1/72 inch), with the
origin at the top-left corner of the page and the Y axis growing downwards.
That is the same system PyMuPDF's ``page.rect`` uses and the one seen on
screen, so no zoom conversion ever gets baked into the model.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

RGB = tuple[float, float, float]
Point = tuple[float, float]
Rect = tuple[float, float, float, float]  # x0, y0, x1, y1


class Kind(str, Enum):
    """Annotation types easypdf.surf knows how to create."""

    RECT = "rect"
    HIGHLIGHT = "highlight"
    LINE = "line"
    ARROW = "arrow"
    TEXT = "text"
    INK = "ink"
    TABLE = "table"
    IMAGE = "image"
    NOTE = "note"
    #: An eraser stroke. Stored like an ink stroke, but it is not drawn when
    #: the file is saved: it is used to really remove whatever lies beneath.
    ERASE = "erase"

    @property
    def label(self) -> str:
        return {
            Kind.RECT: "Box",
            Kind.HIGHLIGHT: "Highlight",
            Kind.LINE: "Line",
            Kind.ARROW: "Arrow",
            Kind.TEXT: "Text",
            Kind.INK: "Drawing",
            Kind.ERASE: "Erasure",
            Kind.TABLE: "Table",
            Kind.IMAGE: "Image",
            Kind.NOTE: "Note",
        }[self]


class Font(str, Enum):
    """Families every PDF reader can draw without embedding anything."""

    SANS = "helv"
    SERIF = "tiro"
    MONO = "cour"

    @property
    def label(self) -> str:
        return {Font.SANS: "Sans", Font.SERIF: "Serif", Font.MONO: "Monospace"}[self]

    @property
    def qt_family(self) -> str:
        return {
            Font.SANS: "Helvetica",
            Font.SERIF: "Times New Roman",
            Font.MONO: "Courier New",
        }[self]


class Align(int, Enum):
    """Text alignment (the same values the PDF format uses)."""

    LEFT = 0
    CENTER = 1
    RIGHT = 2

    @property
    def label(self) -> str:
        return {Align.LEFT: "Left", Align.CENTER: "Centre", Align.RIGHT: "Right"}[self]


def _new_id() -> str:
    return uuid.uuid4().hex


#: Arrow head proportions. They are the same on screen, on paper and in the
#: saved file: PyMuPDF draws the standard PDF arrow heads ten times bigger
#: than the line width, which looks out of proportion with thick strokes, so
#: easypdf.surf draws its own head instead.
ARROW_HEAD_MIN = 11.0    # minimum length, in points
ARROW_HEAD_FACTOR = 5.0  # times the line width
ARROW_HEAD_RATIO = 0.50  # half-width relative to the length


def arrow_head(p1: Point, p2: Point, width: float) -> tuple[Point, Point, Point, Point]:
    """Geometry of the head of an arrow going from ``p1`` to ``p2``.

    Returns ``(base, tip, left, right)``: the base is where the line has to
    stop so the stroke does not poke out in front of the head.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    line_length = math.hypot(dx, dy)
    length = max(ARROW_HEAD_MIN, max(0.1, width) * ARROW_HEAD_FACTOR)
    if line_length < 1e-6:
        return (p2, p2, p2, p2)
    length = min(length, line_length)        # never longer than the line itself
    ux, uy = dx / line_length, dy / line_length
    base = (p2[0] - ux * length, p2[1] - uy * length)
    half = length * ARROW_HEAD_RATIO
    nx, ny = -uy, ux
    left = (base[0] + nx * half, base[1] + ny * half)
    right = (base[0] - nx * half, base[1] - ny * half)
    return (base, p2, left, right)


def arrow_line_end(p1: Point, p2: Point, width: float) -> Point:
    """Point where an arrow's stroke ends (inside the head)."""
    base, tip, _, _ = arrow_head(p1, p2, width)
    return ((base[0] + tip[0]) / 2.0, (base[1] + tip[1]) / 2.0)


def rotate_point(point: Point, degrees: int, width: float, height: float) -> Point:
    """Rotate a point along with its page.

    ``width`` and ``height`` are the page's **before** rotating, and
    ``degrees`` the clockwise rotation (90, 180 or 270). At 90 and 270 the
    page changes orientation, so the point moves onto a ``height`` x ``width``
    canvas.
    """
    x, y = point
    turn = degrees % 360
    if turn == 90:
        return (height - y, x)
    if turn == 180:
        return (width - x, height - y)
    if turn == 270:
        return (y, width - x)
    return (x, y)


def rotate_annotation(ann: Annotation, degrees: int, width: float, height: float) -> None:
    """Rotate an annotation with its page, in place.

    Text is not tilted: the box moves where it belongs but the letters keep
    reading horizontally, which is all a PDF FreeText can draw without
    embedding an appearance stream of its own.
    """
    if degrees % 360 == 0:
        return

    def turn(p: Point) -> Point:
        return rotate_point(p, degrees, width, height)

    x0, y0, x1, y1 = ann.rect
    (a, b), (c, d) = turn((x0, y0)), turn((x1, y1))
    ann.rect = (min(a, c), min(b, d), max(a, c), max(b, d))
    ann.p1 = turn(ann.p1)
    ann.p2 = turn(ann.p2)
    ann.strokes = [[turn(p) for p in stroke] for stroke in ann.strokes]


def move_annotation(ann: Annotation, dx: float, dy: float) -> None:
    """Shift an annotation in place, with everything that makes it up.

    All three representations have to move: the rectangle (boxes, texts,
    tables and images), the end points (lines and arrows) and the strokes
    (ink and eraser). Moving only the rectangle would leave the line behind.
    """
    if not dx and not dy:
        return
    x0, y0, x1, y1 = ann.rect
    ann.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
    ann.p1 = (ann.p1[0] + dx, ann.p1[1] + dy)
    ann.p2 = (ann.p2[0] + dx, ann.p2[1] + dy)
    ann.strokes = [[(x + dx, y + dy) for x, y in stroke] for stroke in ann.strokes]


def _walk_stroke(stroke, step: float):
    """Walk a stroke yielding a point every ``step``, not just the vertices.

    A fast drag leaves the points far apart: without filling the gaps the
    eraser would pass over something without noticing.
    """
    if not stroke:
        return
    yield stroke[0]
    for (x0, y0), (x1, y1) in zip(stroke, stroke[1:]):
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        pieces = int(length / step)
        for i in range(1, pieces + 1):
            f = i / (pieces + 1)
            yield (x0 + dx * f, y0 + dy * f)
        yield (x1, y1)


def stroke_touches(strokes, width: float, rect: Rect) -> bool:
    """True if a stroke ``width`` points thick passes over ``rect``."""
    radius = max(0.5, float(width) / 2.0)
    x0, y0, x1, y1 = rect
    left, right = min(x0, x1) - radius, max(x0, x1) + radius
    top, bottom = min(y0, y1) - radius, max(y0, y1) + radius
    for stroke in strokes:
        for x, y in _walk_stroke(stroke, radius):
            if left <= x <= right and top <= y <= bottom:
                return True
    return False


def stroke_boxes(strokes, width: float) -> list[Rect]:
    """Rectangles a stroke covers, so what is underneath can be erased."""
    radius = max(0.5, float(width) / 2.0)
    boxes: list[Rect] = []
    for stroke in strokes:
        for (x0, y0), (x1, y1) in zip(stroke, stroke[1:]):
            boxes.append((min(x0, x1) - radius, min(y0, y1) - radius,
                          max(x0, x1) + radius, max(y0, y1) + radius))
        if len(stroke) == 1:            # a single tap erases too
            x, y = stroke[0]
            boxes.append((x - radius, y - radius, x + radius, y + radius))
    return boxes


#: Eraser sizes, in PDF points. Ctrl+ and Ctrl- walk this list.
ERASER_SIZES = (6.0, 10.0, 16.0, 24.0, 36.0, 54.0, 80.0)
ERASER_DEFAULT = 16.0


#: How close (in screen pixels) the magnet starts pulling.
SNAP_PIXELS = 6.0


def snap_offset(
    anchors: Sequence[float], candidates: Sequence[float], threshold: float
) -> tuple[float, float | None]:
    """How far to shift to stick an edge to one of the guides.

    ``anchors`` are the edges and centre of whatever is being moved;
    ``candidates`` the lines it can align to. Returns ``(offset, guide used)``,
    or ``(0.0, None)`` if nothing is close enough.
    """
    best_delta, best_guide, best_distance = 0.0, None, threshold
    for anchor in anchors:
        for guide in candidates:
            distance = abs(guide - anchor)
            if distance < best_distance:
                best_distance, best_delta, best_guide = distance, guide - anchor, guide
    return (best_delta, best_guide)


@dataclass
class Annotation:
    """An annotation placed on top of a page.

    Depending on ``kind`` some fields are used and others are not:

    * ``RECT`` / ``HIGHLIGHT`` / ``TEXT``  -> ``rect``
    * ``LINE`` / ``ARROW``                 -> ``p1`` and ``p2``
    * ``INK``                              -> ``strokes``
    * ``TEXT``                             -> plus ``text``, ``font_size``
    """

    kind: Kind
    page: int
    rect: Rect = (0.0, 0.0, 0.0, 0.0)
    p1: Point = (0.0, 0.0)
    p2: Point = (0.0, 0.0)
    strokes: list[list[Point]] = field(default_factory=list)
    text: str = ""
    font_size: float = 12.0
    font: Font = Font.SANS
    bold: bool = False
    italic: bool = False
    align: Align = Align.LEFT
    rows: int = 3
    cols: int = 3
    cells: list[str] = field(default_factory=list)
    image_data: bytes = b""
    image_name: str = ""
    done: bool = False          # note already read
    color: RGB = (0.85, 0.10, 0.10)
    fill: RGB | None = None
    width: float = 1.5
    opacity: float = 1.0
    id: str = field(default_factory=_new_id)

    # -- helpers ---------------------------------------------------------
    def copy(self) -> Annotation:
        """Independent copy (strokes and cells included)."""
        return replace(
            self,
            strokes=[list(stroke) for stroke in self.strokes],
            cells=list(self.cells),
        )

    def normalized_rect(self) -> Rect:
        x0, y0, x1, y1 = self.rect
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def bounds(self) -> Rect:
        """Bounding rectangle, whatever the type."""
        if self.kind in (Kind.LINE, Kind.ARROW):
            (x0, y0), (x1, y1) = self.p1, self.p2
            return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if self.kind in (Kind.INK, Kind.ERASE):
            points = [p for stroke in self.strokes for p in stroke]
            if not points:
                return (0.0, 0.0, 0.0, 0.0)
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            return (min(xs), min(ys), max(xs), max(ys))
        return self.normalized_rect()

    def translate(self, dx: float, dy: float) -> None:
        """Shift the annotation (in PDF points)."""
        x0, y0, x1, y1 = self.rect
        self.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        self.p1 = (self.p1[0] + dx, self.p1[1] + dy)
        self.p2 = (self.p2[0] + dx, self.p2[1] + dy)
        self.strokes = [[(x + dx, y + dy) for x, y in s] for s in self.strokes]

    # -- tables ----------------------------------------------------------
    def cell_count(self) -> int:
        return max(1, self.rows) * max(1, self.cols)

    def normalized_cells(self) -> list[str]:
        """Cell texts, always exactly as many as the grid has cells."""
        total = self.cell_count()
        cells = list(self.cells)[:total]
        cells += [""] * (total - len(cells))
        return cells

    def cell_rects(self) -> list[Rect]:
        """Rectangle of every cell, in reading order."""
        x0, y0, x1, y1 = self.normalized_rect()
        rows, columns = max(1, self.rows), max(1, self.cols)
        height = (y1 - y0) / rows
        width = (x1 - x0) / columns
        return [
            (x0 + c * width, y0 + r * height, x0 + (c + 1) * width, y0 + (r + 1) * height)
            for r in range(rows)
            for c in range(columns)
        ]

    def grid_lines(self) -> list[tuple[Point, Point]]:
        """A table's lines: the border and the inner dividers."""
        x0, y0, x1, y1 = self.normalized_rect()
        rows, columns = max(1, self.rows), max(1, self.cols)
        lines: list[tuple[Point, Point]] = []
        for r in range(rows + 1):
            y = y0 + (y1 - y0) * r / rows
            lines.append(((x0, y), (x1, y)))
        for c in range(columns + 1):
            x = x0 + (x1 - x0) * c / columns
            lines.append(((x, y0), (x, y1)))
        return lines

    def is_empty(self) -> bool:
        """True if the annotation has no useful size and should be dropped."""
        if self.kind in (Kind.INK, Kind.ERASE):
            return not any(len(s) >= 2 for s in self.strokes)
        if self.kind in (Kind.LINE, Kind.ARROW):
            dx = self.p2[0] - self.p1[0]
            dy = self.p2[1] - self.p1[1]
            return (dx * dx + dy * dy) < 4.0
        x0, y0, x1, y1 = self.normalized_rect()
        if self.kind is Kind.NOTE:
            return False      # the icon has a fixed size, it is never too small
        if self.kind is Kind.IMAGE and not self.image_data:
            return True
        if self.kind in (Kind.TEXT, Kind.TABLE, Kind.IMAGE):
            return (x1 - x0) < 2.0 or (y1 - y0) < 2.0
        return (x1 - x0) < 2.0 and (y1 - y0) < 2.0


class AnnotationStore:
    """Ordered collection of the open document's annotations."""

    def __init__(self, annotations: Iterable[Annotation] | None = None) -> None:
        self._items: list[Annotation] = list(annotations or [])

    # -- collection ------------------------------------------------------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Annotation]:
        return iter(self._items)

    def __contains__(self, ann: object) -> bool:
        return any(a is ann for a in self._items)

    @property
    def items(self) -> Sequence[Annotation]:
        return tuple(self._items)

    # -- operations ------------------------------------------------------
    def add(self, ann: Annotation, index: int | None = None) -> Annotation:
        if index is None:
            self._items.append(ann)
        else:
            self._items.insert(index, ann)
        return ann

    def remove(self, ann: Annotation) -> int:
        """Remove an annotation and return the position it held."""
        for i, item in enumerate(self._items):
            if item is ann or item.id == ann.id:
                del self._items[i]
                return i
        raise ValueError("the annotation does not belong to this document")

    def clear(self) -> None:
        self._items.clear()

    def for_page(self, page: int) -> list[Annotation]:
        return [a for a in self._items if a.page == page]

    def pages_used(self) -> list[int]:
        return sorted({a.page for a in self._items})
