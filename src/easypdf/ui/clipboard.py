"""Copiar y pegar anotaciones por el portapapeles del sistema.

Se usa el portapapeles de verdad, y no una variable interna, para poder
copiar en una ventana y pegar en otra. El contenido va con un tipo MIME
propio: asi solo lo entiende este programa y no se confunde con un texto
cualquiera que hubiera copiado el usuario.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication

from ..model import Annotation
from ..templates import TemplateError, annotation_from_dict, annotation_to_dict

#: Tipo MIME propio. Lleva el nombre del programa para no chocar con nada.
MIME = "application/x-easypdf-annotations"

#: Version del formato, por si algun dia cambia lo que se guarda.
FORMAT = 1


def _clipboard():
    aplicacion = QGuiApplication.instance()
    return aplicacion.clipboard() if aplicacion is not None else None


def encode(annotations) -> str:
    """Serializa las anotaciones en el texto que viaja por el portapapeles."""
    return json.dumps(
        {"easypdf": FORMAT, "annotations": [annotation_to_dict(a) for a in annotations]},
        ensure_ascii=False,
    )


def decode(texto: str) -> list[Annotation]:
    """Lee lo que hubiera copiado. Devuelve [] si no es nuestro."""
    try:
        datos = json.loads(texto)
    except (ValueError, TypeError):
        return []
    if not isinstance(datos, dict) or "easypdf" not in datos:
        return []
    resultado = []
    for entrada in datos.get("annotations") or []:
        try:
            resultado.append(annotation_from_dict(entrada))
        except (TemplateError, TypeError, ValueError, KeyError):
            continue          # una anotacion rota no tira las demas
    return resultado


def copy_annotations(annotations) -> int:
    """Deja las anotaciones en el portapapeles. Devuelve cuantas."""
    lista = list(annotations)
    portapapeles = _clipboard()
    if not lista or portapapeles is None:
        return 0
    texto = encode(lista)
    datos = QMimeData()
    datos.setData(MIME, texto.encode("utf-8"))
    # Tambien como texto: no estorba, y deja ver lo copiado si hace falta.
    datos.setText(texto)
    portapapeles.setMimeData(datos)
    return len(lista)


def clipboard_annotations() -> list[Annotation]:
    """Lo que haya copiado de este programa, o [] si no hay nada suyo."""
    portapapeles = _clipboard()
    if portapapeles is None:
        return []
    datos = portapapeles.mimeData()
    if datos is None:
        return []
    if datos.hasFormat(MIME):
        return decode(bytes(datos.data(MIME)).decode("utf-8", "replace"))
    if datos.hasText():
        # Algunos escritorios pierden los tipos MIME propios entre procesos,
        # pero el texto sobrevive: si resulta ser nuestro, vale igual.
        return decode(datos.text())
    return []


def has_annotations() -> bool:
    return bool(clipboard_annotations())


__all__ = [
    "FORMAT", "MIME", "clipboard_annotations", "copy_annotations", "decode",
    "encode", "has_annotations",
]
