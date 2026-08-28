"""Capa de acceso al PDF (PyMuPDF) sin ninguna dependencia de Qt."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import pymupdf

from .annotations import apply_annotations
from .model import Annotation

#: Tamanos de pagina habituales, en puntos PDF (ancho, alto).
PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595.0, 842.0),
    "A4 horizontal": (842.0, 595.0),
    "Carta": (612.0, 792.0),
    "Carta horizontal": (792.0, 612.0),
    "A5": (420.0, 595.0),
    "A3": (842.0, 1191.0),
    "Oficio": (612.0, 1008.0),
}

DEFAULT_PAGE_SIZE = "A4"


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
    def blank(
        cls,
        pages: int = 1,
        size: str | tuple[float, float] = DEFAULT_PAGE_SIZE,
        title: str | None = None,
    ) -> PdfDocument:
        """Crea un documento nuevo con paginas en blanco."""
        ancho, alto = PAGE_SIZES.get(size, size) if isinstance(size, str) else size
        doc = pymupdf.open()
        for _ in range(max(1, pages)):
            doc.new_page(width=ancho, height=alto)
        doc.set_metadata({"producer": "easypdf.surf", "title": title or ""})
        datos = doc.tobytes()
        doc.close()
        documento = cls(datos)
        documento._untitled = title or "Documento nuevo.pdf"
        return documento

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
        if self._path:
            return os.path.basename(self._path)
        return getattr(self, "_untitled", "Sin titulo.pdf")

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

    def page_rotation(self, index: int) -> int:
        """Giro de la pagina, en grados horarios (0, 90, 180 o 270)."""
        return int(self._doc[index].rotation) % 360

    def set_page_rotation(self, index: int, degrees: int) -> None:
        """Fija el giro de la pagina (absoluto, no acumulativo)."""
        self._doc[index].set_rotation(int(degrees) % 360)
        self._refresh_data()

    # -- edicion de paginas ----------------------------------------------
    def _refresh_data(self) -> None:
        """Rehace los bytes base tras cambiar la estructura del documento."""
        self._data = self._doc.tobytes()
        self._password = ""

    def add_blank_page(
        self, index: int | None = None, size: str | tuple[float, float] | None = None
    ) -> int:
        """Inserta una pagina en blanco y devuelve su posicion."""
        if size is None:
            ancho, alto = self.page_size(max(0, min(index or 0, self.page_count - 1)))
        elif isinstance(size, str):
            ancho, alto = PAGE_SIZES.get(size, PAGE_SIZES[DEFAULT_PAGE_SIZE])
        else:
            ancho, alto = size
        posicion = self.page_count if index is None else max(0, min(index, self.page_count))
        self._doc.new_page(pno=posicion, width=ancho, height=alto)
        self._refresh_data()
        return posicion

    def duplicate_page(self, index: int) -> int:
        """Copia una pagina justo detras de ella."""
        if not (0 <= index < self.page_count):
            raise IndexError(f"la pagina {index} no existe")
        destino = index + 1
        # PyMuPDF usa -1 para "al final"; el rango valido llega hasta la ultima.
        self._doc.fullcopy_page(index, to=destino if destino < self.page_count else -1)
        self._refresh_data()
        return index + 1

    def delete_page(self, index: int) -> None:
        if self.page_count <= 1:
            raise PdfError("El documento no puede quedarse sin paginas.")
        if not (0 <= index < self.page_count):
            raise IndexError(f"la pagina {index} no existe")
        self._doc.delete_page(index)
        self._refresh_data()

    def move_page(self, index: int, destino: int) -> None:
        """Mueve una pagina a otra posicion."""
        if not (0 <= index < self.page_count):
            raise IndexError(f"la pagina {index} no existe")
        destino = max(0, min(destino, self.page_count - 1))
        if destino == index:
            return
        # PyMuPDF inserta "delante de" la pagina indicada; -1 significa al final.
        delante = destino if destino < index else destino + 1
        self._doc.move_page(index, delante if delante < self.page_count else -1)
        self._refresh_data()

    def extract_page(self, index: int) -> bytes:
        """Devuelve esa pagina suelta como PDF (para poder deshacer un borrado)."""
        if not (0 <= index < self.page_count):
            raise IndexError(f"la pagina {index} no existe")
        suelta = pymupdf.open()
        suelta.insert_pdf(self._doc, from_page=index, to_page=index)
        datos = suelta.tobytes()
        suelta.close()
        return datos

    def insert_page_bytes(self, data: bytes, index: int) -> None:
        """Vuelve a meter en el documento una pagina extraida."""
        otra = pymupdf.open(stream=data, filetype="pdf")
        try:
            self._doc.insert_pdf(otra, start_at=max(0, min(index, self.page_count)))
        finally:
            otra.close()
        self._refresh_data()

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
