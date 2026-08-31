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

EXTENSION = ".easypdf-plantilla.json"

#: Tipos de plantilla. Sirven para ordenar el panel: una cosa es un documento
#: entero y otra un membrete que se pone encima de lo que ya hay.
CATEGORIES = ("document", "letterhead", "table", "form", "other")
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
    datos: dict = {
        "kind": Kind(ann.kind).value,
        "page": int(ann.page),
        "rect": list(ann.rect),
        "color": list(ann.color),
        "width": float(ann.width),
        "opacity": float(ann.opacity),
    }
    if ann.fill is not None:
        datos["fill"] = list(ann.fill)
    if ann.kind in (Kind.LINE, Kind.ARROW):
        datos["p1"] = list(ann.p1)
        datos["p2"] = list(ann.p2)
    if ann.kind is Kind.INK:
        datos["strokes"] = [[list(p) for p in trazo] for trazo in ann.strokes]
    if ann.kind in (Kind.TEXT, Kind.TABLE):
        datos.update(
            text=ann.text,
            font_size=float(ann.font_size),
            font=Font(ann.font).value,
            bold=bool(ann.bold),
            italic=bool(ann.italic),
            align=int(Align(ann.align)),
        )
    if ann.kind is Kind.TABLE:
        datos.update(rows=int(ann.rows), cols=int(ann.cols), cells=list(ann.cells))
    if ann.kind is Kind.IMAGE and ann.image_data:
        datos["image_name"] = ann.image_name
        datos["image_data"] = base64.b64encode(ann.image_data).decode("ascii")
    return datos


def annotation_from_dict(datos: dict) -> Annotation:
    """Reconstruye una anotacion guardada."""
    try:
        kind = Kind(datos["kind"])
    except (KeyError, ValueError) as exc:
        raise TemplateError(f"tipo de anotacion desconocido: {datos.get('kind')!r}") from exc
    ann = Annotation(kind=kind, page=int(datos.get("page", 0)))
    ann.rect = tuple(datos.get("rect", ann.rect))
    ann.color = tuple(datos.get("color", ann.color))
    ann.width = float(datos.get("width", ann.width))
    ann.opacity = float(datos.get("opacity", ann.opacity))
    if datos.get("fill") is not None:
        ann.fill = tuple(datos["fill"])
    ann.p1 = tuple(datos.get("p1", ann.p1))
    ann.p2 = tuple(datos.get("p2", ann.p2))
    ann.strokes = [[tuple(p) for p in trazo] for trazo in datos.get("strokes", [])]
    ann.text = str(datos.get("text", ""))
    ann.font_size = float(datos.get("font_size", ann.font_size))
    ann.font = Font(datos.get("font", Font.SANS.value))
    ann.bold = bool(datos.get("bold", False))
    ann.italic = bool(datos.get("italic", False))
    ann.align = Align(int(datos.get("align", 0)))
    ann.rows = int(datos.get("rows", ann.rows))
    ann.cols = int(datos.get("cols", ann.cols))
    ann.cells = list(datos.get("cells", []))
    ann.image_name = str(datos.get("image_name", ""))
    if datos.get("image_data"):
        ann.image_data = base64.b64decode(datos["image_data"])
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
    nombre = name.strip()
    if not nombre:
        raise TemplateError("La plantilla necesita un nombre.")
    os.makedirs(directory, exist_ok=True)
    contenido = {
        "version": FORMAT_VERSION,
        "name": nombre,
        "category": category if category in CATEGORIES else DEFAULT_CATEGORY,
        "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "pages": [{"width": float(w), "height": float(h)} for w, h in page_sizes],
        "annotations": [annotation_to_dict(a) for a in annotations if not a.is_empty()],
    }
    ruta = os.path.join(directory, safe_filename(nombre) + EXTENSION)
    temporal = ruta + ".tmp"
    try:
        with open(temporal, "w", encoding="utf-8") as fh:
            json.dump(contenido, fh, ensure_ascii=False, indent=1)
        os.replace(temporal, ruta)
    except OSError as exc:
        if os.path.exists(temporal):
            try:
                os.remove(temporal)
            except OSError:  # pragma: no cover
                pass
        raise TemplateError(f"No se pudo guardar la plantilla: {exc}") from exc
    return ruta


def load_template(path: str) -> tuple[str, list[tuple[float, float]], list[Annotation]]:
    """Lee una plantilla: devuelve (nombre, tamanos de pagina, anotaciones)."""
    try:
        with open(path, encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateError(f"No se pudo leer la plantilla: {exc}") from exc
    if not isinstance(datos, dict) or "annotations" not in datos:
        raise TemplateError("El archivo no parece una plantilla de easypdf.surf.")
    paginas = [
        (float(p.get("width", 595.0)), float(p.get("height", 842.0)))
        for p in datos.get("pages", [])
    ]
    anotaciones = [annotation_from_dict(d) for d in datos.get("annotations", [])]
    return str(datos.get("name") or os.path.basename(path)), paginas, anotaciones


def list_templates(directory: str) -> list[TemplateInfo]:
    """Plantillas guardadas en la carpeta, ordenadas por nombre."""
    if not os.path.isdir(directory):
        return []
    encontradas: list[TemplateInfo] = []
    for archivo in sorted(os.listdir(directory)):
        if not archivo.endswith(EXTENSION):
            continue
        ruta = os.path.join(directory, archivo)
        try:
            with open(ruta, encoding="utf-8") as fh:
                datos = json.load(fh)
            encontradas.append(
                TemplateInfo(
                    name=str(datos.get("name") or archivo),
                    path=ruta,
                    pages=len(datos.get("pages", [])),
                    annotations=len(datos.get("annotations", [])),
                    saved_at=str(datos.get("saved_at", "")),
                    category=str(datos.get("category") or DEFAULT_CATEGORY),
                )
            )
        except (OSError, json.JSONDecodeError):
            continue  # un archivo roto no debe romper la lista
    return sorted(encontradas, key=lambda t: t.name.lower())


def delete_template(path: str) -> None:
    try:
        os.remove(path)
    except OSError as exc:
        raise TemplateError(f"No se pudo borrar la plantilla: {exc}") from exc


def shift_to_page(annotations: Iterable[Annotation], first_page: int, page_count: int):
    """Recoloca las anotaciones de una plantilla a partir de la pagina indicada."""
    resultado = []
    for ann in annotations:
        copia = ann.copy()
        copia.id = Annotation(kind=copia.kind, page=0).id  # identidad nueva
        copia.page = min(max(0, first_page + ann.page), max(0, page_count - 1))
        resultado.append(copia)
    return resultado


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


def _texto(x, y, ancho, alto, texto, tam=12.0, negrita=False,
           align=Align.LEFT, color=(0.0, 0.0, 0.0)) -> Annotation:
    return Annotation(
        kind=Kind.TEXT, page=0, rect=(x, y, x + ancho, y + alto), text=texto,
        font_size=tam, bold=negrita, align=align, color=color, width=0.0,
    )


def builtin_templates() -> list[tuple[str, str, list[tuple[float, float]], list[Annotation]]]:
    """Plantillas que trae el programa: (nombre, tipo, paginas, anotaciones).

    Estan hechas con las mismas anotaciones que crearia el usuario, asi que
    una vez cargadas se pueden mover y editar como cualquier otra cosa.
    """
    linea = lambda y: Annotation(  # noqa: E731 - lectura mas corta
        kind=Kind.LINE, page=0, p1=(56.0, y), p2=(539.0, y),
        color=(0.72, 0.74, 0.78), width=0.8,
    )

    membrete = [
        _texto(56, 48, 300, 26, "NOMBRE DE LA EMPRESA", 15, True),
        _texto(56, 72, 300, 16, "Direccion - Telefono - Correo", 9,
               color=(0.42, 0.45, 0.5)),
        linea(96.0),
        _texto(56, 790, 483, 16, "Pagina 1", 9, align=Align.CENTER,
               color=(0.42, 0.45, 0.5)),
    ]

    carta = membrete[:3] + [
        _texto(56, 130, 483, 20, "Fecha:", 11),
        _texto(56, 158, 483, 20, "Para:", 11),
        _texto(56, 186, 483, 20, "Asunto:", 11, True),
        linea(212.0),
        _texto(56, 236, 483, 400, "", 11),
    ]

    acta = membrete[:3] + [
        _texto(56, 128, 483, 24, "ACTA DE REUNION", 14, True, Align.CENTER),
        _texto(56, 166, 240, 18, "Fecha:", 10),
        _texto(300, 166, 239, 18, "Lugar:", 10),
        _texto(56, 190, 483, 18, "Asistentes:", 10),
        linea(216.0),
        _texto(56, 228, 483, 18, "Acuerdos", 11, True),
        Annotation(kind=Kind.TABLE, page=0, rect=(56.0, 252.0, 539.0, 392.0),
                   rows=5, cols=3, cells=["Acuerdo", "Responsable", "Fecha"] + [""] * 12,
                   align=Align.LEFT, width=0.8, color=(0.2, 0.22, 0.26)),
    ]

    tabla = [
        _texto(56, 56, 483, 24, "Titulo del cuadro", 13, True),
        Annotation(kind=Kind.TABLE, page=0, rect=(56.0, 92.0, 539.0, 372.0),
                   rows=10, cols=4, cells=["Concepto", "Cantidad", "Precio", "Total"] + [""] * 36,
                   align=Align.LEFT, width=0.8, color=(0.2, 0.22, 0.26)),
    ]

    return [
        ("Membrete", "letterhead", [A4], membrete),
        ("Carta", "document", [A4], carta),
        ("Acta de reunion", "document", [A4], acta),
        ("Cuadro de datos", "table", [A4], tabla),
    ]


def builtin_infos() -> list[TemplateInfo]:
    """Las de serie, con el mismo aspecto que las guardadas por el usuario."""
    return [
        TemplateInfo(name=nombre, path=f"builtin:{nombre}", pages=len(paginas),
                     annotations=len(anns), category=tipo, builtin=True)
        for nombre, tipo, paginas, anns in builtin_templates()
    ]


def load_builtin(name: str):
    """Devuelve (nombre, paginas, anotaciones) de una plantilla de serie."""
    for nombre, _tipo, paginas, anns in builtin_templates():
        if nombre == name:
            return (nombre, list(paginas), [a.copy() for a in anns])
    raise TemplateError(f"No existe la plantilla incluida {name!r}")
