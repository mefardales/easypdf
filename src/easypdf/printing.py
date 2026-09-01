"""Printing: the preview and the output use the same PDF that gets saved."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pymupdf
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from .document import PdfDocument
from .i18n import tr
from .model import Annotation

#: Rasterising resolution cap. 300 dpi is normal print quality and avoids
#: rasterising at 1200 dpi (16 times the memory for the same result).
MAX_PRINT_DPI = 300

#: Hard pixel cap per page, in case the printer declares a huge area.
MAX_PAGE_PIXELS = 40_000_000


def page_scale(page_width: float, page_height: float, target_width: float, target_height: float) -> float:
    """Rasterising factor for a page so that it fits the sheet.

    Capped by ``MAX_PRINT_DPI`` and ``MAX_PAGE_PIXELS``: a 1200 dpi printer
    would ask for images hundreds of megabytes big with no visible gain.
    """
    if page_width <= 0 or page_height <= 0:
        return 1.0
    scale = min(target_width / page_width, target_height / page_height)
    scale = min(scale, MAX_PRINT_DPI / 72.0)
    pixels = (page_width * scale) * (page_height * scale)
    if pixels > MAX_PAGE_PIXELS:
        scale *= math.sqrt(MAX_PAGE_PIXELS / pixels)
    return max(0.2, scale)


def pages_for_printer(printer: QPrinter, page_count: int) -> list[int]:
    """Zero-based indices of the pages the print dialog asked for."""
    if printer.printRange() == QPrinter.PageRange:
        first = max(1, printer.fromPage() or 1)
        last = min(page_count, printer.toPage() or page_count)
        return list(range(first - 1, last))
    if printer.printRange() == QPrinter.CurrentPage:
        return []  # the caller decides
    return list(range(page_count))


def render_to_printer(
    data: bytes,
    printer: QPrinter,
    pages: Sequence[int] | None = None,
    password: str = "",
    parent=None,
) -> bool:
    """Draw the PDF pages on the printer (or into the output PDF)."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    if doc.needs_pass:
        doc.authenticate(password)
    indices = list(pages) if pages is not None else list(range(doc.page_count))
    if not indices:
        doc.close()
        return False

    painter = QPainter()
    if not painter.begin(printer):
        doc.close()
        if parent is not None:
            QMessageBox.warning(parent, tr("print"), tr("print_failed"))
        return False

    progress = None
    if parent is not None and len(indices) > 1:
        progress = QProgressDialog(tr("print_preparing"), None, 0, len(indices), parent)
        progress.setWindowTitle(tr("print_title"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(400)

    cancelled = False
    try:
        target = QRectF(printer.pageRect(QPrinter.DevicePixel))
        for position, index in enumerate(indices):
            if progress is not None:
                progress.setValue(position)
                progress.setLabelText(tr("print_page_of", page=index + 1, total=doc.page_count))
                QApplication.processEvents()
                if progress.wasCanceled():
                    cancelled = True
                    break
            if position > 0 and not printer.newPage():
                break
            page = doc[index]
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                continue
            # Rasterised at exactly the resolution that fits the sheet.
            scale = page_scale(rect.width, rect.height, target.width(), target.height())
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=True)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            width = rect.width * scale
            height = rect.height * scale
            fit = min(target.width() / width, target.height() / height)
            draw_w, draw_h = width * fit, height * fit
            box = QRectF(
                target.x() + (target.width() - draw_w) / 2,
                target.y() + (target.height() - draw_h) / 2,
                draw_w,
                draw_h,
            )
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawImage(box, image)
        if progress is not None:
            progress.setValue(len(indices))
    finally:
        painter.end()
        doc.close()
    return not cancelled


def _make_printer(doc: PdfDocument) -> QPrinter:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setDocName(doc.name)
    printer.setFullPage(False)
    return printer


def print_document(
    parent,
    doc: PdfDocument,
    annotations: Sequence[Annotation] = (),
    current_page: int = 0,
) -> bool:
    """Show the system print dialog and print."""
    if not doc.can_print:
        answer = QMessageBox.question(
            parent,
            tr("print_title"),
            tr("print_restricted"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False

    printer = _make_printer(doc)
    printer.setFromTo(1, doc.page_count)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle(tr("print_title"))
    dialog.setOptions(
        QPrintDialog.PrintToFile
        | QPrintDialog.PrintPageRange
        | QPrintDialog.PrintCollateCopies
        | QPrintDialog.PrintCurrentPage
    )
    if dialog.exec() != QPrintDialog.Accepted:
        return False

    data = doc.export_bytes(annotations)
    pages = pages_for_printer(printer, doc.page_count)
    if printer.printRange() == QPrinter.CurrentPage:
        pages = [current_page]
    return render_to_printer(data, printer, pages, parent=parent)


def print_preview(
    parent,
    doc: PdfDocument,
    annotations: Sequence[Annotation] = (),
) -> None:
    """Print preview showing the exact result (annotations included)."""
    data = doc.export_bytes(annotations)
    printer = _make_printer(doc)
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle(tr("print_preview_title"))
    dialog.resize(900, 700)

    def _paint(target_printer: QPrinter) -> None:
        pages = pages_for_printer(target_printer, doc.page_count)
        render_to_printer(data, target_printer, pages)

    dialog.paintRequested.connect(_paint)
    dialog.exec()


__all__ = [
    "print_document",
    "print_preview",
    "render_to_printer",
    "pages_for_printer",
    "page_scale",
]
