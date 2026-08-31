"""Aviso de version nueva.

El programa instalado consulta un archivo pequeno en la web oficial y, si hay
una version mas nueva, lo dice y ofrece descargarla e instalarla. Nada de eso
pasa solo: la descarga solo empieza si el usuario pulsa el boton.

La consulta es una peticion GET sin enviar ningun dato: ni identificador, ni
que documentos se abren, ni nada. Si no hay internet, falla en silencio.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
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


# ---------------------------------------------------------------- descarga
#: Cuanto se lee de golpe al descargar.
CHUNK = 256 * 1024


class DownloadError(RuntimeError):
    """No se pudo descargar o el archivo no llego intacto."""


def asset_for_platform(datos: dict) -> tuple[str, str] | None:
    """Devuelve (url, nombre de archivo) del paquete que toca en este sistema."""
    if sys.platform.startswith("win"):
        clave = "setup"
    elif sys.platform.startswith("linux"):
        clave = "linux"
    else:
        return None                    # en Mac no hay paquete todavia
    url = str(datos.get(clave) or "")
    if not url:
        return None
    return (url, url.rsplit("/", 1)[-1])


def sha256_of(path: str) -> str:
    resumen = hashlib.sha256()
    with open(path, "rb") as fh:
        for trozo in iter(lambda: fh.read(CHUNK), b""):
            resumen.update(trozo)
    return resumen.hexdigest()


def expected_sha256(url: str, timeout: float = TIMEOUT) -> str | None:
    """Lee el .sha256 que acompana a cada descarga."""
    datos = _get(url + ".sha256", timeout)
    if datos is None:
        return None
    primero = datos.decode("utf-8", "replace").strip().split()
    return primero[0].lower() if primero else None


def _get(url: str, timeout: float) -> bytes | None:
    peticion = urllib.request.Request(url, headers={"User-Agent": "easypdf.surf"})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return respuesta.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def download(url: str, destino: str, on_progress=None, cancelled=None,
             timeout: float = 30.0) -> str:
    """Descarga un archivo y devuelve su ruta.

    ``on_progress(bajado, total)`` se llama mientras avanza (total puede ser 0
    si el servidor no lo dice), y ``cancelled()`` permite abortar.
    """
    peticion = urllib.request.Request(url, headers={"User-Agent": "easypdf.surf"})
    parcial = destino + ".parte"
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            total = int(respuesta.headers.get("Content-Length") or 0)
            bajado = 0
            with open(parcial, "wb") as fh:
                while True:
                    if cancelled is not None and cancelled():
                        raise DownloadError("cancelado")
                    trozo = respuesta.read(CHUNK)
                    if not trozo:
                        break
                    fh.write(trozo)
                    bajado += len(trozo)
                    if on_progress is not None:
                        on_progress(bajado, total)
        os.replace(parcial, destino)
    except DownloadError:
        _borrar(parcial)
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _borrar(parcial)
        raise DownloadError(str(exc)) from exc
    return destino


def _borrar(ruta: str) -> None:
    try:
        os.remove(ruta)
    except OSError:
        pass


def download_verified(url: str, destino: str, on_progress=None, cancelled=None,
                      timeout: float = 30.0) -> str:
    """Descarga y comprueba el sha256 antes de dar el archivo por bueno.

    Es imprescindible: lo que se baja aqui se va a ejecutar para instalar, asi
    que hay que asegurarse de que es exactamente lo que se publico.
    """
    esperado = expected_sha256(url, timeout=TIMEOUT)
    download(url, destino, on_progress, cancelled, timeout)
    if esperado:
        real = sha256_of(destino)
        if real != esperado:
            _borrar(destino)
            raise DownloadError(
                f"la descarga no coincide con la publicada ({real[:12]} != {esperado[:12]})"
            )
    return destino


def is_installer(path: str) -> bool:
    """True si lo descargado es algo que se puede ejecutar para instalar.

    Solo el .exe de Windows: en Linux se publica un paquete portable, que se
    descomprime a mano encima de la copia que ya se tenga.
    """
    return os.name == "nt" and path.lower().endswith(".exe")


def launch_installer(path: str) -> None:
    """Arranca el instalador y lo deja seguir por su cuenta.

    Se lanza suelto a proposito: el programa se cierra justo despues, porque
    el instalador tiene que poder sustituir sus propios archivos.
    """
    if not is_installer(path):
        raise DownloadError(f"no se puede instalar {path}")
    os.startfile(path)  # type: ignore[attr-defined]  # solo existe en Windows


__all__ = [
    "CHUNK", "DownloadError", "LATEST_URL", "TIMEOUT", "asset_for_platform",
    "check", "download", "download_verified", "expected_sha256", "fetch_latest",
    "is_installer", "is_newer", "launch_installer", "parse_version", "sha256_of",
]
