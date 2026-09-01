"""The browser tools, driven in a real browser on a phone-sized screen.

These tools only exist inside a browser, so this is the only way to know they
work: a real Chromium loads the page, picks real files, presses the button,
and what comes out is opened again with PyMuPDF and Pillow to see that it is
what it claims to be.

Skipped when there is no browser to drive, which is the case on the CI
runners; ``pip install playwright && playwright install chromium`` is all it
takes to run them locally.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import io
import os
import pathlib
import socketserver
import threading
import zipfile

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright is not installed")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def _browser_path() -> str | None:
    """Where Chromium is, if it is anywhere."""
    bundled = pathlib.Path("/opt/pw-browsers/chromium")
    if bundled.exists():
        return str(bundled)
    return None                      # let Playwright use its own, or skip


@pytest.fixture(scope="module")
def site_url():
    """Serves site/ on a spare port: file:// has no service workers."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    handler.log_message = lambda *args: None

    # Threaded on purpose: a browser opens several connections at once, and a
    # single-threaded server made the service worker's precache fail.
    class Quiet(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass                     # a dropped connection is not a failure

    with Quiet(("127.0.0.1", 0), handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
        httpd.shutdown()


@pytest.fixture(scope="module")
def phone(site_url):
    """A page in a phone-shaped browser, with downloads captured."""
    with sync_playwright() as pw:
        path = _browser_path()
        try:
            browser = pw.chromium.launch(executable_path=path) if path else pw.chromium.launch()
        except Exception as exc:                       # pragma: no cover - no browser
            pytest.skip(f"no browser to drive: {exc}")
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, device_scale_factor=2,
            is_mobile=True, has_touch=True, accept_downloads=True,
        )
        page = context.new_page()
        page.problems = []
        page.on("pageerror", lambda e: page.problems.append(str(e)))
        page.on("console", lambda m: m.type == "error" and page.problems.append(m.text))
        page.site = site_url
        page.context_ref = context
        yield page
        browser.close()


@pytest.fixture()
def samples(tmp_path_factory):
    """Two short PDFs, one of four pages, and a couple of images."""
    import pymupdf
    from PIL import Image

    folder = tmp_path_factory.mktemp("samples")
    for name, pages, word in (("a.pdf", 2, "Alpha"), ("b.pdf", 3, "Beta"),
                              ("four.pdf", 4, "Page")):
        doc = pymupdf.open()
        for i in range(pages):
            doc.new_page().insert_text((72, 120), f"{word} {i + 1}", fontsize=28)
        doc.save(folder / name)
        doc.close()
    Image.new("RGB", (800, 600), (200, 60, 60)).save(folder / "red.jpg")
    Image.new("RGBA", (400, 900), (40, 90, 200, 255)).save(folder / "blue.png")
    return folder


def _use(page, tool, files, before_go=None, tmp_path=None):
    """Open a tool, feed it files, press the button, return what it hands back."""
    page.goto(f"{page.site}/tools/{tool}/", wait_until="networkidle")
    page.set_input_files("#file", [str(f) for f in files])
    page.wait_for_selector("#go:not([disabled])", timeout=20000)
    if before_go:
        before_go()
    page.click("#go")
    page.wait_for_selector("#done:not([hidden]) a.dl", timeout=90000)
    with page.expect_download() as caught:
        page.locator("#done a.dl").first.click()
    target = pathlib.Path(tmp_path) / caught.value.suggested_filename
    caught.value.save_as(target)
    return target


def test_merging_puts_the_files_one_after_another(phone, samples, tmp_path):
    import pymupdf

    out = _use(phone, "merge-pdf", [samples / "a.pdf", samples / "b.pdf"], tmp_path=tmp_path)
    with contextlib.closing(pymupdf.open(out)) as doc:
        assert doc.page_count == 5
        assert "Alpha 1" in doc[0].get_text()
        assert "Beta 1" in doc[2].get_text()      # in the order they were listed


def test_a_page_range_takes_out_just_those_pages(phone, samples, tmp_path):
    import pymupdf

    out = _use(phone, "split-pdf", [samples / "four.pdf"],
               lambda: phone.fill("#range", "2-3"), tmp_path)
    with contextlib.closing(pymupdf.open(out)) as doc:
        assert doc.page_count == 2
        assert "Page 2" in doc[0].get_text()
        assert "Page 3" in doc[1].get_text()


def test_splitting_into_one_file_per_page_gives_a_readable_zip(phone, samples, tmp_path):
    """The zip is written by hand, so the CRC of every entry has to be right."""
    import pymupdf

    out = _use(phone, "split-pdf", [samples / "four.pdf"],
               lambda: phone.click('#mode button[data-mode="each"]'), tmp_path)
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as bundle:
        names = bundle.namelist()
        assert len(names) == 4
        first = bundle.read(names[0])             # this is what checks the CRC
    with contextlib.closing(pymupdf.open(stream=first, filetype="pdf")) as doc:
        assert doc.page_count == 1


def test_turning_and_moving_pages_reaches_the_saved_file(phone, samples, tmp_path):
    import pymupdf

    def rearrange():
        phone.click("#rot-all")
        for _ in range(3):                        # walk page 1 to the end
            phone.locator('.card[data-i="0"] .acts button').nth(2).click()

    out = _use(phone, "organize-pdf", [samples / "four.pdf"], rearrange, tmp_path)
    with contextlib.closing(pymupdf.open(out)) as doc:
        assert doc.page_count == 4
        assert "Page 1" in doc[3].get_text()
        assert doc[0].rotation == 90


def test_deleting_pages_keeps_the_rest_in_order(phone, samples, tmp_path):
    import pymupdf

    def drop_two():
        phone.locator('.card[data-i="1"] .acts button').click()
        phone.locator('.card[data-i="3"] .acts button').click()

    out = _use(phone, "delete-pages", [samples / "four.pdf"], drop_two, tmp_path)
    with contextlib.closing(pymupdf.open(out)) as doc:
        assert doc.page_count == 2
        assert "Page 1" in doc[0].get_text()
        assert "Page 3" in doc[1].get_text()


def test_images_become_one_page_each_inside_the_paper(phone, samples, tmp_path):
    import pymupdf

    out = _use(phone, "images-to-pdf", [samples / "red.jpg", samples / "blue.png"],
               tmp_path=tmp_path)
    with contextlib.closing(pymupdf.open(out)) as doc:
        assert doc.page_count == 2
        assert abs(doc[1].rect.height - 841.89) < 1     # the tall one gets A4 portrait
        assert len(doc[0].get_images()) == 1            # really embedded, not drawn


def test_every_page_comes_out_as_a_picture(phone, samples, tmp_path):
    from PIL import Image

    out = _use(phone, "pdf-to-image", [samples / "four.pdf"], tmp_path=tmp_path)
    with zipfile.ZipFile(out) as bundle:
        names = bundle.namelist()
        assert len(names) == 4
        assert all(name.endswith(".jpg") for name in names)
        data = bundle.read(names[0])
    picture = Image.open(io.BytesIO(data))
    assert picture.format == "JPEG"
    assert abs(picture.width - 1240) < 30               # A4 at the default 150 dpi


def test_pages_can_be_reordered_by_dragging_the_grip(phone, samples, tmp_path):
    """Dragging is what people expect; the arrows are the fallback, not the tool."""
    import pymupdf

    page = phone
    page.goto(f"{page.site}/tools/organize-pdf/", wait_until="networkidle")
    page.set_input_files("#file", [str(samples / "four.pdf")])
    page.wait_for_selector("#go:not([disabled])")
    page.wait_for_timeout(600)

    grip = page.locator(".card").nth(0).locator(".grip").bounding_box()
    third = page.locator(".card").nth(2).bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(third["x"] + third["width"] / 2, third["y"] + third["height"] / 2,
                    steps=12)
    page.mouse.up()
    page.wait_for_timeout(200)

    page.click("#go")
    page.wait_for_selector("#done:not([hidden]) a.dl", timeout=90000)
    with page.expect_download() as caught:
        page.locator("#done a.dl").first.click()
    out = pathlib.Path(tmp_path) / caught.value.suggested_filename
    caught.value.save_as(out)
    with contextlib.closing(pymupdf.open(out)) as doc:
        order = [doc[i].get_text().strip() for i in range(doc.page_count)]
    assert order[:3] == ["Page 2", "Page 3", "Page 1"], order


def test_finishing_clears_the_form_and_offers_what_is_next(phone, samples):
    """A .drop of its own sets display, and a class beats a bare [hidden], so
    the form used to stay on screen behind the result."""
    page = phone
    page.goto(f"{page.site}/tools/merge-pdf/", wait_until="networkidle")
    page.set_input_files("#file", [str(samples / "a.pdf"), str(samples / "b.pdf")])
    page.wait_for_selector("#go:not([disabled])")
    page.click("#go")
    page.wait_for_selector("#done:not([hidden]) a.dl", timeout=90000)

    assert page.locator("#drop").is_hidden(), "the drop zone is still on screen"
    assert page.locator(".actbar").is_hidden()
    assert page.locator("#files").is_hidden()
    assert page.locator(".again").count() == 1          # start over
    assert page.locator(".next a").count() == 5         # the other five tools


def test_the_spanish_pages_speak_spanish(phone):
    phone.goto(f"{phone.site}/es/tools/merge-pdf/", wait_until="networkidle")
    assert phone.locator("h1").inner_text() == "Unir PDF"
    assert "Unir" in phone.locator("#go").inner_text()


def test_the_hub_lists_every_tool(phone):
    phone.goto(f"{phone.site}/tools/", wait_until="networkidle")
    assert phone.locator(".tools li").count() == 6


def test_it_installs_and_keeps_working_with_no_connection(phone, samples):
    """The point of the worker: on a phone with no signal it still works."""
    page = phone
    page.goto(f"{page.site}/tools/merge-pdf/", wait_until="networkidle")
    state = page.evaluate(
        "async () => (await navigator.serviceWorker.ready).active.state"
    )
    assert state == "activated"

    page.set_input_files("#file", [str(samples / "a.pdf"), str(samples / "b.pdf")])
    page.wait_for_selector("#go:not([disabled])")
    page.click("#go")
    page.wait_for_selector("#done:not([hidden]) a.dl", timeout=90000)

    # The worker fills its cache in the background, so give it a moment rather
    # than racing it.
    cached = []
    for _ in range(40):
        cached = page.evaluate("""async () => {
            const c = await caches.open('easypdf-v1');
            return (await c.keys()).map(r => new URL(r.url).pathname);
        }""")
        if "/tools/app.js" in cached and "/tools/vendor/pdf-lib.min.js" in cached:
            break
        page.wait_for_timeout(250)
    assert "/tools/app.js" in cached, cached
    assert "/tools/vendor/pdf-lib.min.js" in cached, cached   # kept when first used

    page.context_ref.set_offline(True)
    try:
        page.goto(f"{page.site}/tools/merge-pdf/", wait_until="domcontentloaded")
        assert page.locator("h1").inner_text() == "Merge PDF"
        page.set_input_files("#file", [str(samples / "a.pdf"), str(samples / "b.pdf")])
        page.wait_for_selector("#go:not([disabled])")
        page.click("#go")
        page.wait_for_selector("#done:not([hidden]) a.dl", timeout=60000)
    finally:
        page.context_ref.set_offline(False)


def test_the_two_languages_do_not_wipe_each_other(phone, samples):
    """There is now one worker for the whole site. When there were two, each
    cleaned up "every cache that is not mine" and threw away the other's, so a
    visitor who used both lost offline support over and over."""
    page = phone

    def english_cache():
        return page.evaluate("""async () => {
            const c = await caches.open('easypdf-v1');
            return (await c.keys()).map(r => new URL(r.url).pathname);
        }""")

    # Use the English tool for real, so its cache holds the heavy library.
    page.goto(f"{page.site}/tools/merge-pdf/", wait_until="networkidle")
    page.set_input_files("#file", [str(samples / "a.pdf"), str(samples / "b.pdf")])
    page.wait_for_selector("#go:not([disabled])")
    page.click("#go")
    page.wait_for_selector("#done:not([hidden]) a.dl", timeout=90000)
    for _ in range(40):
        if "/tools/vendor/pdf-lib.min.js" in english_cache():
            break
        page.wait_for_timeout(250)
    assert "/tools/vendor/pdf-lib.min.js" in english_cache()

    # Now go to the Spanish side, which the same worker serves.
    page.goto(f"{page.site}/es/tools/merge-pdf/", wait_until="networkidle")
    page.evaluate("async () => await navigator.serviceWorker.ready")
    page.wait_for_timeout(1200)

    # What English had kept has to still be there.
    kept = english_cache()
    assert "/tools/vendor/pdf-lib.min.js" in kept, kept
    assert "/tools/app.js" in kept, kept


def test_nothing_went_wrong_in_the_console(phone):
    """Runs last: anything the pages complained about along the way."""
    assert not phone.problems, "; ".join(phone.problems[:5])


def test_no_tool_talks_to_the_network(phone, samples):
    """The whole promise: the file never leaves the device."""
    page = phone
    page.goto(f"{page.site}/tools/merge-pdf/", wait_until="networkidle")
    reached = []
    page.on("request", lambda r: reached.append(r.url))
    page.set_input_files("#file", [str(samples / "a.pdf"), str(samples / "b.pdf")])
    page.wait_for_selector("#go:not([disabled])")
    page.click("#go")
    page.wait_for_selector("#done:not([hidden]) a.dl", timeout=90000)

    # Only this site's own files may be fetched, and never with a body.
    outside = [url for url in reached if not url.startswith(page.site)]
    assert not outside, f"went out to {outside}"
    assert not any(r for r in reached if "upload" in r.lower())


if os.environ.get("EASYPDF_TOOLS_SLOW"):            # pragma: no cover - opt in
    def test_a_long_document_still_finishes(phone, tmp_path):
        import pymupdf

        big = tmp_path / "big.pdf"
        doc = pymupdf.open()
        for i in range(120):
            doc.new_page().insert_text((72, 120), f"Page {i + 1}", fontsize=24)
        doc.save(big)
        doc.close()
        out = _use(phone, "delete-pages", [big], tmp_path=tmp_path)
        with contextlib.closing(pymupdf.open(out)) as result:
            assert result.page_count == 120
