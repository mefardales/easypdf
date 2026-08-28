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

    @property
    def label(self) -> str:
        return {
            Kind.RECT: "Cuadro",
            Kind.HIGHLIGHT: "Resaltado",
            Kind.LINE: "Linea",
            Kind.ARROW: "Flecha",
            Kind.TEXT: "Texto",
            Kind.INK: "Dibujo",
        }[self]


def _new_id() -> str:
    return uuid.uuid4().hex


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
    color: RGB = (0.85, 0.10, 0.10)
    fill: RGB | None = None
    width: float = 1.5
    opacity: float = 1.0
    id: str = field(default_factory=_new_id)

    # -- utilidades ------------------------------------------------------
    def copy(self) -> Annotation:
        """Copia independiente (incluida la lista de trazos)."""
        return replace(self, strokes=[list(s) for s in self.strokes])

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

    def is_empty(self) -> bool:
        """True si la anotacion no tiene tamano util y deberia descartarse."""
        if self.kind is Kind.INK:
            return not any(len(s) >= 2 for s in self.strokes)
        if self.kind in (Kind.LINE, Kind.ARROW):
            dx = self.p2[0] - self.p1[0]
            dy = self.p2[1] - self.p1[1]
            return (dx * dx + dy * dy) < 4.0
        x0, y0, x1, y1 = self.normalized_rect()
        if self.kind is Kind.TEXT:
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
