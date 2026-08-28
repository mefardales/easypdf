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
) -> str:
    """Guarda una plantilla y devuelve la ruta del archivo."""
    nombre = name.strip()
    if not nombre:
        raise TemplateError("La plantilla necesita un nombre.")
    os.makedirs(directory, exist_ok=True)
    contenido = {
        "version": FORMAT_VERSION,
        "name": nombre,
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
