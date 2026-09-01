"""Individual pieces for building forms.

Templates bring whole documents; these are the bricks they are built from:
a field with its rule, a tick box, a signature line, a table. They are
dropped wherever the user is looking and from then on they are edited and
moved like any other annotation, because that is what they are.

They do not depend on Qt on purpose: they are document data, just like
templates.py, so they can be tested without opening a window.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Align, Annotation, Kind
from .templates import GREY, INK, RULE, _t

#: Default width of a piece, in PDF points. It fits comfortably on an A4
#: with margins and leaves room to put two side by side.
WIDTH = 240.0

#: Side of a tick box.
BOX = 11.0

#: Groups the pieces are shown in.
CATEGORIES = ("field", "choice", "signature", "layout")


@dataclass(frozen=True)
class ElementInfo:
    """A piece of the catalogue: its key, translated name and group."""

    key: str
    name: str
    category: str


#: key -> category. This order is the one shown in the panel.
ELEMENTS: dict[str, str] = {
    "text_field": "field",
    "long_field": "field",
    "date_field": "field",
    "boxed_field": "field",
    "checkbox": "choice",
    "checklist": "choice",
    "yes_no": "choice",
    "signature": "signature",
    "two_signatures": "signature",
    "place_date": "signature",
    "heading": "layout",
    "separator": "layout",
    "table": "layout",
    "note_box": "layout",
}


def element_infos() -> list[ElementInfo]:
    """The whole catalogue, with names in the interface language."""
    from .i18n import tr

    return [ElementInfo(key, tr(f"el_{key}"), group)
            for key, group in ELEMENTS.items()]


# ------------------------------------------------------------------ pieces
def _text(x, y, width, height, text, size=10.0, bold=False,
          align=Align.LEFT, color=INK) -> Annotation:
    return Annotation(
        kind=Kind.TEXT, page=0, rect=(x, y, x + width, y + height), text=text,
        font_size=size, bold=bold, align=align, color=color, width=0.0,
    )


def _rule(x0, y, x1, color=RULE, thickness=0.8) -> Annotation:
    return Annotation(kind=Kind.LINE, page=0, p1=(x0, y), p2=(x1, y),
                      color=color, width=thickness)


def _box(x, y, width, height, color=RULE, thickness=0.8) -> Annotation:
    return Annotation(kind=Kind.RECT, page=0, rect=(x, y, x + width, y + height),
                      color=color, width=thickness)


def _field(x, y, width, label) -> list[Annotation]:
    """Label on top and a rule below, which is how you fill one in by hand."""
    return [_text(x, y, width, 12, label, 9, color=GREY),
            _rule(x, y + 26, x + width)]


def _tick(x, y, label, width=WIDTH) -> list[Annotation]:
    # The box drops 2 pt to sit centred against the height of the letters. It
    # is the box that moves and not the text: that way the piece starts
    # exactly at (x, y) and can be placed without surprises.
    return [_box(x, y + 2, BOX, BOX),
            _text(x + BOX + 8, y, width - BOX - 8, 15, label)]


def _signature(x, y, width, caption) -> list[Annotation]:
    # The rule sits right at (x, y): the room to sign is whatever is above it,
    # and the user decides that when dropping the piece. Reserving it here
    # only meant the piece did not land where it was asked to.
    return [_rule(x, y, x + width),
            _text(x, y + 4, width, 12, caption, 9, align=Align.CENTER, color=GREY)]


def build(key: str, x: float, y: float, width: float = WIDTH) -> list[Annotation]:
    """Create the piece with its top-left corner at (x, y).

    Returns a list of annotations already placed, on page 0: whoever inserts
    them is responsible for setting the page they belong to.
    """
    span = max(60.0, float(width))
    half = (span - 20.0) / 2.0

    if key == "text_field":
        return _field(x, y, span, _t("label"))
    if key == "long_field":
        pieces = [_text(x, y, span, 12, _t("label"), 9, color=GREY)]
        for row in range(3):
            pieces.append(_rule(x, y + 26 + row * 22, x + span))
        return pieces
    if key == "date_field":
        return _field(x, y, min(span, 150.0), _t("date"))
    if key == "boxed_field":
        return [_text(x, y, span, 12, _t("label"), 9, color=GREY),
                _box(x, y + 16, span, 56)]
    if key == "checkbox":
        return _tick(x, y, _t("option"), span)
    if key == "checklist":
        pieces: list[Annotation] = []
        for row in range(4):
            pieces += _tick(x, y + row * 22, f"{_t('option')} {row + 1}", span)
        return pieces
    if key == "yes_no":
        return _tick(x, y, _t("yes"), half) + _tick(x + half + 20, y, _t("no"), half)
    if key == "signature":
        return _signature(x, y, span, _t("signature"))
    if key == "two_signatures":
        return _signature(x, y, half, _t("signature")) + _signature(
            x + half + 20, y, half, _t("signature")
        )
    if key == "place_date":
        return _field(x, y, half, _t("place")) + _field(x + half + 20, y, half, _t("date"))
    if key == "heading":
        return [_text(x, y, span, 20, _t("heading"), 13, True),
                _rule(x, y + 24, x + span, INK, 1.0)]
    if key == "separator":
        return [_rule(x, y, x + span)]
    if key == "table":
        headers = [_t("concept"), _t("qty"), _t("value")]
        return [Annotation(
            kind=Kind.TABLE, page=0, rect=(x, y, x + span, y + 96),
            rows=4, cols=3, cells=headers + [""] * 9,
            align=Align.LEFT, width=0.8, color=INK,
        )]
    if key == "note_box":
        return [_text(x, y, span, 12, _t("notes_short"), 9, color=GREY),
                _box(x, y + 16, span, 80)]
    raise KeyError(f"there is no piece called {key!r}")


def size_of(key: str) -> tuple[float, float]:
    """How much room a piece takes, so it can be centred when inserted."""
    pieces = build(key, 0.0, 0.0)
    x0 = min(min(a.bounds()[0], a.bounds()[2]) for a in pieces)
    y0 = min(min(a.bounds()[1], a.bounds()[3]) for a in pieces)
    x1 = max(max(a.bounds()[0], a.bounds()[2]) for a in pieces)
    y1 = max(max(a.bounds()[1], a.bounds()[3]) for a in pieces)
    return (x1 - x0, y1 - y0)


__all__ = ["BOX", "CATEGORIES", "ELEMENTS", "ElementInfo", "WIDTH", "build",
           "element_infos", "size_of"]
