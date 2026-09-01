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


def test_pyproject_declares_the_same_version():
    found = re.search(r'^version\s*=\s*"([^"]+)"', _leer("pyproject.toml"), re.M)
    assert found, "no hay version en pyproject.toml"
    assert found.group(1) == __version__


def test_the_installer_declares_the_same_version():
    text = _leer("packaging/installer.iss")
    found = re.search(r'#define MyAppVersion "([^"]+)"', text)
    assert found, "no hay MyAppVersion en installer.iss"
    assert found.group(1) == __version__


def test_the_windows_metadata_declares_the_same_version():
    text = _leer("packaging/version_info.txt")
    expected = tuple(int(p) for p in __version__.split(".")) + (0,)

    # los dos campos numericos, que son los que lee Windows de verdad
    for campo in ("filevers", "prodvers"):
        found = re.search(rf"{campo}=\(([^)]+)\)", text)
        assert found, f"no hay {campo} en version_info.txt"
        numeros = tuple(int(n) for n in found.group(1).split(","))
        assert numeros == expected, f"{campo} dice {numeros} y el paquete {expected}"

    # y los de texto, que son los que se ven en Propiedades
    for campo in ("FileVersion", "ProductVersion"):
        found = re.search(rf"StringStruct\('{campo}', '([^']+)'\)", text)
        assert found, f"no hay {campo} en version_info.txt"
        assert found.group(1) == f"{__version__}.0"


def test_the_site_links_the_packages_version():
    """Los enlaces de descarga tienen que apuntar a esta version."""
    for page_item in ("site/index.html", "site/es/index.html"):
        enlaces = re.findall(r"releases/download/v([\d.]+)/EasyPDF-([\d.]+)-", _leer(page_item))
        assert enlaces, f"{page_item} no tiene enlaces de descarga"
        for label, file in enlaces:
            assert label == __version__, f"{page_item} enlaza la v{label}"
            assert file == __version__, f"{page_item} enlaza el archivo {file}"
