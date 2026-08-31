"""Piezas sueltas para montar formularios.

Las plantillas traen documentos enteros; esto son los ladrillos con los que
se construyen: un campo con su raya, una casilla, una linea de firma, una
tabla. Se insertan donde este mirando el usuario y a partir de ahi se editan
y se mueven como cualquier otra anotacion, porque eso es lo que son.

No dependen de Qt a proposito: son datos del documento, igual que
templates.py, y asi se pueden probar sin levantar una ventana.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Align, Annotation, Kind
from .templates import GRIS, LINEA, TINTA, _t

#: Ancho por omision de una pieza, en puntos PDF. Cabe de sobra en un A4
#: con margenes y deja sitio para poner dos en paralelo.
WIDTH = 240.0

#: Lado de una casilla de verificacion.
BOX = 11.0

#: Grupos en los que se ensenan las piezas.
CATEGORIES = ("field", "choice", "signature", "layout")


@dataclass(frozen=True)
class ElementInfo:
    """Una pieza del catalogo: su clave, su nombre traducido y su grupo."""

    key: str
    name: str
    category: str


#: key -> categoria. El orden es el que se ve en el panel.
ELEMENTS: dict[str, str] = {
    "text_field": "field",
    "long_field": "field",
    "date_field": "field",
    "boxed_field": "field",
    "checkbox": "choice",
    "checklist": "choice",
    "yes_no": "choice",
    "signature": "signature",
    "two_signatures": "signature",
    "place_date": "signature",
    "heading": "layout",
    "separator": "layout",
    "table": "layout",
    "note_box": "layout",
}


def element_infos() -> list[ElementInfo]:
    """El catalogo entero, con los nombres en el idioma de la interfaz."""
    from .i18n import tr

    return [ElementInfo(clave, tr(f"el_{clave}"), grupo)
            for clave, grupo in ELEMENTS.items()]


# ------------------------------------------------------------------ piezas
def _texto(x, y, ancho, alto, texto, tam=10.0, negrita=False,
           align=Align.LEFT, color=TINTA) -> Annotation:
    return Annotation(
        kind=Kind.TEXT, page=0, rect=(x, y, x + ancho, y + alto), text=texto,
        font_size=tam, bold=negrita, align=align, color=color, width=0.0,
    )


def _raya(x0, y, x1, color=LINEA, grosor=0.8) -> Annotation:
    return Annotation(kind=Kind.LINE, page=0, p1=(x0, y), p2=(x1, y),
                      color=color, width=grosor)


def _caja(x, y, ancho, alto, color=LINEA, grosor=0.8) -> Annotation:
    return Annotation(kind=Kind.RECT, page=0, rect=(x, y, x + ancho, y + alto),
                      color=color, width=grosor)


def _campo(x, y, ancho, etiqueta) -> list[Annotation]:
    """Etiqueta encima y raya debajo, que es como se rellena a mano."""
    return [_texto(x, y, ancho, 12, etiqueta, 9, color=GRIS),
            _raya(x, y + 26, x + ancho)]


def _casilla(x, y, etiqueta, ancho=WIDTH) -> list[Annotation]:
    # El cuadro baja 2 pt para quedar centrado con la altura de la letra. Baja
    # el cuadro y no sube el texto: asi la pieza empieza exactamente en (x, y)
    # y se puede colocar sin sorpresas.
    return [_caja(x, y + 2, BOX, BOX),
            _texto(x + BOX + 8, y, ancho - BOX - 8, 15, etiqueta)]


def _firma(x, y, ancho, pie) -> list[Annotation]:
    # La raya va justo en (x, y): el hueco para firmar es el que quede encima,
    # y lo decide el usuario al soltar la pieza. Reservarlo aqui solo hacia que
    # la pieza no cayera donde se la pedia.
    return [_raya(x, y, x + ancho),
            _texto(x, y + 4, ancho, 12, pie, 9, align=Align.CENTER, color=GRIS)]


def build(key: str, x: float, y: float, width: float = WIDTH) -> list[Annotation]:
    """Crea la pieza con su esquina superior izquierda en (x, y).

    Devuelve una lista de anotaciones ya colocadas, en la pagina 0: quien la
    inserte se encarga de ponerles la pagina que toque.
    """
    ancho = max(60.0, float(width))
    mitad = (ancho - 20.0) / 2.0

    if key == "text_field":
        return _campo(x, y, ancho, _t("label"))
    if key == "long_field":
        piezas = [_texto(x, y, ancho, 12, _t("label"), 9, color=GRIS)]
        for fila in range(3):
            piezas.append(_raya(x, y + 26 + fila * 22, x + ancho))
        return piezas
    if key == "date_field":
        return _campo(x, y, min(ancho, 150.0), _t("date"))
    if key == "boxed_field":
        return [_texto(x, y, ancho, 12, _t("label"), 9, color=GRIS),
                _caja(x, y + 16, ancho, 56)]
    if key == "checkbox":
        return _casilla(x, y, _t("option"), ancho)
    if key == "checklist":
        piezas: list[Annotation] = []
        for fila in range(4):
            piezas += _casilla(x, y + fila * 22, f"{_t('option')} {fila + 1}", ancho)
        return piezas
    if key == "yes_no":
        return _casilla(x, y, _t("yes"), mitad) + _casilla(x + mitad + 20, y, _t("no"), mitad)
    if key == "signature":
        return _firma(x, y, ancho, _t("signature"))
    if key == "two_signatures":
        return _firma(x, y, mitad, _t("signature")) + _firma(x + mitad + 20, y, mitad,
                                                             _t("signature"))
    if key == "place_date":
        return _campo(x, y, mitad, _t("place")) + _campo(x + mitad + 20, y, mitad, _t("date"))
    if key == "heading":
        return [_texto(x, y, ancho, 20, _t("heading"), 13, True),
                _raya(x, y + 24, x + ancho, TINTA, 1.0)]
    if key == "separator":
        return [_raya(x, y, x + ancho)]
    if key == "table":
        cabeceras = [_t("concept"), _t("qty"), _t("value")]
        return [Annotation(
            kind=Kind.TABLE, page=0, rect=(x, y, x + ancho, y + 96),
            rows=4, cols=3, cells=cabeceras + [""] * 9,
            align=Align.LEFT, width=0.8, color=TINTA,
        )]
    if key == "note_box":
        return [_texto(x, y, ancho, 12, _t("notes_short"), 9, color=GRIS),
                _caja(x, y + 16, ancho, 80)]
    raise KeyError(f"no existe la pieza {key!r}")


def size_of(key: str) -> tuple[float, float]:
    """Cuanto ocupa una pieza, para poder centrarla al insertarla."""
    piezas = build(key, 0.0, 0.0)
    x0 = min(min(a.bounds()[0], a.bounds()[2]) for a in piezas)
    y0 = min(min(a.bounds()[1], a.bounds()[3]) for a in piezas)
    x1 = max(max(a.bounds()[0], a.bounds()[2]) for a in piezas)
    y1 = max(max(a.bounds()[1], a.bounds()[3]) for a in piezas)
    return (x1 - x0, y1 - y0)


__all__ = ["BOX", "CATEGORIES", "ELEMENTS", "ElementInfo", "WIDTH", "build",
           "element_infos", "size_of"]
