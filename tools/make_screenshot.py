#!/usr/bin/env python3
"""Builds docs/screenshot.png: the EasyPDF window with an example in it.

The same document and the same annotations are drawn every time, so the
README's screenshot can be regenerated after any visual change.

Usage:  python tools/make_screenshot.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

PARAGRAPHS = [
    "Over the last quarter we reviewed the internal customer support procedures",
    "and cut the average response time by 34%. The team welcomed two new people",
    "and completed the training planned for the year.",
    "",
    "Critical incidents dropped from 18 to 5, and none of them took longer than",
    "four hours to resolve. Cost per case remains stable.",
    "",
    "Proposals for the next quarter:",
    "   1. Extend phone support until 20:00.",
    "   2. Publish the FAQ on the internal portal.",
    "   3. Review the maintenance contract before 30 June.",
    "",
    "The indicator breakdown is attached in the appendix on the last page,",
    "together with the comparison against the three previous quarters.",
]


def build_sample_pdf(path: str, pages: int = 4) -> None:
    import pymupdf

    doc = pymupdf.open()
    for number in range(pages):
        page = doc.new_page()
        page.insert_text((72, 90), "Quarterly activity report", fontsize=20, fontname="hebo")
        page.insert_text(
            (72, 115),
            f"Operations department  -  Page {number + 1} of {pages}",
            fontsize=10,
            color=(0.4, 0.4, 0.4),
        )
        page.draw_line(
            pymupdf.Point(72, 128), pymupdf.Point(523, 128), color=(0.8, 0.8, 0.8), width=1
        )
        y = 165
        for line in PARAGRAPHS:
            page.insert_text((72, y), line, fontsize=11)
            y += 19
    doc.save(path)
    doc.close()


def main() -> int:
    import tempfile

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from easypdf.i18n import set_language
    from easypdf.model import Annotation, Kind
    from easypdf.ui.main_window import MainWindow
    from easypdf.ui.page_view import Tool

    with tempfile.TemporaryDirectory() as tmp:
        sample = os.path.join(tmp, "report.pdf")
        build_sample_pdf(sample)

        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        # After building the window: its __init__ applies the language stored
        # in the user settings, which is of no interest here.
        set_language("en")
        window.retranslate()
        window.resize(1280, 860)
        window.thumb_dock.setVisible(True)   # the screenshot always shows it
        window.show()
        QTest.qWaitForWindowExposed(window)
        window.open_path(sample)
        window.view.set_zoom(1.0)
        window.view.go_to_page(0)
        app.processEvents()

        annotations = [
            Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(70, 152, 470, 172),
                       color=(1.0, 0.83, 0.0)),
            Annotation(kind=Kind.RECT, page=0, rect=(66, 320, 460, 400),
                       color=(0.85, 0.10, 0.10), width=2.0),
            Annotation(kind=Kind.ARROW, page=0, p1=(430, 470), p2=(400, 408),
                       color=(0.08, 0.40, 0.75), width=2.0),
            Annotation(kind=Kind.TEXT, page=0, rect=(300, 478, 520, 520),
                       text="Double-check this\nwith the team", font_size=12,
                       color=(0.08, 0.40, 0.75), width=1.0),
            Annotation(kind=Kind.INK, page=0,
                       strokes=[[(80, 430), (120, 455), (160, 425), (200, 460), (240, 430)]],
                       color=(0.18, 0.49, 0.20), width=2.5),
            Annotation(kind=Kind.TABLE, page=0, rect=(72, 540, 520, 620), rows=3, cols=3,
                       cells=["Quarter", "Incidents", "Cost",
                              "Previous", "18", "4,200 EUR",
                              "Current", "5", "3,950 EUR"],
                       color=(0.15, 0.15, 0.18), width=0.8, font_size=9),
        ]
        for ann in annotations:
            window.view.add_annotation(ann, undoable=False)

        window.select_tool(Tool.TABLE)
        window._update_actions()
        window.statusBar().showMessage(
            "Tool: Table  -  drag on the page; double click a cell to type"
        )
        QTest.qWait(800)
        app.processEvents()

        target = os.path.join(ROOT, "docs", "screenshot.png")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not window.grab().save(target):
            raise RuntimeError("the screenshot could not be saved")
        print(f"Wrote {target}")

        window._modified = False
        window.view.undo_stack.setClean()
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
