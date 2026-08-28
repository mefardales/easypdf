"""Traduccion del modelo de EasyPDF a anotaciones reales de PDF (PyMuPDF).

Las anotaciones se escriben como objetos PDF estandar (Square, Line, FreeText,
Ink, Highlight), asi que cualquier otro lector -Adobe Reader, Edge, Firefox-
las muestra igual y siguen siendo seleccionables.
"""

from __future__ import annotations

from collections.abc import Iterable

import pymupdf

from .model import Annotation, Kind

#: Nombre que se guarda en el campo /T de la anotacion.
AUTHOR = "EasyPDF"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _color(rgb: Iterable[float] | None) -> list[float] | None:
    if rgb is None:
        return None
    return [_clamp01(c) for c in rgb]


def _apply_common(annot: pymupdf.Annot, ann: Annotation) -> None:
    """Ajustes comunes: opacidad, autor y aspecto."""
    annot.set_opacity(_clamp01(ann.opacity))
    try:
        annot.set_info(title=AUTHOR)
    except Exception:  # pragma: no cover - depende de la version de PyMuPDF
        pass
    annot.update()


def _rect(ann: Annotation, page: pymupdf.Page) -> pymupdf.Rect:
    x0, y0, x1, y1 = ann.normalized_rect()
    rect = pymupdf.Rect(x0, y0, x1, y1) * page.derotation_matrix
    return pymupdf.Rect(rect).normalize()


def _point(pt, page: pymupdf.Page) -> pymupdf.Point:
    return pymupdf.Point(pt[0], pt[1]) * page.derotation_matrix


def add_annotation(page: pymupdf.Page, ann: Annotation) -> pymupdf.Annot:
    """Anade una anotacion del modelo a una pagina de PyMuPDF."""
    if ann.kind is Kind.RECT:
        annot = page.add_rect_annot(_rect(ann, page))
        annot.set_colors(stroke=_color(ann.color), fill=_color(ann.fill))
        annot.set_border(width=max(0.0, ann.width))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.HIGHLIGHT:
        annot = page.add_highlight_annot(_rect(ann, page))
        annot.set_colors(stroke=_color(ann.color))
        _apply_common(annot, ann)
        return annot

    if ann.kind in (Kind.LINE, Kind.ARROW):
        annot = page.add_line_annot(_point(ann.p1, page), _point(ann.p2, page))
        annot.set_colors(stroke=_color(ann.color))
        annot.set_border(width=max(0.1, ann.width))
        if ann.kind is Kind.ARROW:
            annot.set_line_ends(pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_CLOSED_ARROW)
            # La punta de flecha se rellena con el mismo color del trazo.
            annot.set_colors(stroke=_color(ann.color), fill=_color(ann.color))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.TEXT:
        rect = _rect(ann, page)
        # PyMuPDF necesita algo de holgura para no recortar la ultima linea.
        rect = pymupdf.Rect(rect.x0, rect.y0, max(rect.x1, rect.x0 + 8), max(rect.y1, rect.y0 + ann.font_size + 4))
        annot = page.add_freetext_annot(
            rect,
            ann.text,
            fontsize=max(1.0, ann.font_size),
            fontname="helv",
            text_color=_color(ann.color),
            fill_color=_color(ann.fill),
            # En una nota de texto simple PyMuPDF dibuja el borde con el mismo
            # color del texto, que es justo lo que muestra el editor.
            border_width=max(0.0, ann.width),
            opacity=_clamp01(ann.opacity),
        )
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.INK:
        strokes = [
            [tuple(_point(p, page)) for p in stroke]
            for stroke in ann.strokes
            if len(stroke) >= 2
        ]
        if not strokes:
            raise ValueError("un dibujo necesita al menos un trazo con dos puntos")
        annot = page.add_ink_annot(strokes)
        annot.set_colors(stroke=_color(ann.color))
        annot.set_border(width=max(0.1, ann.width))
        _apply_common(annot, ann)
        return annot

    raise ValueError(f"tipo de anotacion desconocido: {ann.kind!r}")


def apply_annotations(doc: pymupdf.Document, annotations: Iterable[Annotation]) -> int:
    """Escribe todas las anotaciones en el documento. Devuelve cuantas se anadieron."""
    count = 0
    for ann in annotations:
        if ann.is_empty():
            continue
        if not (0 <= ann.page < doc.page_count):
            continue
        add_annotation(doc[ann.page], ann)
        count += 1
    return count
