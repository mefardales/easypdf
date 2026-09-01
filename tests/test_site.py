"""The generated site has to match what is committed.

A rename in the generator once left ``$title`` and ``$description`` sitting in
the published pages, because the placeholders in the HTML template were not
renamed with them. ``safe_substitute`` says nothing when that happens, so this
is what catches it.

Covers the landing pages and the browser tools, both of which are written by
tools/build_site.py.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


TOOLS = ["merge-pdf", "split-pdf", "organize-pdf", "delete-pages",
         "images-to-pdf", "pdf-to-image"]


def _pages() -> list[pathlib.Path]:
    site = ROOT / "site"
    pages = [site / "index.html", site / "es" / "index.html"]
    for folder in (site / "tools", site / "es" / "tools"):
        pages.append(folder / "index.html")
        pages.extend(folder / slug / "index.html" for slug in TOOLS)
    return pages


def test_no_placeholder_is_left_unfilled():
    for page in _pages():
        text = page.read_text(encoding="utf-8")
        left = re.findall(r"\$\{?[a-zA-Z_]\w*\}?", text)
        assert not left, f"{page.name} still carries placeholders: {sorted(set(left))}"


def test_the_sitemap_does_not_claim_everything_changed_today():
    """A lastmod that is always "now" is noise: search engines learn to ignore
    it, and it also made a rebuild differ from the committed site for no
    reason. The date only moves when the page really changes."""
    sitemap = (ROOT / "site" / "sitemap.xml").read_text(encoding="utf-8")
    before = re.findall(r"<lastmod>([^<]+)</lastmod>", sitemap)
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_site.py")],
                   capture_output=True, cwd=str(ROOT), timeout=120, check=True)
    after = re.findall(r"<lastmod>([^<]+)</lastmod>",
                       (ROOT / "site" / "sitemap.xml").read_text(encoding="utf-8"))
    assert before == after, "rebuilding moved the dates without anything changing"


def test_every_template_placeholder_is_given_a_value(tmp_path):
    """Regenerating must reproduce the committed pages exactly."""
    before = {page: page.read_text(encoding="utf-8") for page in _pages()}
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_site.py")],
        capture_output=True, cwd=str(ROOT), timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode()[-400:]
    for page, text in before.items():
        assert page.read_text(encoding="utf-8") == text, (
            f"{page.name} changes when regenerated: the generator and the "
            f"committed page have drifted apart"
        )
