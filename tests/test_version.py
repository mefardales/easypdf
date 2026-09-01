"""The version has to say the same thing in every file.

The number appears in the package, in the installer, in the metadata Windows
shows under Properties and in pyproject.toml. When they drift apart, the site
ends up linking files that do not exist and the .exe declares a version other
than the one it carries. That happened once, so now it checks itself.
"""

from __future__ import annotations

import pathlib
import re

from easypdf import __version__

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_pyproject_declares_the_same_version():
    found = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M)
    assert found, "there is no version in pyproject.toml"
    assert found.group(1) == __version__


def test_the_installer_declares_the_same_version():
    text = _read("packaging/installer.iss")
    found = re.search(r'#define MyAppVersion "([^"]+)"', text)
    assert found, "there is no MyAppVersion in installer.iss"
    assert found.group(1) == __version__


def test_the_windows_metadata_declares_the_same_version():
    text = _read("packaging/version_info.txt")
    expected = tuple(int(p) for p in __version__.split(".")) + (0,)

    # the two numeric fields, which are what Windows actually reads
    for field in ("filevers", "prodvers"):
        found = re.search(rf"{field}=\(([^)]+)\)", text)
        assert found, f"there is no {field} in version_info.txt"
        numbers = tuple(int(n) for n in found.group(1).split(","))
        assert numbers == expected, f"{field} says {numbers} and the package {expected}"

    # and the text ones, which are what shows under Properties
    for field in ("FileVersion", "ProductVersion"):
        found = re.search(rf"StringStruct\('{field}', '([^']+)'\)", text)
        assert found, f"there is no {field} in version_info.txt"
        assert found.group(1) == f"{__version__}.0"


def test_the_site_links_the_packages_version():
    """The download links have to point at this version."""
    for page in ("site/index.html", "site/es/index.html"):
        links = re.findall(r"releases/download/v([\d.]+)/EasyPDF-([\d.]+)-", _read(page))
        assert links, f"{page} has no download links"
        for label, file in links:
            assert label == __version__, f"{page} links v{label}"
            assert file == __version__, f"{page} links the file {file}"
