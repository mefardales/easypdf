"""Capa de acceso al PDF (PyMuPDF) sin ninguna dependencia de Qt."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import pymupdf

from .annotations import apply_annotations
from .model import Annotation


class PdfError(RuntimeError):
    """Error al abrir o guardar un PDF."""


class PasswordRequired(PdfError):
    """El documento esta protegido y hace falta una contrasena."""


@dataclass(frozen=True)
class RenderedPage:
    """Pagina rasterizada en RGB de 8 bits por canal."""

    width: int
    height: int
    stride: int
    samples: bytes


@dataclass(frozen=True)
class SearchHit:
    """Una coincidencia de busqueda, en puntos PDF."""

    page: int
    rect: tuple[float, float, float, float]


class PdfDocument:
    """Documento abierto en memoria.

    Se guardan siempre los bytes originales del archivo. Al guardar, EasyPDF
    parte de esos bytes y les anade las anotaciones actuales, de modo que
    guardar dos veces nunca duplica nada y las anotaciones siguen siendo
    editables durante toda la sesion.
    """

    def __init__(self, data: bytes, path: str | None = None, password: str = "") -> None:
        self._data = bytes(data)
        self._path = path
        self._password = password
        try:
            self._doc = pymupdf.open(stream=self._data, filetype="pdf")
        except Exception as exc:  # pragma: no cover - depende del archivo
            raise PdfError(f"No se pudo abrir el PDF: {exc}") from exc
        if self._doc.needs_pass and not self._doc.authenticate(password):
            self._doc.close()
            raise PasswordRequired("El documento esta protegido con contrasena.")

    # -- construccion ----------------------------------------------------
    @classmethod
    def open(cls, path: str, password: str = "") -> PdfDocument:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            raise PdfError(f"No se pudo leer el archivo: {exc}") from exc
        return cls(data, path=path, password=password)

    def close(self) -> None:
        try:
            self._doc.close()
        except Exception:  # pragma: no cover
            pass

    # -- informacion -----------------------------------------------------
    @property
    def path(self) -> str | None:
        return self._path

    @property
    def name(self) -> str:
        return os.path.basename(self._path) if self._path else "Sin titulo.pdf"

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    @property
    def metadata(self) -> dict:
        return dict(self._doc.metadata or {})

    @property
    def can_print(self) -> bool:
        """False si el PDF prohibe imprimir (se respeta la restriccion)."""
        return bool(self._doc.permissions & pymupdf.PDF_PERM_PRINT)

    def page_size(self, index: int) -> tuple[float, float]:
        """Tamano de la pagina en puntos PDF, tal y como se ve (con rotacion)."""
        rect = self._doc[index].rect
        return (rect.width, rect.height)

    def page_sizes(self) -> list[tuple[float, float]]:
        return [self.page_size(i) for i in range(self.page_count)]

    # -- render ----------------------------------------------------------
    def render_page(self, index: int, scale: float = 1.0) -> RenderedPage:
        """Rasteriza una pagina. ``scale`` 1.0 = 72 ppp."""
        scale = max(0.05, min(8.0, float(scale)))
        page = self._doc[index]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=True)
        return RenderedPage(pix.width, pix.height, pix.stride, pix.samples)

    def page_text(self, index: int) -> str:
        return self._doc[index].get_text("text")

    def search(self, needle: str, max_hits: int = 2000) -> list[SearchHit]:
        """Busca texto en todo el documento (sin distinguir mayusculas)."""
        needle = needle.strip()
        if not needle:
            return []
        hits: list[SearchHit] = []
        for i in range(self.page_count):
            for rect in self._doc[i].search_for(needle):
                hits.append(SearchHit(i, (rect.x0, rect.y0, rect.x1, rect.y1)))
                if len(hits) >= max_hits:
                    return hits
        return hits

    # -- salida ----------------------------------------------------------
    def _fresh_copy(self) -> pymupdf.Document:
        doc = pymupdf.open(stream=self._data, filetype="pdf")
        if doc.needs_pass:
            doc.authenticate(self._password)
        return doc

    def export_bytes(self, annotations: Iterable[Annotation] = ()) -> bytes:
        """Devuelve el PDF original con las anotaciones indicadas incorporadas."""
        doc = self._fresh_copy()
        try:
            apply_annotations(doc, annotations)
            return doc.tobytes(garbage=3, deflate=True)
        except Exception as exc:
            raise PdfError(f"No se pudo generar el PDF: {exc}") from exc
        finally:
            doc.close()

    def save_as(self, path: str, annotations: Iterable[Annotation] = ()) -> None:
        """Guarda una copia con las anotaciones. Escribe de forma atomica."""
        data = self.export_bytes(annotations)
        tmp = f"{path}.easypdf-tmp"
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except OSError as exc:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:  # pragma: no cover
                    pass
            raise PdfError(f"No se pudo guardar el archivo: {exc}") from exc
        self._path = path

    # -- utilidades ------------------------------------------------------
    @staticmethod
    def is_pdf(path: str) -> bool:
        return os.path.splitext(path)[1].lower() == ".pdf"


def open_bytes_for_render(data: bytes, password: str = "") -> pymupdf.Document:
    """Abre bytes de PDF para rasterizar (usado al imprimir)."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    if doc.needs_pass:
        doc.authenticate(password)
    return doc


def render_pages(
    doc: pymupdf.Document, pages: Sequence[int], scale: float
) -> Iterable[tuple[int, RenderedPage]]:
    """Generador de paginas rasterizadas (para imprimir sin cargarlo todo)."""
    for index in pages:
        pix = doc[index].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=True)
        yield index, RenderedPage(pix.width, pix.height, pix.stride, pix.samples)
