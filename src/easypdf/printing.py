"""Impresion: la vista previa y la salida usan el mismo PDF que se guarda."""

from __future__ import annotations

from collections.abc import Sequence

import pymupdf
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from .document import PdfDocument
from .model import Annotation

#: Limite de resolucion para no agotar la memoria en impresoras de 1200 ppp.
MAX_PRINT_DPI = 600


def pages_for_printer(printer: QPrinter, page_count: int) -> list[int]:
    """Indices (base 0) de las paginas que pide el dialogo de impresion."""
    if printer.printRange() == QPrinter.PageRange:
        first = max(1, printer.fromPage() or 1)
        last = min(page_count, printer.toPage() or page_count)
        return list(range(first - 1, last))
    if printer.printRange() == QPrinter.CurrentPage:
        return []  # lo decide quien llama
    return list(range(page_count))


def render_to_printer(
    data: bytes,
    printer: QPrinter,
    pages: Sequence[int] | None = None,
    password: str = "",
    parent=None,
) -> bool:
    """Dibuja las paginas del PDF en la impresora (o en el PDF de salida)."""
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
            QMessageBox.warning(parent, "Imprimir", "No se pudo iniciar la impresion.")
        return False

    progress = None
    if parent is not None and len(indices) > 1:
        progress = QProgressDialog("Preparando paginas...", "Cancelar", 0, len(indices), parent)
        progress.setWindowTitle("Imprimir")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(400)

    cancelled = False
    try:
        target = QRectF(printer.pageRect(QPrinter.DevicePixel))
        for position, index in enumerate(indices):
            if progress is not None:
                progress.setValue(position)
                progress.setLabelText(f"Pagina {index + 1} de {doc.page_count}")
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
            # Se rasteriza justo a la resolucion que cabe en la hoja.
            scale = min(target.width() / rect.width, target.height() / rect.height)
            scale = max(0.2, min(scale, MAX_PRINT_DPI / 72.0))
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
    """Muestra el dialogo de impresion del sistema e imprime."""
    if not doc.can_print:
        answer = QMessageBox.question(
            parent,
            "Imprimir",
            "Este PDF pide no ser impreso.\n\nEsa restriccion no esta protegida por "
            "contrasena, asi que EasyPDF puede imprimirlo igualmente.\n\n"
            "Solo hazlo si tienes derecho a ello. Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False

    printer = _make_printer(doc)
    printer.setFromTo(1, doc.page_count)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Imprimir documento")
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
    """Vista previa de impresion con el resultado exacto (anotaciones incluidas)."""
    data = doc.export_bytes(annotations)
    printer = _make_printer(doc)
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle("Vista previa de impresion")
    dialog.resize(900, 700)

    def _paint(target_printer: QPrinter) -> None:
        pages = pages_for_printer(target_printer, doc.page_count)
        render_to_printer(data, target_printer, pages)

    dialog.paintRequested.connect(_paint)
    dialog.exec()


__all__ = ["print_document", "print_preview", "render_to_printer", "pages_for_printer"]
