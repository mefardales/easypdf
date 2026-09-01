"""PDF access layer (PyMuPDF) with no Qt dependency at all."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import pymupdf

from .annotations import apply_annotations
from .model import Annotation

#: Common page sizes, in PDF points (width, height). The keys are internal
#: identifiers; i18n.page_size_label() translates them for display.
PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595.0, 842.0),
    "A4 landscape": (842.0, 595.0),
    "Letter": (612.0, 792.0),
    "Letter landscape": (792.0, 612.0),
    "A5": (420.0, 595.0),
    "A3": (842.0, 1191.0),
    "Legal": (612.0, 1008.0),
}

#: The keys used to be in Spanish. Anyone who had picked one keeps their
#: choice instead of silently falling back to A4.
LEGACY_PAGE_SIZES = {
    "A4 horizontal": "A4 landscape",
    "Carta": "Letter",
    "Carta horizontal": "Letter landscape",
    "Oficio": "Legal",
}

DEFAULT_PAGE_SIZE = "A4"


def page_size_key(name: str) -> str:
    """Current name of a page size, translating the old Spanish keys."""
    return LEGACY_PAGE_SIZES.get(name, name)


class PdfError(RuntimeError):
    """Error while opening or saving a PDF."""


class PasswordRequired(PdfError):
    """The document is protected and a password is needed."""


@dataclass(frozen=True)
class RenderedPage:
    """Page rasterised as RGB, 8 bits per channel."""

    width: int
    height: int
    stride: int
    samples: bytes


@dataclass(frozen=True)
class SearchHit:
    """A search hit, in PDF points."""

    page: int
    rect: tuple[float, float, float, float]


class PdfDocument:
    """Document held in memory.

    The file's original bytes are always kept. When saving, easypdf.surf
    starts from those bytes and adds the current annotations, so saving
    twice never duplicates anything and the annotations stay editable for
    the whole session.
    """

    def __init__(self, data: bytes, path: str | None = None, password: str = "") -> None:
        self._data = bytes(data)
        self._path = path
        self._password = password
        try:
            self._doc = pymupdf.open(stream=self._data, filetype="pdf")
        except Exception as exc:  # pragma: no cover - depends on the file
            raise PdfError(f"Could not open the PDF: {exc}") from exc
        if self._doc.needs_pass and not self._doc.authenticate(password):
            self._doc.close()
            raise PasswordRequired("The document is password protected.")

    # -- construction ----------------------------------------------------
    @classmethod
    def blank(
        cls,
        pages: int = 1,
        size: str | tuple[float, float] = DEFAULT_PAGE_SIZE,
        title: str | None = None,
    ) -> PdfDocument:
        """Create a new document with blank pages."""
        # An unknown name used to fall through as the string itself and blow
        # up on unpacking; now it falls back to the default size.
        if isinstance(size, str):
            width, height = PAGE_SIZES.get(page_size_key(size), PAGE_SIZES[DEFAULT_PAGE_SIZE])
        else:
            width, height = size
        doc = pymupdf.open()
        for _ in range(max(1, pages)):
            doc.new_page(width=width, height=height)
        doc.set_metadata({"producer": "easypdf.surf", "title": title or ""})
        data = doc.tobytes()
        doc.close()
        document = cls(data)
        from .i18n import tr

        document._untitled = title or tr("untitled_document")
        return document

    @classmethod
    def open(cls, path: str, password: str = "") -> PdfDocument:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            raise PdfError(f"Could not read the file: {exc}") from exc
        return cls(data, path=path, password=password)

    def close(self) -> None:
        try:
            self._doc.close()
        except Exception:  # pragma: no cover
            pass

    # -- information -----------------------------------------------------
    @property
    def path(self) -> str | None:
        return self._path

    @property
    def name(self) -> str:
        if self._path:
            return os.path.basename(self._path)
        from .i18n import tr

        return getattr(self, "_untitled", tr("untitled"))

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    @property
    def metadata(self) -> dict:
        return dict(self._doc.metadata or {})

    @property
    def can_print(self) -> bool:
        """False if the PDF forbids printing (the restriction is honoured)."""
        return bool(self._doc.permissions & pymupdf.PDF_PERM_PRINT)

    def page_size(self, index: int) -> tuple[float, float]:
        """Page size in PDF points, as displayed (rotation included)."""
        rect = self._doc[index].rect
        return (rect.width, rect.height)

    def page_sizes(self) -> list[tuple[float, float]]:
        return [self.page_size(i) for i in range(self.page_count)]

    # -- bookmarks -------------------------------------------------------
    def bookmarks(self) -> list[tuple[str, int]]:
        """Document bookmarks as (title, zero-based page).

        The PDF's own outline is used, which is what any reader shows in its
        bookmarks panel, so they are visible outside easypdf.surf too.
        """
        bookmarks = []
        for entry in self._doc.get_toc(simple=True):
            _level, title, page = entry[0], entry[1], entry[2]
            if page >= 1:                         # 0 or -1 = no destination
                bookmarks.append((str(title), int(page) - 1))
        return bookmarks

    def set_bookmarks(self, bookmarks) -> None:
        """Replace the bookmarks. Flat list of (title, zero-based page)."""
        toc = [
            [1, str(title), int(page) + 1]
            for title, page in bookmarks
            if 0 <= int(page) < self.page_count
        ]
        self._doc.set_toc(toc)
        self._refresh_data()

    # -- notes -----------------------------------------------------------
    def take_notes(self) -> list[tuple[int, float, float, str]]:
        """Take the sticky notes out of the PDF and return them.

        They are removed from the document on purpose: from here on
        easypdf.surf carries them in its annotation list and writes them
        back when saving. If they stayed here too, every save would
        duplicate them.
        """
        found: list[tuple[int, float, float, str]] = []
        touched = False
        for number in range(self._doc.page_count):
            page = self._doc[number]
            for annot in list(page.annots(types=(pymupdf.PDF_ANNOT_TEXT,))):
                rect = annot.rect
                found.append(
                    (number, rect.x0, rect.y0, annot.info.get("content", ""))
                )
                page.delete_annot(annot)
                touched = True
        if touched:
            self._refresh_data()
        return found

    def page_rotation(self, index: int) -> int:
        """Page rotation, in clockwise degrees (0, 90, 180 or 270)."""
        return int(self._doc[index].rotation) % 360

    def set_page_rotation(self, index: int, degrees: int) -> None:
        """Set the page rotation (absolute, not cumulative)."""
        self._doc[index].set_rotation(int(degrees) % 360)
        self._refresh_data()

    # -- page editing ----------------------------------------------------
    def _refresh_data(self) -> None:
        """Rebuild the base bytes after changing the document's structure."""
        self._data = self._doc.tobytes()
        self._password = ""

    def add_blank_page(
        self, index: int | None = None, size: str | tuple[float, float] | None = None
    ) -> int:
        """Insert a blank page and return its position."""
        if size is None:
            width, height = self.page_size(max(0, min(index or 0, self.page_count - 1)))
        elif isinstance(size, str):
            width, height = PAGE_SIZES.get(
                page_size_key(size), PAGE_SIZES[DEFAULT_PAGE_SIZE]
            )
        else:
            width, height = size
        position = self.page_count if index is None else max(0, min(index, self.page_count))
        self._doc.new_page(pno=position, width=width, height=height)
        self._refresh_data()
        return position

    def duplicate_page(self, index: int) -> int:
        """Copy a page right after itself."""
        if not (0 <= index < self.page_count):
            raise IndexError(f"page {index} does not exist")
        target = index + 1
        # PyMuPDF uses -1 for "at the end"; the valid range ends at the last.
        self._doc.fullcopy_page(index, to=target if target < self.page_count else -1)
        self._refresh_data()
        return index + 1

    def delete_page(self, index: int) -> None:
        if self.page_count <= 1:
            raise PdfError("The document cannot be left with no pages.")
        if not (0 <= index < self.page_count):
            raise IndexError(f"la pagina {index} no existe")
        self._doc.delete_page(index)
        self._refresh_data()

    def move_page(self, index: int, target: int) -> None:
        """Move a page to another position."""
        if not (0 <= index < self.page_count):
            raise IndexError(f"page {index} does not exist")
        target = max(0, min(target, self.page_count - 1))
        if target == index:
            return
        # PyMuPDF inserts "in front of" the given page; -1 means at the end.
        before = target if target < index else target + 1
        self._doc.move_page(index, before if before < self.page_count else -1)
        self._refresh_data()

    def extract_page(self, index: int) -> bytes:
        """Return that single page as a PDF (so a deletion can be undone)."""
        if not (0 <= index < self.page_count):
            raise IndexError(f"page {index} does not exist")
        single = pymupdf.open()
        single.insert_pdf(self._doc, from_page=index, to_page=index)
        data = single.tobytes()
        single.close()
        return data

    def insert_page_bytes(self, data: bytes, index: int) -> None:
        """Put an extracted page back into the document."""
        other = pymupdf.open(stream=data, filetype="pdf")
        try:
            self._doc.insert_pdf(other, start_at=max(0, min(index, self.page_count)))
        finally:
            other.close()
        self._refresh_data()

    # -- render ----------------------------------------------------------
    def render_page(self, index: int, scale: float = 1.0) -> RenderedPage:
        """Rasterise a page. ``scale`` 1.0 = 72 dpi."""
        scale = max(0.05, min(8.0, float(scale)))
        page = self._doc[index]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=True)
        return RenderedPage(pix.width, pix.height, pix.stride, pix.samples)

    def page_text(self, index: int) -> str:
        return self._doc[index].get_text("text")

    def search(self, needle: str, max_hits: int = 2000) -> list[SearchHit]:
        """Search text across the whole document (case-insensitive)."""
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

    # -- output ----------------------------------------------------------
    def _fresh_copy(self) -> pymupdf.Document:
        doc = pymupdf.open(stream=self._data, filetype="pdf")
        if doc.needs_pass:
            doc.authenticate(self._password)
        return doc

    def export_bytes(self, annotations: Iterable[Annotation] = ()) -> bytes:
        """Return the original PDF with the given annotations baked in."""
        doc = self._fresh_copy()
        try:
            apply_annotations(doc, annotations)
            return doc.tobytes(garbage=3, deflate=True)
        except Exception as exc:
            raise PdfError(f"Could not generate the PDF: {exc}") from exc
        finally:
            doc.close()

    def save_as(self, path: str, annotations: Iterable[Annotation] = ()) -> None:
        """Save a copy with the annotations. Written atomically."""
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
            raise PdfError(f"Could not save the file: {exc}") from exc
        self._path = path

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def is_pdf(path: str) -> bool:
        return os.path.splitext(path)[1].lower() == ".pdf"


def open_bytes_for_render(data: bytes, password: str = "") -> pymupdf.Document:
    """Open PDF bytes for rasterising (used when printing)."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    if doc.needs_pass:
        doc.authenticate(password)
    return doc


def render_pages(
    doc: pymupdf.Document, pages: Sequence[int], scale: float
) -> Iterable[tuple[int, RenderedPage]]:
    """Generator of rasterised pages (to print without loading everything)."""
    for index in pages:
        pix = doc[index].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=True)
        yield index, RenderedPage(pix.width, pix.height, pix.stride, pix.samples)
