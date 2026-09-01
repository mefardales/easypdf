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


def test_one_worker_and_one_manifest_cover_the_whole_site():
    """A worker at the root reaches /es/ and /tools/ too.

    There used to be one per language, and each cleaned up "every cache that
    is not mine" - so they took turns wiping each other.
    """
    assert (SITE / "sw.js").is_file()
    assert (SITE / "manifest.webmanifest").is_file()
    assert not (SITE / "tools" / "sw.js").exists(), "a second worker is back"
    assert not (SITE / "es" / "tools" / "sw.js").exists()

    manifest = json.loads((SITE / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["scope"] == "/"
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])


def test_the_icons_the_manifest_promises_are_on_disk():
    manifest = json.loads((SITE / "manifest.webmanifest").read_text(encoding="utf-8"))
    for icon in manifest["icons"]:
        assert (SITE / icon["src"].lstrip("/")).is_file(), f"{icon['src']} is missing"


def test_every_page_of_the_site_is_installable():
    """The landing pages too: most people arrive there, not at a tool."""
    for page in [SITE / "index.html", SITE / "es" / "index.html"] + PAGES:
        text = page.read_text(encoding="utf-8")
        assert 'rel="manifest" href="/manifest.webmanifest"' in text, page.name
        assert "/sw.js" in text, f"{page.name} does not register the worker"


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


# -- the landing, which is where most visitors arrive ---------------------
LANDINGS = [SITE / "index.html", SITE / "es" / "index.html"]


@pytest.mark.parametrize("page", LANDINGS, ids=lambda p: str(p.relative_to(SITE)))
def test_the_landing_shows_the_tools_without_scrolling_far(page):
    """On a phone the header links are hidden to save room, so the tools have
    to be reachable some other way: a pill in the header that survives the
    media query, and the six of them right under the hero."""
    text = page.read_text(encoding="utf-8")
    assert 'class="nl nl-keep"' in text, "the Tools link is hidden on mobile"
    assert 'class="tools-strip"' in text
    assert text.count('<li><a href="/tools/' if page.parent.name != "es"
                      else '<li><a href="/es/tools/') == 6


@pytest.mark.parametrize("page", LANDINGS + PAGES, ids=lambda p: str(p.relative_to(SITE)))
def test_every_page_carries_what_search_engines_read(page):
    text = page.read_text(encoding="utf-8")
    for needed in ('<link rel="canonical"',
                   'hreflang="en"', 'hreflang="es"', 'hreflang="x-default"',
                   'property="og:title"', 'property="og:description"',
                   'property="og:image"', 'name="twitter:card"',
                   'application/ld+json'):
        assert needed in text, f"{page.name} is missing {needed}"
    assert text.count("<h1") == 1, f"{page.name} does not have exactly one h1"

    title = re.search(r"<title>(.*?)</title>", text, re.S).group(1)
    description = re.search(r'name="description" content="(.*?)"', text, re.S).group(1)
    assert 25 <= len(title) <= 65, f"{page.name}: title is {len(title)} characters"
    assert 70 <= len(description) <= 160, f"{page.name}: description is {len(description)}"


def test_the_tool_pages_declare_their_breadcrumbs():
    """It is what puts a trail in the search result instead of a bare URL."""
    text = (SITE / "tools" / "merge-pdf" / "index.html").read_text(encoding="utf-8")
    blocks = re.findall(r'application/ld\+json">(.*?)</script>', text, re.S)
    data = json.loads(blocks[0])
    kinds = {item["@type"] for item in data}
    assert kinds == {"WebApplication", "BreadcrumbList"}, kinds
    crumbs = next(item for item in data if item["@type"] == "BreadcrumbList")
    assert [c["name"] for c in crumbs["itemListElement"]] == ["Home", "Tools", "Merge PDF"]
    assert [c["position"] for c in crumbs["itemListElement"]] == [1, 2, 3]


def test_the_screenshot_is_also_served_as_webp():
    """It is the heaviest thing on the landing, and page speed is ranked."""
    png = SITE / "screenshot.png"
    webp = SITE / "screenshot.webp"
    assert webp.is_file(), "no webp alongside the png"
    assert webp.stat().st_size < png.stat().st_size * 0.6
    text = (SITE / "index.html").read_text(encoding="utf-8")
    assert '<source srcset="/screenshot.webp" type="image/webp">' in text
    assert 'src="/screenshot.png"' in text, "no fallback for browsers without webp"
