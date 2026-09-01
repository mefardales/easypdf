"""The generated site has to match what is committed.

A rename in the generator once left ``$title`` and ``$description`` sitting in
the published pages, because the placeholders in the HTML template were not
renamed with them. ``safe_substitute`` says nothing when that happens, so this
is what catches it.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _pages() -> list[pathlib.Path]:
    return [ROOT / "site" / "index.html", ROOT / "site" / "es" / "index.html"]


def test_no_placeholder_is_left_unfilled():
    for page in _pages():
        text = page.read_text(encoding="utf-8")
        left = re.findall(r"\$\{?[a-zA-Z_]\w*\}?", text)
        assert not left, f"{page.name} still carries placeholders: {sorted(set(left))}"


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
