"""The browser tools pages.

These checks need no browser: they read what the generator produced. The
tools are actually driven in a real Chromium by tests/test_tools_browser.py,
which skips itself when there is no browser to drive.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SLUGS = ["merge-pdf", "split-pdf", "organize-pdf", "delete-pages",
         "images-to-pdf", "pdf-to-image"]
PAGES = ([SITE / "tools" / "index.html"]
         + [SITE / "tools" / s / "index.html" for s in SLUGS]
         + [SITE / "es" / "tools" / "index.html"]
         + [SITE / "es" / "tools" / s / "index.html" for s in SLUGS])


def test_every_tool_page_exists_in_both_languages():
    missing = [str(p.relative_to(SITE)) for p in PAGES if not p.is_file()]
    assert not missing, f"pages not generated: {missing}"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(SITE)))
def test_no_placeholder_is_left_unfilled(page):
    """The same trap the landing fell into once: a renamed placeholder."""
    left = re.findall(r"\$\{?[a-zA-Z_]\w*\}?", page.read_text(encoding="utf-8"))
    assert not left, f"{page.name} still carries placeholders: {sorted(set(left))}"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(SITE)))
def test_every_asset_a_page_asks_for_is_there(page):
    """A tool that cannot load its script is a blank screen, not an error."""
    text = page.read_text(encoding="utf-8")
    for path in re.findall(r'(?:src|href)="(/[^"#]*)', text):
        target = SITE / path.strip("/")
        if path.endswith("/") or not target.suffix:
            target = target / "index.html"
        assert target.is_file(), f"{page.name} points at {path}, which is not there"


def test_the_texts_reach_the_page_in_the_right_language():
    english = (SITE / "tools" / "merge-pdf" / "index.html").read_text(encoding="utf-8")
    spanish = (SITE / "es" / "tools" / "merge-pdf" / "index.html").read_text(encoding="utf-8")
    assert "<h1>Merge PDF</h1>" in english
    assert "<h1>Unir PDF</h1>" in spanish
    # window.T carries what the script says out loud
    assert '"working": "Working..."' in english
    assert '"working": "Trabajando..."' in spanish


def test_each_language_gets_its_own_worker_and_manifest():
    """A service worker only reaches pages at or below its own path."""
    for folder in (SITE / "tools", SITE / "es" / "tools"):
        assert (folder / "sw.js").is_file(), f"{folder.name} has no worker"
        assert (folder / "manifest.webmanifest").is_file()
    a = json.loads((SITE / "tools" / "manifest.webmanifest").read_text(encoding="utf-8"))
    b = json.loads((SITE / "es" / "tools" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert a["id"] != b["id"]
    assert a["display"] == b["display"] == "standalone"
    for manifest in (a, b):
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        assert {"192x192", "512x512"} <= sizes
        assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])


def test_the_icons_the_manifest_promises_are_on_disk():
    for lang_dir in (SITE / "tools", SITE / "es" / "tools"):
        manifest = json.loads((lang_dir / "manifest.webmanifest").read_text(encoding="utf-8"))
        for icon in manifest["icons"]:
            src = icon["src"]
            target = SITE / src.lstrip("/") if src.startswith("/") else lang_dir / src
            assert target.is_file(), f"{src} is missing"


def test_the_libraries_are_served_from_the_site():
    """No CDN: an outside script could see the documents, and the promise is
    that nothing leaves the device."""
    vendor = SITE / "tools" / "vendor"
    for name in ("pdf-lib.min.js", "pdf.min.js", "pdf.worker.min.js"):
        assert (vendor / name).is_file(), f"{name} is not vendored"
    for name in ("pdf-lib.LICENSE.md", "pdfjs.LICENSE"):
        assert (vendor / name).is_file(), f"{name} is missing: both are needed"
    # Only what the browser executes or renders; canonical and hreflang links
    # are absolute on purpose and fetch nothing.
    runs = re.compile(r'<(?:script[^>]*\bsrc|img[^>]*\bsrc|link[^>]*rel="stylesheet"[^>]*href)'
                      r'="(https?://[^"]+)"')
    for page in PAGES:
        outside = runs.findall(page.read_text(encoding="utf-8"))
        assert not outside, f"{page.name} loads something from outside: {outside}"


def test_the_sitemap_lists_every_tool():
    sitemap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    for lang in ("/tools/", "/es/tools/"):
        assert f"<loc>https://easypdf.surf{lang}</loc>" in sitemap
        for slug in SLUGS:
            assert f"<loc>https://easypdf.surf{lang}{slug}/</loc>" in sitemap


def test_the_landing_links_to_the_tools():
    assert '/tools/">Tools</a>' in (SITE / "index.html").read_text(encoding="utf-8")
    assert '/es/tools/">Herramientas</a>' in (SITE / "es" / "index.html").read_text(
        encoding="utf-8"
    )
