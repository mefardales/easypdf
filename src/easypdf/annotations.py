"""Translation of the easypdf.surf model into real PDF annotations (PyMuPDF).

Annotations are written as standard PDF objects (Square, Line, FreeText, Ink,
Highlight), so any other reader - Adobe Reader, Edge, Firefox - shows them the
same way and they stay selectable.
"""

from __future__ import annotations

import html
from collections.abc import Iterable

import pymupdf

from .model import Align, Annotation, Font, Kind, arrow_head, stroke_boxes

#: Name stored in the annotation's /T field.
AUTHOR = "easypdf.surf"

#: Names of the 14 base PDF fonts: every reader has them, so nothing needs
#: embedding in the file.
FONT_CODES = {
    (Font.SANS, False, False): "helv",
    (Font.SANS, True, False): "hebo",
    (Font.SANS, False, True): "heit",
    (Font.SANS, True, True): "hebi",
    (Font.SERIF, False, False): "tiro",
    (Font.SERIF, True, False): "tibo",
    (Font.SERIF, False, True): "tiit",
    (Font.SERIF, True, True): "tibi",
    (Font.MONO, False, False): "cour",
    (Font.MONO, True, False): "cobo",
    (Font.MONO, False, True): "coit",
    (Font.MONO, True, True): "cobi",
}

#: Padding between a cell border and its text, in points.
CELL_PADDING = 2.5

#: Equivalent CSS families, for bold or italic text.
CSS_FAMILIES = {Font.SANS: "sans-serif", Font.SERIF: "serif", Font.MONO: "monospace"}

CSS_ALIGN = {Align.LEFT: "left", Align.CENTER: "center", Align.RIGHT: "right"}


def font_code(ann: Annotation) -> str:
    """PDF font name for a family plus bold and italic."""
    return FONT_CODES.get((Font(ann.font), bool(ann.bold), bool(ann.italic)), "helv")


def _hex_color(rgb) -> str:
    r, g, b = (int(round(_clamp01(c) * 255)) for c in (rgb or (0, 0, 0)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _rich_html(ann: Annotation, text: str) -> str:
    """Simple HTML text for bold and italic."""
    body = html.escape(text).replace("\n", "<br>")
    if ann.bold:
        body = f"<b>{body}</b>"
    if ann.italic:
        body = f"<i>{body}</i>"
    return body


def _add_freetext(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    ann: Annotation,
    text: str,
    border_width: float,
    fill: bool = True,
) -> pymupdf.Annot:
    """Free text with family, size, alignment and, where needed, bold/italic.

    PyMuPDF ignores the bold and italic variants in plain text (they all end
    up drawn with the base font), so in that case the rich text mode is used,
    where they are honoured.
    """
    fill_color = _color(ann.fill) if fill else None
    if ann.bold or ann.italic:
        style = (
            f"font-family:{CSS_FAMILIES.get(Font(ann.font), 'sans-serif')};"
            f"font-size:{max(1.0, ann.font_size):g}px;"
            f"color:{_hex_color(ann.color)};"
            f"text-align:{CSS_ALIGN.get(Align(ann.align), 'left')}"
        )
        annot = page.add_freetext_annot(
            rect,
            _rich_html(ann, text),
            fontsize=max(1.0, ann.font_size),
            fill_color=fill_color,
            border_width=border_width,
            opacity=_clamp01(ann.opacity),
            richtext=True,
            style=style,
        )
        return annot
    return page.add_freetext_annot(
        rect,
        text,
        fontsize=max(1.0, ann.font_size),
        fontname=font_code(ann),
        align=int(Align(ann.align)),
        text_color=_color(ann.color),
        fill_color=fill_color,
        border_width=border_width,
        opacity=_clamp01(ann.opacity),
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _color(rgb: Iterable[float] | None) -> list[float] | None:
    if rgb is None:
        return None
    return [_clamp01(c) for c in rgb]


def _set_plain_content(annot: pymupdf.Annot, text: str) -> None:
    """Store the plain text without rebuilding the annotation appearance.

    In rich text the content travels as HTML. Using set_info() to also leave
    it in plain form would make PyMuPDF regenerate the appearance from that
    plain text, losing bold and italic, so it is written straight into the
    PDF object.
    """
    try:
        annot.parent.parent.xref_set_key(annot.xref, "Contents", pymupdf.get_pdf_str(text))
    except Exception:  # pragma: no cover - depends on the PyMuPDF version
        pass


def _apply_common(annot: pymupdf.Annot, ann: Annotation) -> None:
    """Common settings: opacity, author and appearance."""
    annot.set_opacity(_clamp01(ann.opacity))
    try:
        annot.set_info(title=AUTHOR)
    except Exception:  # pragma: no cover - depends on the PyMuPDF version
        pass
    annot.update()


def _rect(ann: Annotation, page: pymupdf.Page) -> pymupdf.Rect:
    x0, y0, x1, y1 = ann.normalized_rect()
    rect = pymupdf.Rect(x0, y0, x1, y1) * page.derotation_matrix
    return pymupdf.Rect(rect).normalize()


def _point(pt, page: pymupdf.Page) -> pymupdf.Point:
    return pymupdf.Point(pt[0], pt[1]) * page.derotation_matrix


def add_annotation(page: pymupdf.Page, ann: Annotation) -> pymupdf.Annot:
    """Add a model annotation to a PyMuPDF page."""
    if ann.kind is Kind.RECT:
        annot = page.add_rect_annot(_rect(ann, page))
        annot.set_colors(stroke=_color(ann.color), fill=_color(ann.fill))
        annot.set_border(width=max(0.0, ann.width))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.NOTE:
        # Standard PDF sticky note: any reader shows the icon and lets you
        # read the text on click, no easypdf.surf needed to see it.
        x0, y0, _x1, _y1 = ann.normalized_rect()
        annot = page.add_text_annot(_point((x0, y0), page), ann.text, icon="Note")
        annot.set_colors(stroke=_color(ann.color))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.HIGHLIGHT:
        annot = page.add_highlight_annot(_rect(ann, page))
        annot.set_colors(stroke=_color(ann.color))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.LINE:
        annot = page.add_line_annot(_point(ann.p1, page), _point(ann.p2, page))
        annot.set_colors(stroke=_color(ann.color))
        annot.set_border(width=max(0.1, ann.width))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.ARROW:
        # The head is drawn as our own triangle instead of the standard PDF
        # one: PyMuPDF makes it ten times the line width, which with thick
        # strokes covers half the page and does not match what is on screen.
        base, tip, left, right = arrow_head(ann.p1, ann.p2, ann.width)
        stroke_end = ((base[0] + tip[0]) / 2.0, (base[1] + tip[1]) / 2.0)
        annot = page.add_line_annot(_point(ann.p1, page), _point(stroke_end, page))
        annot.set_colors(stroke=_color(ann.color))
        annot.set_border(width=max(0.1, ann.width))
        _apply_common(annot, ann)

        head = page.add_polygon_annot(
            [tuple(_point(pt, page)) for pt in (tip, left, right)]
        )
        head.set_colors(stroke=_color(ann.color), fill=_color(ann.color))
        head.set_border(width=0.1)
        _apply_common(head, ann)
        return annot

    if ann.kind is Kind.TEXT:
        rect = _rect(ann, page)
        # PyMuPDF needs some slack so the last line is not clipped.
        rect = pymupdf.Rect(
            rect.x0,
            rect.y0,
            max(rect.x1, rect.x0 + 8),
            max(rect.y1, rect.y0 + ann.font_size + 4),
        )
        annot = _add_freetext(page, rect, ann, ann.text, max(0.0, ann.width))
        _apply_common(annot, ann)
        if ann.bold or ann.italic:
            _set_plain_content(annot, ann.text)
        return annot

    if ann.kind is Kind.INK:
        strokes = [
            [tuple(_point(p, page)) for p in stroke]
            for stroke in ann.strokes
            if len(stroke) >= 2
        ]
        if not strokes:
            raise ValueError("a drawing needs at least one stroke with two points")
        annot = page.add_ink_annot(strokes)
        annot.set_colors(stroke=_color(ann.color))
        annot.set_border(width=max(0.1, ann.width))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.TABLE:
        return _add_table(page, ann)

    if ann.kind is Kind.IMAGE:
        return _add_image(page, ann)

    raise ValueError(f"unknown annotation kind: {ann.kind!r}")


def _add_image(page: pymupdf.Page, ann: Annotation) -> None:
    """Place an image on top of the page.

    The PDF format has no image annotation that every reader draws the same
    way, so the image is inserted into the page's content: it shows and
    prints in any program. Since saving always starts from the original
    file, saving again does not duplicate it.
    """
    if not ann.image_data:
        raise ValueError("the image has no data")
    rect = _rect(ann, page)
    page.insert_image(rect, stream=ann.image_data, keep_proportion=False, overlay=True)
    return None


def _add_table(page: pymupdf.Page, ann: Annotation) -> pymupdf.Annot:
    """Write a table: background, grid and the text of every cell.

    The PDF format has no "table" annotation type, so the grid is stored as a
    single ink stroke holding all its straight lines, and every cell with
    text is stored as a free text. It looks the same in any reader.
    """
    if ann.fill:
        background = page.add_rect_annot(_rect(ann, page))
        background.set_colors(stroke=None, fill=_color(ann.fill))
        background.set_border(width=0)
        _apply_common(background, ann)

    strokes = [
        [tuple(_point(a, page)), tuple(_point(b, page))] for a, b in ann.grid_lines()
    ]
    grid = page.add_ink_annot(strokes)
    grid.set_colors(stroke=_color(ann.color))
    grid.set_border(width=max(0.1, ann.width))
    _apply_common(grid, ann)

    for text, cell in zip(ann.normalized_cells(), ann.cell_rects()):
        if not text.strip():
            continue
        x0, y0, x1, y1 = cell
        box = pymupdf.Rect(
            x0 + CELL_PADDING, y0 + CELL_PADDING, x1 - CELL_PADDING, y1 - CELL_PADDING
        )
        if box.is_empty or box.width < 2 or box.height < 2:
            continue
        cell_annot = _add_freetext(
            page,
            pymupdf.Rect(box * page.derotation_matrix).normalize(),
            ann,
            text,
            border_width=0,
            fill=False,
        )
        _apply_common(cell_annot, ann)
        if ann.bold or ann.italic:
            _set_plain_content(cell_annot, text)

    return grid


def apply_erasures(doc: pymupdf.Document, erasures: Iterable[Annotation]) -> int:
    """Really remove whatever lies under the eraser strokes.

    Painting over is not enough: covered text can still be selected and
    copied out of a PDF, so anyone erasing a confidential detail believes
    they are safe and is not. This uses the PDF's redaction, which removes
    that area's content from the file. It is final: once saved there is no
    getting it back.

    Returns how many pages were touched.
    """
    by_page: dict[int, list[Annotation]] = {}
    for ann in erasures:
        if ann.kind is not Kind.ERASE or ann.is_empty():
            continue
        if 0 <= ann.page < doc.page_count:
            by_page.setdefault(ann.page, []).append(ann)

    for index, passes in by_page.items():
        page = doc[index]
        for ann in passes:
            fill_color = _color(ann.color)
            for box in stroke_boxes(ann.strokes, ann.width):
                rect = pymupdf.Rect(*box) & page.rect
                if rect.is_empty:
                    continue
                page.add_redact_annot(rect, fill=fill_color)
        page.apply_redactions(
            # Only the pixels the eraser touches are removed from an image:
            # taking the whole photo away for brushing a corner of it is not
            # erasing, it is something else.
            images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
            # A vector drawing (rules, boxes from the PDF itself) goes if it
            # ends up fully covered.
            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
    return len(by_page)


def apply_annotations(doc: pymupdf.Document, annotations: Iterable[Annotation]) -> int:
    """Write every annotation into the document. Returns how many were added."""
    items = list(annotations)
    # Erase first and draw afterwards: whatever the user put on top of an
    # erased area has to survive.
    apply_erasures(doc, items)
    count = 0
    for ann in items:
        if ann.kind is Kind.ERASE:
            continue          # it already did its job when erasing
        if ann.is_empty():
            continue
        if not (0 <= ann.page < doc.page_count):
            continue
        add_annotation(doc[ann.page], ann)
        count += 1
    return count
