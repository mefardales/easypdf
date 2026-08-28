"""La version tiene que decir lo mismo en todos los archivos.

El numero aparece en el paquete, en el instalador, en los metadatos que
Windows ensena en Propiedades y en pyproject.toml. Cuando se descuadran, la
web acaba enlazando archivos que no existen y el .exe declara una version
distinta de la que trae. Ya paso una vez, asi que se comprueba sola.
"""

from __future__ import annotations

import pathlib
import re

from easypdf import __version__

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _leer(relativa: str) -> str:
    return (RAIZ / relativa).read_text(encoding="utf-8")


def test_pyproject_declara_la_misma_version():
    encontrado = re.search(r'^version\s*=\s*"([^"]+)"', _leer("pyproject.toml"), re.M)
    assert encontrado, "no hay version en pyproject.toml"
    assert encontrado.group(1) == __version__


def test_el_instalador_declara_la_misma_version():
    texto = _leer("packaging/installer.iss")
    encontrado = re.search(r'#define MyAppVersion "([^"]+)"', texto)
    assert encontrado, "no hay MyAppVersion en installer.iss"
    assert encontrado.group(1) == __version__


def test_los_metadatos_de_windows_declaran_la_misma_version():
    texto = _leer("packaging/version_info.txt")
    esperado = tuple(int(p) for p in __version__.split(".")) + (0,)

    # los dos campos numericos, que son los que lee Windows de verdad
    for campo in ("filevers", "prodvers"):
        encontrado = re.search(rf"{campo}=\(([^)]+)\)", texto)
        assert encontrado, f"no hay {campo} en version_info.txt"
        numeros = tuple(int(n) for n in encontrado.group(1).split(","))
        assert numeros == esperado, f"{campo} dice {numeros} y el paquete {esperado}"

    # y los de texto, que son los que se ven en Propiedades
    for campo in ("FileVersion", "ProductVersion"):
        encontrado = re.search(rf"StringStruct\('{campo}', '([^']+)'\)", texto)
        assert encontrado, f"no hay {campo} en version_info.txt"
        assert encontrado.group(1) == f"{__version__}.0"


def test_la_web_enlaza_la_version_del_paquete():
    """Los enlaces de descarga tienen que apuntar a esta version."""
    for pagina in ("site/index.html", "site/es/index.html"):
        enlaces = re.findall(r"releases/download/v([\d.]+)/EasyPDF-([\d.]+)-", _leer(pagina))
        assert enlaces, f"{pagina} no tiene enlaces de descarga"
        for etiqueta, archivo in enlaces:
            assert etiqueta == __version__, f"{pagina} enlaza la v{etiqueta}"
            assert archivo == __version__, f"{pagina} enlaza el archivo {archivo}"
