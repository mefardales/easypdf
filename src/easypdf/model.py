"""Modelo de datos de las anotaciones.

Este modulo es Python puro: no depende ni de Qt ni de PyMuPDF, de forma que la
logica se puede probar sin interfaz grafica.

Sistema de coordenadas
----------------------
Todas las coordenadas se guardan en **puntos PDF** (1 pt = 1/72 pulgadas), con
el origen en la esquina superior izquierda de la pagina y el eje Y creciendo
hacia abajo, que es el mismo sistema que usa ``page.rect`` de PyMuPDF y el que
se ve en pantalla. Asi no hay conversiones de zoom guardadas en el modelo.
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
    """Tipos de anotacion que sabe crear EasyPDF."""

    RECT = "rect"
    HIGHLIGHT = "highlight"
    LINE = "line"
    ARROW = "arrow"
    TEXT = "text"
    INK = "ink"
    TABLE = "table"

    @property
    def label(self) -> str:
        return {
            Kind.RECT: "Cuadro",
            Kind.HIGHLIGHT: "Resaltado",
            Kind.LINE: "Linea",
            Kind.ARROW: "Flecha",
            Kind.TEXT: "Texto",
            Kind.INK: "Dibujo",
            Kind.TABLE: "Tabla",
        }[self]


class Font(str, Enum):
    """Familias que cualquier lector de PDF sabe dibujar sin incrustar nada."""

    SANS = "helv"
    SERIF = "tiro"
    MONO = "cour"

    @property
    def label(self) -> str:
        return {Font.SANS: "Sans", Font.SERIF: "Serif", Font.MONO: "Monoespaciada"}[self]

    @property
    def qt_family(self) -> str:
        return {
            Font.SANS: "Helvetica",
            Font.SERIF: "Times New Roman",
            Font.MONO: "Courier New",
        }[self]


class Align(int, Enum):
    """Alineacion del texto (mismos valores que usa el PDF)."""

    LEFT = 0
    CENTER = 1
    RIGHT = 2

    @property
    def label(self) -> str:
        return {Align.LEFT: "Izquierda", Align.CENTER: "Centro", Align.RIGHT: "Derecha"}[self]


def _new_id() -> str:
    return uuid.uuid4().hex


#: Proporciones de la punta de flecha. Son las mismas en pantalla, al imprimir
#: y en el archivo guardado: PyMuPDF dibuja las puntas estandar del PDF diez
#: veces mas grandes que el grosor de la linea, lo que con trazos gruesos queda
#: desproporcionado, asi que EasyPDF dibuja su propia punta.
ARROW_HEAD_MIN = 11.0    # largo minimo, en puntos
ARROW_HEAD_FACTOR = 5.0  # veces el grosor de la linea
ARROW_HEAD_RATIO = 0.50  # media anchura respecto al largo


def arrow_head(p1: Point, p2: Point, width: float) -> tuple[Point, Point, Point, Point]:
    """Geometria de la punta de una flecha que va de ``p1`` a ``p2``.

    Devuelve ``(base, punta, izquierda, derecha)``: la base es donde debe
    terminar la linea para que el trazo no asome por delante de la punta.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    largo_linea = math.hypot(dx, dy)
    largo = max(ARROW_HEAD_MIN, max(0.1, width) * ARROW_HEAD_FACTOR)
    if largo_linea < 1e-6:
        return (p2, p2, p2, p2)
    largo = min(largo, largo_linea)          # nunca mas larga que la propia linea
    ux, uy = dx / largo_linea, dy / largo_linea
    base = (p2[0] - ux * largo, p2[1] - uy * largo)
    media = largo * ARROW_HEAD_RATIO
    nx, ny = -uy, ux
    izquierda = (base[0] + nx * media, base[1] + ny * media)
    derecha = (base[0] - nx * media, base[1] - ny * media)
    return (base, p2, izquierda, derecha)


def arrow_line_end(p1: Point, p2: Point, width: float) -> Point:
    """Punto donde termina el trazo de una flecha (dentro de la punta)."""
    base, punta, _, _ = arrow_head(p1, p2, width)
    return ((base[0] + punta[0]) / 2.0, (base[1] + punta[1]) / 2.0)


@dataclass
class Annotation:
    """Una anotacion colocada encima de una pagina.

    Segun ``kind`` se usan unos campos u otros:

    * ``RECT`` / ``HIGHLIGHT`` / ``TEXT``  -> ``rect``
    * ``LINE`` / ``ARROW``                 -> ``p1`` y ``p2``
    * ``INK``                              -> ``strokes``
    * ``TEXT``                             -> ademas ``text``, ``font_size``
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
    color: RGB = (0.85, 0.10, 0.10)
    fill: RGB | None = None
    width: float = 1.5
    opacity: float = 1.0
    id: str = field(default_factory=_new_id)

    # -- utilidades ------------------------------------------------------
    def copy(self) -> Annotation:
        """Copia independiente (incluidos los trazos y las celdas)."""
        return replace(
            self,
            strokes=[list(stroke) for stroke in self.strokes],
            cells=list(self.cells),
        )

    def normalized_rect(self) -> Rect:
        x0, y0, x1, y1 = self.rect
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def bounds(self) -> Rect:
        """Rectangulo envolvente, sea cual sea el tipo."""
        if self.kind in (Kind.LINE, Kind.ARROW):
            (x0, y0), (x1, y1) = self.p1, self.p2
            return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if self.kind is Kind.INK:
            pts = [p for stroke in self.strokes for p in stroke]
            if not pts:
                return (0.0, 0.0, 0.0, 0.0)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        return self.normalized_rect()

    def translate(self, dx: float, dy: float) -> None:
        """Desplaza la anotacion (en puntos PDF)."""
        x0, y0, x1, y1 = self.rect
        self.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        self.p1 = (self.p1[0] + dx, self.p1[1] + dy)
        self.p2 = (self.p2[0] + dx, self.p2[1] + dy)
        self.strokes = [[(x + dx, y + dy) for x, y in s] for s in self.strokes]

    # -- tablas ----------------------------------------------------------
    def cell_count(self) -> int:
        return max(1, self.rows) * max(1, self.cols)

    def normalized_cells(self) -> list[str]:
        """Textos de las celdas, siempre con el tamano justo de la rejilla."""
        total = self.cell_count()
        cells = list(self.cells)[:total]
        cells += [""] * (total - len(cells))
        return cells

    def cell_rects(self) -> list[Rect]:
        """Rectangulo de cada celda, en orden de lectura."""
        x0, y0, x1, y1 = self.normalized_rect()
        filas, columnas = max(1, self.rows), max(1, self.cols)
        alto = (y1 - y0) / filas
        ancho = (x1 - x0) / columnas
        return [
            (x0 + c * ancho, y0 + f * alto, x0 + (c + 1) * ancho, y0 + (f + 1) * alto)
            for f in range(filas)
            for c in range(columnas)
        ]

    def grid_lines(self) -> list[tuple[Point, Point]]:
        """Lineas de la tabla: el borde y las separaciones interiores."""
        x0, y0, x1, y1 = self.normalized_rect()
        filas, columnas = max(1, self.rows), max(1, self.cols)
        lineas: list[tuple[Point, Point]] = []
        for f in range(filas + 1):
            y = y0 + (y1 - y0) * f / filas
            lineas.append(((x0, y), (x1, y)))
        for c in range(columnas + 1):
            x = x0 + (x1 - x0) * c / columnas
            lineas.append(((x, y0), (x, y1)))
        return lineas

    def is_empty(self) -> bool:
        """True si la anotacion no tiene tamano util y deberia descartarse."""
        if self.kind is Kind.INK:
            return not any(len(s) >= 2 for s in self.strokes)
        if self.kind in (Kind.LINE, Kind.ARROW):
            dx = self.p2[0] - self.p1[0]
            dy = self.p2[1] - self.p1[1]
            return (dx * dx + dy * dy) < 4.0
        x0, y0, x1, y1 = self.normalized_rect()
        if self.kind in (Kind.TEXT, Kind.TABLE):
            return (x1 - x0) < 2.0 or (y1 - y0) < 2.0
        return (x1 - x0) < 2.0 and (y1 - y0) < 2.0


class AnnotationStore:
    """Coleccion ordenada de anotaciones del documento abierto."""

    def __init__(self, annotations: Iterable[Annotation] | None = None) -> None:
        self._items: list[Annotation] = list(annotations or [])

    # -- coleccion -------------------------------------------------------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Annotation]:
        return iter(self._items)

    def __contains__(self, ann: object) -> bool:
        return any(a is ann for a in self._items)

    @property
    def items(self) -> Sequence[Annotation]:
        return tuple(self._items)

    # -- operaciones -----------------------------------------------------
    def add(self, ann: Annotation, index: int | None = None) -> Annotation:
        if index is None:
            self._items.append(ann)
        else:
            self._items.insert(index, ann)
        return ann

    def remove(self, ann: Annotation) -> int:
        """Elimina una anotacion y devuelve la posicion que ocupaba."""
        for i, item in enumerate(self._items):
            if item is ann or item.id == ann.id:
                del self._items[i]
                return i
        raise ValueError("la anotacion no pertenece al documento")

    def clear(self) -> None:
        self._items.clear()

    def for_page(self, page: int) -> list[Annotation]:
        return [a for a in self._items if a.page == page]

    def pages_used(self) -> list[int]:
        return sorted({a.page for a in self._items})
