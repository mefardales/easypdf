"""Traduccion del modelo de easypdf.surf a anotaciones reales de PDF (PyMuPDF).

Las anotaciones se escriben como objetos PDF estandar (Square, Line, FreeText,
Ink, Highlight), asi que cualquier otro lector -Adobe Reader, Edge, Firefox-
las muestra igual y siguen siendo seleccionables.
"""

from __future__ import annotations

import html
from collections.abc import Iterable

import pymupdf

from .model import Align, Annotation, Font, Kind, arrow_head

#: Nombre que se guarda en el campo /T de la anotacion.
AUTHOR = "easypdf.surf"

#: Nombres de las 14 fuentes basicas del PDF: cualquier lector las tiene, asi
#: que no hace falta incrustar nada en el archivo.
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

#: Margen entre el borde de una celda y su texto, en puntos.
CELL_PADDING = 2.5

#: Familias CSS equivalentes, para el texto con negrita o cursiva.
CSS_FAMILIES = {Font.SANS: "sans-serif", Font.SERIF: "serif", Font.MONO: "monospace"}

CSS_ALIGN = {Align.LEFT: "left", Align.CENTER: "center", Align.RIGHT: "right"}


def font_code(ann: Annotation) -> str:
    """Nombre de fuente PDF segun familia, negrita y cursiva."""
    return FONT_CODES.get((Font(ann.font), bool(ann.bold), bool(ann.italic)), "helv")


def _hex_color(rgb) -> str:
    r, g, b = (int(round(_clamp01(c) * 255)) for c in (rgb or (0, 0, 0)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _rich_html(ann: Annotation, text: str) -> str:
    """Texto en HTML sencillo para negrita y cursiva."""
    cuerpo = html.escape(text).replace("\n", "<br>")
    if ann.bold:
        cuerpo = f"<b>{cuerpo}</b>"
    if ann.italic:
        cuerpo = f"<i>{cuerpo}</i>"
    return cuerpo


def _add_freetext(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    ann: Annotation,
    text: str,
    border_width: float,
    fill: bool = True,
) -> pymupdf.Annot:
    """Texto libre con familia, tamano, alineacion y, si toca, negrita/cursiva.

    PyMuPDF ignora las variantes negrita y cursiva en el texto normal (todas
    acaban dibujadas con la fuente base), asi que en ese caso se usa el modo de
    texto enriquecido, donde si se respetan.
    """
    relleno = _color(ann.fill) if fill else None
    if ann.bold or ann.italic:
        estilo = (
            f"font-family:{CSS_FAMILIES.get(Font(ann.font), 'sans-serif')};"
            f"font-size:{max(1.0, ann.font_size):g}px;"
            f"color:{_hex_color(ann.color)};"
            f"text-align:{CSS_ALIGN.get(Align(ann.align), 'left')}"
        )
        annot = page.add_freetext_annot(
            rect,
            _rich_html(ann, text),
            fontsize=max(1.0, ann.font_size),
            fill_color=relleno,
            border_width=border_width,
            opacity=_clamp01(ann.opacity),
            richtext=True,
            style=estilo,
        )
        return annot
    return page.add_freetext_annot(
        rect,
        text,
        fontsize=max(1.0, ann.font_size),
        fontname=font_code(ann),
        align=int(Align(ann.align)),
        text_color=_color(ann.color),
        fill_color=relleno,
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
    """Guarda el texto en claro sin rehacer el aspecto de la anotacion.

    En el texto enriquecido el contenido viaja como HTML. Usar set_info() para
    dejarlo tambien en claro haria que PyMuPDF regenerase la apariencia desde
    ese texto plano y se perderian la negrita y la cursiva, asi que se escribe
    directamente en el objeto PDF.
    """
    try:
        annot.parent.parent.xref_set_key(annot.xref, "Contents", pymupdf.get_pdf_str(text))
    except Exception:  # pragma: no cover - depende de la version de PyMuPDF
        pass


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

    if ann.kind is Kind.NOTE:
        # Nota adhesiva estandar del PDF: cualquier lector ensena el icono y
        # deja leer el texto al pulsarlo, no hace falta EasyPDF para verla.
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
        # La punta se dibuja como un triangulo propio en vez de usar la punta
        # estandar del PDF: PyMuPDF la hace diez veces el grosor de la linea,
        # que con trazos gruesos tapa media pagina y no coincide con lo que se
        # ve en pantalla.
        base, punta, izquierda, derecha = arrow_head(ann.p1, ann.p2, ann.width)
        fin = ((base[0] + punta[0]) / 2.0, (base[1] + punta[1]) / 2.0)
        annot = page.add_line_annot(_point(ann.p1, page), _point(fin, page))
        annot.set_colors(stroke=_color(ann.color))
        annot.set_border(width=max(0.1, ann.width))
        _apply_common(annot, ann)

        cabeza = page.add_polygon_annot(
            [tuple(_point(pt, page)) for pt in (punta, izquierda, derecha)]
        )
        cabeza.set_colors(stroke=_color(ann.color), fill=_color(ann.color))
        cabeza.set_border(width=0.1)
        _apply_common(cabeza, ann)
        return annot

    if ann.kind is Kind.TEXT:
        rect = _rect(ann, page)
        # PyMuPDF necesita algo de holgura para no recortar la ultima linea.
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
            raise ValueError("un dibujo necesita al menos un trazo con dos puntos")
        annot = page.add_ink_annot(strokes)
        annot.set_colors(stroke=_color(ann.color))
        annot.set_border(width=max(0.1, ann.width))
        _apply_common(annot, ann)
        return annot

    if ann.kind is Kind.TABLE:
        return _add_table(page, ann)

    if ann.kind is Kind.IMAGE:
        return _add_image(page, ann)

    raise ValueError(f"tipo de anotacion desconocido: {ann.kind!r}")


def _add_image(page: pymupdf.Page, ann: Annotation) -> None:
    """Coloca una imagen encima de la pagina.

    El PDF no tiene una anotacion de imagen que todos los lectores dibujen
    igual, asi que la imagen se inserta en el contenido de la pagina: se ve y
    se imprime en cualquier programa. Como al guardar siempre se parte del
    archivo original, volver a guardar no la duplica.
    """
    if not ann.image_data:
        raise ValueError("la imagen no tiene datos")
    rect = _rect(ann, page)
    page.insert_image(rect, stream=ann.image_data, keep_proportion=False, overlay=True)
    return None


def _add_table(page: pymupdf.Page, ann: Annotation) -> pymupdf.Annot:
    """Escribe una tabla: fondo, rejilla y el texto de cada celda.

    El PDF no tiene un tipo de anotacion "tabla", asi que la rejilla se guarda
    como un unico trazo de tinta con todas sus lineas rectas y cada celda con
    texto se guarda como un texto libre. Se ve igual en cualquier lector.
    """
    if ann.fill:
        fondo = page.add_rect_annot(_rect(ann, page))
        fondo.set_colors(stroke=None, fill=_color(ann.fill))
        fondo.set_border(width=0)
        _apply_common(fondo, ann)

    trazos = [
        [tuple(_point(a, page)), tuple(_point(b, page))] for a, b in ann.grid_lines()
    ]
    rejilla = page.add_ink_annot(trazos)
    rejilla.set_colors(stroke=_color(ann.color))
    rejilla.set_border(width=max(0.1, ann.width))
    _apply_common(rejilla, ann)

    for texto, celda in zip(ann.normalized_cells(), ann.cell_rects()):
        if not texto.strip():
            continue
        x0, y0, x1, y1 = celda
        caja = pymupdf.Rect(
            x0 + CELL_PADDING, y0 + CELL_PADDING, x1 - CELL_PADDING, y1 - CELL_PADDING
        )
        if caja.is_empty or caja.width < 2 or caja.height < 2:
            continue
        celda_annot = _add_freetext(
            page,
            pymupdf.Rect(caja * page.derotation_matrix).normalize(),
            ann,
            texto,
            border_width=0,
            fill=False,
        )
        _apply_common(celda_annot, ann)
        if ann.bold or ann.italic:
            _set_plain_content(celda_annot, texto)

    return rejilla


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
