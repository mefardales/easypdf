#!/usr/bin/env python3
"""Genera docs/captura-principal.png: la ventana de EasyPDF con un ejemplo.

Se dibuja siempre el mismo documento y las mismas anotaciones, asi que la
captura del README se puede regenerar despues de cualquier cambio visual.

Uso:  python tools/make_screenshot.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

PARRAFOS = [
    "Durante el ultimo trimestre se han revisado los procedimientos internos de",
    "atencion al cliente y se ha reducido el tiempo medio de respuesta en un 34%.",
    "El equipo ha incorporado dos personas nuevas y ha completado la formacion",
    "prevista en el plan anual.",
    "",
    "Las incidencias criticas han bajado de 18 a 5, y ninguna de ellas ha superado",
    "las cuatro horas de resolucion. El coste por expediente se mantiene estable.",
    "",
    "Propuestas para el proximo trimestre:",
    "   1. Ampliar el horario de soporte telefonico hasta las 20:00.",
    "   2. Publicar la guia de preguntas frecuentes en el portal interno.",
    "   3. Revisar el contrato de mantenimiento antes del 30 de junio.",
    "",
    "Se adjunta el detalle de indicadores en el anexo de la ultima pagina, junto",
    "con la comparativa de los tres trimestres anteriores.",
]


def build_sample_pdf(path: str, pages: int = 4) -> None:
    import pymupdf

    doc = pymupdf.open()
    for number in range(pages):
        page = doc.new_page()
        page.insert_text((72, 90), "Informe trimestral de actividad", fontsize=20, fontname="hebo")
        page.insert_text(
            (72, 115),
            f"Departamento de operaciones  -  Pagina {number + 1} de {pages}",
            fontsize=10,
            color=(0.4, 0.4, 0.4),
        )
        page.draw_line(
            pymupdf.Point(72, 128), pymupdf.Point(523, 128), color=(0.8, 0.8, 0.8), width=1
        )
        y = 165
        for linea in PARRAFOS:
            page.insert_text((72, y), linea, fontsize=11)
            y += 19
    doc.save(path)
    doc.close()


def main() -> int:
    import tempfile

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from easypdf.model import Annotation, Kind
    from easypdf.ui.main_window import MainWindow
    from easypdf.ui.page_view import Tool

    with tempfile.TemporaryDirectory() as tmp:
        muestra = os.path.join(tmp, "informe.pdf")
        build_sample_pdf(muestra)

        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        window.resize(1280, 860)
        window.show()
        QTest.qWaitForWindowExposed(window)
        window.open_path(muestra)
        window.view.set_zoom(1.0)
        window.view.go_to_page(0)
        app.processEvents()

        anotaciones = [
            Annotation(kind=Kind.HIGHLIGHT, page=0, rect=(70, 152, 470, 172),
                       color=(1.0, 0.83, 0.0)),
            Annotation(kind=Kind.RECT, page=0, rect=(66, 320, 460, 400),
                       color=(0.85, 0.10, 0.10), width=2.0),
            Annotation(kind=Kind.ARROW, page=0, p1=(430, 470), p2=(400, 408),
                       color=(0.08, 0.40, 0.75), width=2.0),
            Annotation(kind=Kind.TEXT, page=0, rect=(300, 478, 520, 520),
                       text="Revisar este dato\ncon el equipo", font_size=12,
                       color=(0.08, 0.40, 0.75), width=1.0),
            Annotation(kind=Kind.INK, page=0,
                       strokes=[[(80, 430), (120, 455), (160, 425), (200, 460), (240, 430)]],
                       color=(0.18, 0.49, 0.20), width=2.5),
        ]
        for ann in anotaciones:
            window.view.add_annotation(ann, undoable=False)

        window.select_tool(Tool.RECT)
        window._update_actions()
        window.statusBar().showMessage(
            "Herramienta: Cuadro  -  arrastra sobre la pagina para dibujar"
        )
        QTest.qWait(800)
        app.processEvents()

        destino = os.path.join(ROOT, "docs", "captura-principal.png")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        if not window.grab().save(destino):
            raise RuntimeError("no se pudo guardar la captura")
        print(f"Escrito {destino}")

        window._modified = False
        window.view.undo_stack.setClean()
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
