"""Plantillas: guardar lo creado para reutilizarlo en otros documentos.

Una plantilla es un archivo JSON con el tamano de sus paginas y todas sus
anotaciones (incluidas las imagenes, guardadas dentro del propio archivo). Se
puede usar de dos maneras:

* crear un documento nuevo a partir de ella (paginas + anotaciones), o
* aplicarla encima del documento que ya se tiene abierto.

Este modulo no depende de Qt para poder probarse sin interfaz.
"""

from __future__ import annotations

import base64
import json
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .model import Align, Annotation, Font, Kind

#: Version del formato, por si algun dia cambia.
FORMAT_VERSION = 1

EXTENSION = ".easypdf-template.json"

#: Como se llamaban antes. Se siguen leyendo para no perder lo que ya
#: hubiera guardado el usuario; lo nuevo se escribe con EXTENSION.
LEGACY_EXTENSIONS = (".easypdf-plantilla.json",)

#: Tipos de plantilla. Sirven para ordenar el panel: una cosa es un documento
#: entero y otra un membrete que se pone encima de lo que ya hay.
CATEGORIES = ("letterhead", "document", "report", "certificate", "table",
              "form", "other")
DEFAULT_CATEGORY = "other"


class TemplateError(RuntimeError):
    """Error al leer o escribir una plantilla."""


@dataclass(frozen=True)
class TemplateInfo:
    """Datos de una plantilla guardada, sin cargar su contenido."""

    name: str
    path: str
    pages: int
    annotations: int
    saved_at: str = ""
    category: str = "other"
    builtin: bool = False


def safe_filename(name: str) -> str:
    """Nombre de archivo valido a partir del nombre que escriba el usuario."""
    limpio = re.sub(r"[^\w\s.-]", "", name, flags=re.UNICODE).strip()
    limpio = re.sub(r"\s+", " ", limpio)
    return limpio or "plantilla"


# ---------------------------------------------------------------- serializar
def annotation_to_dict(ann: Annotation) -> dict:
    """Convierte una anotacion en datos guardables."""
    data: dict = {
        "kind": Kind(ann.kind).value,
        "page": int(ann.page),
        "rect": list(ann.rect),
        "color": list(ann.color),
        "width": float(ann.width),
        "opacity": float(ann.opacity),
    }
    if ann.fill is not None:
        data["fill"] = list(ann.fill)
    if ann.kind in (Kind.LINE, Kind.ARROW):
        data["p1"] = list(ann.p1)
        data["p2"] = list(ann.p2)
    if ann.kind in (Kind.INK, Kind.ERASE):
        data["strokes"] = [[list(p) for p in stroke] for stroke in ann.strokes]
    if ann.kind in (Kind.TEXT, Kind.TABLE):
        data.update(
            text=ann.text,
            font_size=float(ann.font_size),
            font=Font(ann.font).value,
            bold=bool(ann.bold),
            italic=bool(ann.italic),
            align=int(Align(ann.align)),
        )
    if ann.kind is Kind.TABLE:
        data.update(rows=int(ann.rows), cols=int(ann.cols), cells=list(ann.cells))
    if ann.kind is Kind.IMAGE and ann.image_data:
        data["image_name"] = ann.image_name
        data["image_data"] = base64.b64encode(ann.image_data).decode("ascii")
    return data


def annotation_from_dict(data: dict) -> Annotation:
    """Reconstruye una anotacion guardada."""
    try:
        kind = Kind(data["kind"])
    except (KeyError, ValueError) as exc:
        raise TemplateError(f"tipo de anotacion desconocido: {data.get('kind')!r}") from exc
    ann = Annotation(kind=kind, page=int(data.get("page", 0)))
    ann.rect = tuple(data.get("rect", ann.rect))
    ann.color = tuple(data.get("color", ann.color))
    ann.width = float(data.get("width", ann.width))
    ann.opacity = float(data.get("opacity", ann.opacity))
    if data.get("fill") is not None:
        ann.fill = tuple(data["fill"])
    ann.p1 = tuple(data.get("p1", ann.p1))
    ann.p2 = tuple(data.get("p2", ann.p2))
    ann.strokes = [[tuple(p) for p in stroke] for stroke in data.get("strokes", [])]
    ann.text = str(data.get("text", ""))
    ann.font_size = float(data.get("font_size", ann.font_size))
    ann.font = Font(data.get("font", Font.SANS.value))
    ann.bold = bool(data.get("bold", False))
    ann.italic = bool(data.get("italic", False))
    ann.align = Align(int(data.get("align", 0)))
    ann.rows = int(data.get("rows", ann.rows))
    ann.cols = int(data.get("cols", ann.cols))
    ann.cells = list(data.get("cells", []))
    ann.image_name = str(data.get("image_name", ""))
    if data.get("image_data"):
        ann.image_data = base64.b64decode(data["image_data"])
    return ann


# ---------------------------------------------------------------- archivos
def save_template(
    directory: str,
    name: str,
    annotations: Iterable[Annotation],
    page_sizes: Sequence[tuple[float, float]] = (),
    category: str = DEFAULT_CATEGORY,
) -> str:
    """Guarda una plantilla y devuelve la ruta del archivo."""
    name = name.strip()
    if not name:
        raise TemplateError("La plantilla necesita un nombre.")
    os.makedirs(directory, exist_ok=True)
    content = {
        "version": FORMAT_VERSION,
        "name": name,
        "category": category if category in CATEGORIES else DEFAULT_CATEGORY,
        "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "pages": [{"width": float(w), "height": float(h)} for w, h in page_sizes],
        "annotations": [annotation_to_dict(a) for a in annotations if not a.is_empty()],
    }
    path = os.path.join(directory, safe_filename(name) + EXTENSION)
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(content, fh, ensure_ascii=False, indent=1)
        os.replace(temporary, path)
    except OSError as exc:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:  # pragma: no cover
                pass
        raise TemplateError(f"No se pudo guardar la plantilla: {exc}") from exc
    return path


def load_template(path: str) -> tuple[str, list[tuple[float, float]], list[Annotation]]:
    """Lee una plantilla: devuelve (nombre, tamanos de pagina, anotaciones)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateError(f"No se pudo leer la plantilla: {exc}") from exc
    if not isinstance(data, dict) or "annotations" not in data:
        raise TemplateError("El archivo no parece una plantilla de easypdf.surf.")
    page_items = [
        (float(p.get("width", 595.0)), float(p.get("height", 842.0)))
        for p in data.get("pages", [])
    ]
    annotations = [annotation_from_dict(d) for d in data.get("annotations", [])]
    return str(data.get("name") or os.path.basename(path)), page_items, annotations


def list_templates(directory: str) -> list[TemplateInfo]:
    """Plantillas guardadas en la carpeta, ordenadas por nombre."""
    if not os.path.isdir(directory):
        return []
    found: list[TemplateInfo] = []
    for file in sorted(os.listdir(directory)):
        if not file.endswith((EXTENSION,) + LEGACY_EXTENSIONS):
            continue
        path = os.path.join(directory, file)
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            found.append(
                TemplateInfo(
                    name=str(data.get("name") or file),
                    path=path,
                    pages=len(data.get("pages", [])),
                    annotations=len(data.get("annotations", [])),
                    saved_at=str(data.get("saved_at", "")),
                    category=str(data.get("category") or DEFAULT_CATEGORY),
                )
            )
        except (OSError, json.JSONDecodeError):
            continue  # un archivo roto no debe romper la lista
    return sorted(found, key=lambda t: t.name.lower())


def delete_template(path: str) -> None:
    try:
        os.remove(path)
    except OSError as exc:
        raise TemplateError(f"No se pudo borrar la plantilla: {exc}") from exc


def shift_to_page(annotations: Iterable[Annotation], first_page: int, page_count: int):
    """Recoloca las anotaciones de una plantilla a partir de la pagina indicada."""
    result = []
    for ann in annotations:
        copia = ann.copy()
        copia.id = Annotation(kind=copia.kind, page=0).id  # identidad nueva
        copia.page = min(max(0, first_page + ann.page), max(0, page_count - 1))
        result.append(copia)
    return result


__all__ = [
    "TemplateError",
    "TemplateInfo",
    "annotation_from_dict",
    "annotation_to_dict",
    "delete_template",
    "list_templates",
    "load_template",
    "save_template",
    "shift_to_page",
    "EXTENSION",
]


# ---------------------------------------------------------------- de serie
A4 = (595.0, 842.0)
IZQ, DER = 56.0, 539.0          # margenes de la hoja
GREY = (0.42, 0.45, 0.50)
RULE = (0.72, 0.74, 0.78)
INK = (0.10, 0.12, 0.16)

#: Textos de las plantillas incluidas. Van aparte de i18n.py porque son
#: contenido de documento, no interfaz, y este modulo no depende de Qt.
BUILTIN_TEXTS = {
    "en": {
        "letterhead": "Letterhead",
        "letter": "Letter",
        "memo": "Memo",
        "minutes": "Meeting minutes",
        "report_cover": "Report cover",
        "report": "Monthly report",
        "diploma": "Diploma",
        "attendance_cert": "Certificate of attendance",
        "data_table": "Data table",
        "invoice": "Invoice",
        "quote": "Quotation",
        "signatures": "Attendance sheet",
        "checklist": "Checklist",
        "company": "COMPANY NAME",
        "company_sub": "Address - Phone - Email",
        "page1": "Page 1",
        "date": "Date:",
        "to": "To:",
        "from": "From:",
        "subject": "Subject:",
        "place": "Place:",
        "attendees": "Attendees:",
        "agreements": "Agreements",
        "agreement": "Agreement",
        "owner": "Owner",
        "due": "Due date",
        "minutes_title": "MEETING MINUTES",
        "report_title": "MONTHLY REPORT",
        "department": "Department",
        "period": "Period",
        "prepared": "Prepared by",
        "summary": "Summary",
        "figures": "Key figures",
        "indicator": "Indicator",
        "value": "Value",
        "change": "Change",
        "notes": "Notes and next steps",
        "diploma_title": "CERTIFICATE",
        "diploma_given": "This is to certify that",
        "diploma_name": "FULL NAME",
        "diploma_body": "has successfully completed the programme",
        "diploma_course": "Name of the course",
        "signature": "Signature",
        "attendance_body": "attended the session",
        "invoice_title": "INVOICE",
        "invoice_no": "Invoice no.",
        "customer": "Customer",
        "concept": "Item",
        "qty": "Qty",
        "price": "Price",
        "total": "Total",
        "quote_title": "QUOTATION",
        "valid": "Valid until",
        "signatures_title": "ATTENDANCE SHEET",
        "name": "Name",
        "role": "Role",
        "checklist_title": "CHECKLIST",
        "task": "Task",
        "done": "Done",
        "who": "Who",
        "label": "Label",
        "option": "Option",
        "yes": "Yes",
        "no": "No",
        "heading": "Heading",
        "notes_short": "Notes",
    },
    "es": {
        "letterhead": "Membrete",
        "letter": "Carta",
        "memo": "Memorando",
        "minutes": "Acta de reunion",
        "report_cover": "Portada de informe",
        "report": "Informe mensual",
        "diploma": "Diploma",
        "attendance_cert": "Certificado de asistencia",
        "data_table": "Cuadro de datos",
        "invoice": "Factura",
        "quote": "Presupuesto",
        "signatures": "Hoja de firmas",
        "checklist": "Lista de comprobacion",
        "company": "NOMBRE DE LA EMPRESA",
        "company_sub": "Direccion - Telefono - Correo",
        "page1": "Pagina 1",
        "date": "Fecha:",
        "to": "Para:",
        "from": "De:",
        "subject": "Asunto:",
        "place": "Lugar:",
        "attendees": "Asistentes:",
        "agreements": "Acuerdos",
        "agreement": "Acuerdo",
        "owner": "Responsable",
        "due": "Fecha limite",
        "minutes_title": "ACTA DE REUNION",
        "report_title": "INFORME MENSUAL",
        "department": "Departamento",
        "period": "Periodo",
        "prepared": "Preparado por",
        "summary": "Resumen",
        "figures": "Datos principales",
        "indicator": "Indicador",
        "value": "Valor",
        "change": "Variacion",
        "notes": "Observaciones y proximos pasos",
        "diploma_title": "CERTIFICADO",
        "diploma_given": "Se certifica que",
        "diploma_name": "NOMBRE Y APELLIDOS",
        "diploma_body": "ha completado con aprovechamiento el programa",
        "diploma_course": "Nombre del curso",
        "signature": "Firma",
        "attendance_body": "asistio a la sesion",
        "invoice_title": "FACTURA",
        "invoice_no": "Factura n.",
        "customer": "Cliente",
        "concept": "Concepto",
        "qty": "Cant.",
        "price": "Precio",
        "total": "Total",
        "quote_title": "PRESUPUESTO",
        "valid": "Valido hasta",
        "signatures_title": "HOJA DE FIRMAS",
        "name": "Nombre",
        "role": "Cargo",
        "checklist_title": "LISTA DE COMPROBACION",
        "task": "Tarea",
        "done": "Hecho",
        "who": "Quien",
        "label": "Etiqueta",
        "option": "Opcion",
        "yes": "Si",
        "no": "No",
        "heading": "Titulo",
        "notes_short": "Notas",
    },
}


def _t(key: str) -> str:
    """Texto de plantilla en el idioma de la interfaz."""
    from .i18n import DEFAULT_LANGUAGE, language

    language = language()
    tabla = BUILTIN_TEXTS.get(language) or BUILTIN_TEXTS[DEFAULT_LANGUAGE]
    return tabla.get(key, BUILTIN_TEXTS[DEFAULT_LANGUAGE].get(key, key))


def _texto(x, y, width, height, text, tam=11.0, negrita=False,
           align=Align.LEFT, color=INK) -> Annotation:
    return Annotation(
        kind=Kind.TEXT, page=0, rect=(x, y, x + width, y + height), text=text,
        font_size=tam, bold=negrita, align=align, color=color, width=0.0,
    )


def _linea(y, x0=IZQ, x1=DER, color=RULE, thickness=0.8) -> Annotation:
    return Annotation(kind=Kind.LINE, page=0, p1=(x0, y), p2=(x1, y),
                      color=color, width=thickness)


def _tabla(y, height, rows, headers, ancho_x0=IZQ, ancho_x1=DER) -> Annotation:
    cells = list(headers) + [""] * (len(headers) * (rows - 1))
    return Annotation(
        kind=Kind.TABLE, page=0, rect=(ancho_x0, y, ancho_x1, y + height),
        rows=rows, cols=len(headers), cells=cells,
        align=Align.LEFT, width=0.8, color=INK,
    )


def _cabecera() -> list[Annotation]:
    """Membrete: nombre de la empresa, datos y raya."""
    return [
        _texto(IZQ, 48, 340, 24, _t("company"), 15, True),
        _texto(IZQ, 72, 340, 14, _t("company_sub"), 9, color=GREY),
        _linea(96.0),
    ]


def _pie() -> Annotation:
    return _texto(IZQ, 790, DER - IZQ, 14, _t("page1"), 9,
                  align=Align.CENTER, color=GREY)


def builtin_templates() -> list[tuple[str, str, list[tuple[float, float]], list[Annotation]]]:
    """Plantillas que trae el programa: (nombre, tipo, paginas, anotaciones).

    Estan hechas con las mismas anotaciones que crearia el usuario, asi que
    una vez cargadas se pueden mover y editar como cualquier otra cosa. Los
    textos salen en el idioma de la interfaz.
    """
    width = DER - IZQ

    membrete = _cabecera() + [_pie()]

    carta = _cabecera() + [
        _texto(IZQ, 130, width, 16, _t("date"), 11),
        _texto(IZQ, 156, width, 16, _t("to"), 11),
        _texto(IZQ, 182, width, 16, _t("subject"), 11, True),
        _linea(208.0),
        _texto(IZQ, 230, width, 420, "", 11),
        _texto(IZQ, 690, 220, 16, _t("signature"), 10, color=GREY),
        _linea(686.0, IZQ, IZQ + 220),
    ]

    memo = _cabecera() + [
        _texto(IZQ, 128, width, 22, _t("memo").upper(), 14, True),
        _texto(IZQ, 160, 240, 16, _t("to"), 10),
        _texto(300, 160, 239, 16, _t("from"), 10),
        _texto(IZQ, 182, 240, 16, _t("date"), 10),
        _texto(300, 182, 239, 16, _t("subject"), 10),
        _linea(208.0),
        _texto(IZQ, 228, width, 440, "", 11),
    ]

    acta = _cabecera() + [
        _texto(IZQ, 128, width, 22, _t("minutes_title"), 14, True, Align.CENTER),
        _texto(IZQ, 164, 240, 16, _t("date"), 10),
        _texto(300, 164, 239, 16, _t("place"), 10),
        _texto(IZQ, 186, width, 16, _t("attendees"), 10),
        _linea(212.0),
        _texto(IZQ, 228, width, 16, _t("agreements"), 11, True),
        _tabla(250, 150, 5, [_t("agreement"), _t("owner"), _t("due")]),
        _texto(IZQ, 690, 220, 16, _t("signature"), 10, color=GREY),
        _linea(686.0, IZQ, IZQ + 220),
    ]

    cover = [
        _linea(300.0, IZQ, DER, INK, 2.0),
        _texto(IZQ, 316, width, 40, _t("report_title"), 26, True),
        _texto(IZQ, 366, width, 20, _t("department"), 12, color=GREY),
        _texto(IZQ, 390, width, 20, _t("period"), 12, color=GREY),
        _texto(IZQ, 414, width, 20, _t("prepared"), 12, color=GREY),
        _linea(450.0, IZQ, DER, INK, 2.0),
        _texto(IZQ, 780, width, 16, _t("company"), 10, color=GREY),
    ]

    informe = _cabecera() + [
        _texto(IZQ, 128, width, 24, _t("report_title"), 15, True),
        _texto(IZQ, 158, 240, 16, _t("period"), 10, color=GREY),
        _texto(300, 158, 239, 16, _t("prepared"), 10, color=GREY),
        _linea(182.0),
        _texto(IZQ, 200, width, 16, _t("summary"), 12, True),
        _texto(IZQ, 222, width, 90, "", 11),
        _texto(IZQ, 326, width, 16, _t("figures"), 12, True),
        _tabla(348, 120, 4, [_t("indicator"), _t("value"), _t("change")]),
        _texto(IZQ, 488, width, 16, _t("notes"), 12, True),
        _texto(IZQ, 510, width, 220, "", 11),
        _pie(),
    ]

    diploma = [
        Annotation(kind=Kind.RECT, page=0, rect=(36.0, 36.0, 559.0, 806.0),
                   color=INK, width=2.0),
        Annotation(kind=Kind.RECT, page=0, rect=(48.0, 48.0, 547.0, 794.0),
                   color=RULE, width=0.8),
        _texto(IZQ, 150, width, 44, _t("diploma_title"), 30, True, Align.CENTER),
        _linea(210.0, 180.0, 415.0, INK, 1.2),
        _texto(IZQ, 250, width, 20, _t("diploma_given"), 12, align=Align.CENTER,
               color=GREY),
        _texto(IZQ, 290, width, 34, _t("diploma_name"), 22, True, Align.CENTER),
        _texto(IZQ, 344, width, 20, _t("diploma_body"), 12, align=Align.CENTER,
               color=GREY),
        _texto(IZQ, 378, width, 26, _t("diploma_course"), 16, True, Align.CENTER),
        _texto(IZQ, 470, width, 18, _t("date"), 11, align=Align.CENTER, color=GREY),
        _linea(650.0, 150.0, 330.0),
        _texto(150, 656, 180, 16, _t("signature"), 10, align=Align.CENTER, color=GREY),
        _linea(650.0, 360.0, 540.0),
        _texto(360, 656, 180, 16, _t("signature"), 10, align=Align.CENTER, color=GREY),
    ]

    attendance = [
        Annotation(kind=Kind.RECT, page=0, rect=(36.0, 36.0, 559.0, 806.0),
                   color=INK, width=2.0),
        _texto(IZQ, 170, width, 34, _t("attendance_cert"), 22, True, Align.CENTER),
        _linea(224.0, 200.0, 395.0, INK, 1.2),
        _texto(IZQ, 280, width, 20, _t("diploma_given"), 12, align=Align.CENTER,
               color=GREY),
        _texto(IZQ, 316, width, 30, _t("diploma_name"), 20, True, Align.CENTER),
        _texto(IZQ, 364, width, 20, _t("attendance_body"), 12, align=Align.CENTER,
               color=GREY),
        _texto(IZQ, 396, width, 26, _t("diploma_course"), 15, True, Align.CENTER),
        _texto(IZQ, 470, width, 18, _t("date"), 11, align=Align.CENTER, color=GREY),
        _linea(640.0, 200.0, 395.0),
        _texto(200, 646, 195, 16, _t("signature"), 10, align=Align.CENTER, color=GREY),
    ]

    box = [
        _texto(IZQ, 56, width, 24, _t("data_table"), 13, True),
        _tabla(92, 280, 10, [_t("concept"), _t("qty"), _t("price"), _t("total")]),
    ]

    factura = _cabecera() + [
        _texto(IZQ, 128, width, 24, _t("invoice_title"), 16, True),
        _texto(IZQ, 160, 240, 16, _t("invoice_no"), 10),
        _texto(300, 160, 239, 16, _t("date"), 10),
        _texto(IZQ, 182, width, 16, _t("customer"), 10),
        _linea(208.0),
        _tabla(224, 260, 9, [_t("concept"), _t("qty"), _t("price"), _t("total")]),
        _texto(340, 500, 120, 18, _t("total"), 12, True, Align.RIGHT),
        _linea(496.0, 340.0, DER),
        _pie(),
    ]

    presupuesto = _cabecera() + [
        _texto(IZQ, 128, width, 24, _t("quote_title"), 16, True),
        _texto(IZQ, 160, 240, 16, _t("customer"), 10),
        _texto(300, 160, 239, 16, _t("valid"), 10),
        _linea(186.0),
        _tabla(202, 260, 9, [_t("concept"), _t("qty"), _t("price"), _t("total")]),
        _texto(340, 478, 120, 18, _t("total"), 12, True, Align.RIGHT),
        _linea(474.0, 340.0, DER),
        _texto(IZQ, 690, 220, 16, _t("signature"), 10, color=GREY),
        _linea(686.0, IZQ, IZQ + 220),
    ]

    firmas = _cabecera() + [
        _texto(IZQ, 128, width, 24, _t("signatures_title"), 14, True, Align.CENTER),
        _texto(IZQ, 162, 240, 16, _t("date"), 10),
        _texto(300, 162, 239, 16, _t("place"), 10),
        _tabla(196, 480, 13, [_t("name"), _t("role"), _t("signature")]),
        _pie(),
    ]

    check_flag = _cabecera() + [
        _texto(IZQ, 128, width, 24, _t("checklist_title"), 14, True),
        _texto(IZQ, 158, width, 16, _t("date"), 10, color=GREY),
        _tabla(186, 480, 15, [_t("task"), _t("who"), _t("done")]),
        _pie(),
    ]

    return [
        (_t("letterhead"), "letterhead", [A4], membrete),
        (_t("letter"), "document", [A4], carta),
        (_t("memo"), "document", [A4], memo),
        (_t("minutes"), "document", [A4], acta),
        (_t("report_cover"), "report", [A4], cover),
        (_t("report"), "report", [A4], informe),
        (_t("diploma"), "certificate", [A4], diploma),
        (_t("attendance_cert"), "certificate", [A4], attendance),
        (_t("data_table"), "table", [A4], box),
        (_t("invoice"), "table", [A4], factura),
        (_t("quote"), "table", [A4], presupuesto),
        (_t("signatures"), "form", [A4], firmas),
        (_t("checklist"), "form", [A4], check_flag),
    ]


def builtin_infos() -> list[TemplateInfo]:
    """Las de serie, con el mismo aspecto que las guardadas por el usuario."""
    return [
        TemplateInfo(name=name, path=f"builtin:{name}", pages=len(page_items),
                     annotations=len(anns), category=tipo, builtin=True)
        for name, tipo, page_items, anns in builtin_templates()
    ]


def load_builtin(name: str):
    """Return (name, pages, annotations) of a built-in template."""
    for candidate, _category, page_sizes, anns in builtin_templates():
        if candidate == name:
            return (candidate, list(page_sizes), [a.copy() for a in anns])
    raise TemplateError(f"There is no built-in template called {name!r}")
