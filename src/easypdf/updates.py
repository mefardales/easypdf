"""Aviso de version nueva.

El programa instalado consulta un archivo pequeno en la web oficial y, si hay
una version mas nueva, lo dice y ofrece ir a descargarla. No descarga ni
instala nada por su cuenta: eso lo decide siempre el usuario.

La consulta es una peticion GET sin enviar ningun dato: ni identificador, ni
que documentos se abren, ni nada. Si no hay internet, falla en silencio.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

#: De donde se lee la ultima version publicada. Lo genera la propia web.
LATEST_URL = "https://easypdf.surf/latest.json"

#: Cuanto se espera antes de rendirse, en segundos. Corto a proposito: esto
#: no puede entretener el arranque del programa.
TIMEOUT = 6.0


def parse_version(text: str) -> tuple[int, ...]:
    """Convierte '1.2.0' en (1, 2, 0) para poder comparar.

    Lo que no sean numeros se ignora, asi que '1.2.0-beta' vale como (1, 2, 0).
    Una cadena sin ningun numero da (0,), que pierde contra cualquier version.
    """
    partes: list[int] = []
    for trozo in str(text).strip().lstrip("vV").split("."):
        digitos = ""
        for caracter in trozo:
            if not caracter.isdigit():
                break
            digitos += caracter
        if not digitos:
            break
        partes.append(int(digitos))
    return tuple(partes) if partes else (0,)


def is_newer(candidate: str, current: str) -> bool:
    """True si ``candidate`` es una version posterior a ``current``."""
    return parse_version(candidate) > parse_version(current)


def fetch_latest(url: str = LATEST_URL, timeout: float = TIMEOUT) -> dict | None:
    """Lee el archivo de la web. Devuelve None si no se puede."""
    peticion = urllib.request.Request(
        url,
        headers={"User-Agent": "easypdf.surf", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError, TimeoutError):
        return None            # sin internet, o la web no contesta: da igual
    return datos if isinstance(datos, dict) else None


def check(current: str, url: str = LATEST_URL, timeout: float = TIMEOUT) -> dict | None:
    """Devuelve los datos de la version nueva, o None si no hay novedad."""
    datos = fetch_latest(url, timeout)
    if not datos:
        return None
    version = str(datos.get("version", "")).strip()
    if not version or not is_newer(version, current):
        return None
    return datos


__all__ = ["LATEST_URL", "TIMEOUT", "check", "fetch_latest", "is_newer", "parse_version"]
