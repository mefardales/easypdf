"""New version notice.

None of this touches the internet: a local server is started so the tests do
not depend on the site being up.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from easypdf.updates import check, fetch_latest, is_newer, parse_version


@pytest.fixture()
def server():
    """Local server that serves whatever latest.json the test decides."""
    state = {"body": json.dumps({"version": "9.9.9"}), "code": 200}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = state["body"].encode("utf-8")
            self.send_response(state["code"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_address[1]}/latest.json"
    yield state
    httpd.shutdown()


# -- comparing versions --------------------------------------------------
def test_parse_version_turns_it_into_numbers():
    assert parse_version("1.2.0") == (1, 2, 0)
    assert parse_version("v1.3") == (1, 3)
    assert parse_version("1.2.0-beta") == (1, 2, 0)


def test_a_version_with_no_digits_loses_to_anything():
    assert parse_version("nothing") == (0,)
    assert parse_version("") == (0,)
    assert is_newer("0.0.1", "nothing")


def test_it_compares_numbers_not_text():
    """'1.10.0' comes after '1.9.0', even though as text it is smaller."""
    assert is_newer("1.10.0", "1.9.0")
    assert is_newer("2.0.0", "1.99.99")
    assert not is_newer("1.9.0", "1.10.0")


def test_the_same_version_is_not_newer():
    assert not is_newer("1.2.0", "1.2.0")


# -- the query -----------------------------------------------------------
def test_it_reads_the_file_from_the_site(server):
    assert fetch_latest(server["url"]) == {"version": "9.9.9"}


def test_it_only_reports_something_newer(server):
    assert check("1.0.0", server["url"]) == {"version": "9.9.9"}
    assert check("9.9.9", server["url"]) is None
    assert check("10.0.0", server["url"]) is None


def test_no_internet_does_not_break_it():
    # port 1: nobody is listening there
    assert fetch_latest("http://127.0.0.1:1/latest.json", timeout=1) is None
    assert check("1.0.0", "http://127.0.0.1:1/latest.json", timeout=1) is None


def test_a_response_that_is_not_json_does_not_break_it(server):
    server["body"] = "<html>error page</html>"
    assert fetch_latest(server["url"]) is None
    assert check("1.0.0", server["url"]) is None


def test_json_without_a_version_says_nothing(server):
    server["body"] = json.dumps({"url": "https://easypdf.surf"})
    assert check("1.0.0", server["url"]) is None


def test_json_that_is_not_an_object_does_not_break_it(server):
    server["body"] = json.dumps(["1.2.3"])
    assert fetch_latest(server["url"]) is None


def test_closing_the_window_mid_check_does_not_break(qapp, server):
    """The thread cannot report back to a window that is gone."""
    import time

    from easypdf.ui.update_check import UpdateChecker

    checker = UpdateChecker()
    received = []
    checker.finished.connect(received.append)
    checker.cancel()                      # as when closing the window
    checker.start(server["url"], current="1.0.0")

    deadline = time.monotonic() + 5
    while checker.running and time.monotonic() < deadline:
        qapp.processEvents()
    qapp.processEvents()
    assert received == []                 # says nothing, and raises nothing


def test_the_check_reports_its_result(qapp, server):
    import time

    from easypdf.ui.update_check import UpdateChecker

    checker = UpdateChecker()
    received = []
    checker.finished.connect(received.append)
    checker.start(server["url"], current="1.0.0")

    deadline = time.monotonic() + 5
    while not received and time.monotonic() < deadline:
        qapp.processEvents()
    assert received and received[0]["version"] == "9.9.9"


# -- the download --------------------------------------------------------
@pytest.fixture()
def file_server(tmp_path):
    """Local server that serves real files, with their .sha256 next to them."""
    import hashlib
    from http.server import SimpleHTTPRequestHandler

    content = b"this stands in for an installer" * 5000
    (tmp_path / "EasyPDF-9.9.9-Setup.exe").write_bytes(content)
    (tmp_path / "EasyPDF-9.9.9-Setup.exe.sha256").write_text(
        hashlib.sha256(content).hexdigest() + "  EasyPDF-9.9.9-Setup.exe\n"
    )

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(tmp_path), **kwargs)

        def log_message(self, *args):
            pass

    class Server(HTTPServer):
        def handle_error(self, request, client_address):
            pass          # dropping the connection on cancel is not a failure

    httpd = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield {
        "base": base,
        "url": f"{base}/EasyPDF-9.9.9-Setup.exe",
        "content": content,
        "dir": tmp_path,
    }
    httpd.shutdown()


def test_it_picks_the_right_package_for_each_system(monkeypatch):
    import sys as _sys

    from easypdf.updates import asset_for_platform

    data = {
        "setup": "https://easypdf.surf/EasyPDF-2.0.0-Setup.exe",
        "linux": "https://easypdf.surf/EasyPDF-2.0.0-linux-x64.tar.xz",
    }
    monkeypatch.setattr(_sys, "platform", "win32")
    assert asset_for_platform(data) == (data["setup"], "EasyPDF-2.0.0-Setup.exe")
    monkeypatch.setattr(_sys, "platform", "linux")
    assert asset_for_platform(data) == (data["linux"], "EasyPDF-2.0.0-linux-x64.tar.xz")
    monkeypatch.setattr(_sys, "platform", "darwin")
    assert asset_for_platform(data) is None      # there is no Mac package yet


def test_no_link_for_this_system_means_no_download(monkeypatch):
    import sys as _sys

    from easypdf.updates import asset_for_platform

    monkeypatch.setattr(_sys, "platform", "win32")
    assert asset_for_platform({"linux": "https://x/a.tar.xz"}) is None
    assert asset_for_platform({}) is None


def test_it_downloads_the_file_and_reports_progress(file_server, tmp_path):
    from easypdf.updates import download

    steps = []
    target = str(tmp_path / "downloaded.exe")
    download(file_server["url"], target, on_progress=lambda a, b: steps.append((a, b)))

    assert open(target, "rb").read() == file_server["content"]
    assert steps, "it never reported progress once"
    assert steps[-1][0] == len(file_server["content"])
    assert steps[-1][1] == len(file_server["content"])   # the server's total


def test_the_download_checks_the_sha256(file_server, tmp_path):
    from easypdf.updates import download_verified, sha256_of

    target = str(tmp_path / "downloaded.exe")
    download_verified(file_server["url"], target)
    assert sha256_of(target) == sha256_of(
        str(file_server["dir"] / "EasyPDF-9.9.9-Setup.exe")
    )


def test_a_mismatched_sha256_throws_the_file_away(file_server, tmp_path):
    """What is downloaded gets run: if it is not what was published, it is no good."""
    from easypdf.updates import DownloadError, download_verified

    (file_server["dir"] / "EasyPDF-9.9.9-Setup.exe.sha256").write_text(
        "0" * 64 + "  EasyPDF-9.9.9-Setup.exe\n"
    )
    target = str(tmp_path / "downloaded.exe")
    with pytest.raises(DownloadError):
        download_verified(file_server["url"], target)
    assert not os.path.exists(target)


def test_a_download_without_a_published_sha256_is_still_valid(file_server, tmp_path):
    """Older packages may not carry one; that is no reason not to fetch them."""
    from easypdf.updates import download_verified

    (file_server["dir"] / "EasyPDF-9.9.9-Setup.exe.sha256").unlink()
    target = str(tmp_path / "downloaded.exe")
    download_verified(file_server["url"], target)
    assert open(target, "rb").read() == file_server["content"]


def test_cancelling_leaves_no_leftovers(file_server, tmp_path):
    from easypdf.updates import DownloadError, download

    target = str(tmp_path / "downloaded.exe")
    with pytest.raises(DownloadError):
        download(file_server["url"], target, cancelled=lambda: True)
    assert not os.path.exists(target)
    assert not os.path.exists(target + ".part")


def test_a_url_that_does_not_exist_gives_a_clear_error(file_server, tmp_path):
    from easypdf.updates import DownloadError, download

    target = str(tmp_path / "downloaded.exe")
    with pytest.raises(DownloadError):
        download(file_server["base"] + "/missing.exe", target)
    assert not os.path.exists(target)


def test_only_the_windows_exe_is_installed(monkeypatch):
    from easypdf.updates import is_installer

    monkeypatch.setattr(os, "name", "nt")
    assert is_installer("C:/Users/x/EasyPDF-2.0.0-Setup.exe")
    assert not is_installer("C:/Users/x/EasyPDF-2.0.0-linux-x64.tar.xz")
    monkeypatch.setattr(os, "name", "posix")
    assert not is_installer("/home/x/EasyPDF-2.0.0-Setup.exe")


def test_a_package_that_is_not_an_installer_is_never_run():
    from easypdf.updates import DownloadError, launch_installer

    with pytest.raises(DownloadError):
        launch_installer("/home/x/EasyPDF-2.0.0-linux-x64.tar.xz")


# -- the download window -------------------------------------------------
def _button(dialog, text):
    """Find a button by its text inside the dialog's button row."""
    from PySide6.QtWidgets import QPushButton

    for button in dialog.findChildren(QPushButton):
        if button.text() == text:
            return button
    return None


def _wait(qapp, condition, seconds=10):
    import time

    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        qapp.processEvents()
    qapp.processEvents()
    return condition()


@pytest.fixture()
def update_dialog(qapp, file_server, tmp_path, monkeypatch):
    """Build the notice window pointing at the local server."""
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "download_dir", lambda: str(tmp_path / "downloads"))
    (tmp_path / "downloads").mkdir()
    monkeypatch.setattr(
        update_download,
        "asset_for_platform",
        lambda data: (file_server["url"], "EasyPDF-9.9.9-Setup.exe"),
    )

    made = []

    def build(install_cb=None, installable=False):
        monkeypatch.setattr(update_download, "is_installer", lambda path: installable)
        dialog = update_download.UpdateDialog(
            None, "9.9.9", {"version": "9.9.9"}, install_cb=install_cb
        )
        made.append(dialog)
        return dialog

    yield build, tr
    for dialog in made:
        dialog.close()
        dialog.deleteLater()


def test_the_notice_offers_to_download(update_dialog):
    build, tr = update_dialog
    dialog = build()
    assert _button(dialog, tr("update_download")) is not None
    assert _button(dialog, tr("update_go")) is not None
    assert _button(dialog, tr("update_skip")) is not None


def test_skipping_the_version_is_remembered(update_dialog):
    build, tr = update_dialog
    dialog = build()
    assert not dialog.skipped
    _button(dialog, tr("update_skip")).click()
    assert dialog.skipped


def test_no_package_for_this_system_means_no_download_button(qapp, monkeypatch):
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "asset_for_platform", lambda data: None)
    dialog = update_download.UpdateDialog(None, "9.9.9", {"version": "9.9.9"})
    try:
        assert _button(dialog, tr("update_download")) is None
        assert _button(dialog, tr("update_go")) is not None
        assert dialog.note.isVisible() or dialog.note.text() == tr("update_no_asset")
    finally:
        dialog.close()
        dialog.deleteLater()


def test_downloading_from_the_window_reports_when_it_is_ready(
    qapp, update_dialog, file_server
):
    """The whole case: download is pressed and it ends with the file verified."""
    build, tr = update_dialog
    dialog = build(installable=False)
    _button(dialog, tr("update_download")).click()

    assert _wait(qapp, lambda: bool(dialog._file)), "the download never finished"
    assert open(dialog._file, "rb").read() == file_server["content"]
    # On a system with no installer it offers to open the folder, not to run anything.
    assert _button(dialog, tr("update_open_folder")) is not None
    assert _button(dialog, tr("update_install_now")) is None
    # And the first moment's buttons must not stay painted behind.
    assert _button(dialog, tr("update_download")) is None
    assert _button(dialog, tr("update_skip")) is None


def test_when_done_on_windows_it_offers_to_install(qapp, update_dialog):
    build, tr = update_dialog
    installed = []
    dialog = build(install_cb=lambda path: installed.append(path) or True, installable=True)
    _button(dialog, tr("update_download")).click()

    assert _wait(qapp, lambda: bool(dialog._file)), "the download never finished"
    button = _button(dialog, tr("update_install_now"))
    assert button is not None
    button.click()
    assert installed == [dialog._file]


def test_backing_out_of_the_close_cancels_the_install(qapp, update_dialog):
    """install_cb returns False when there are unsaved changes and it is cancelled."""
    build, tr = update_dialog
    dialog = build(install_cb=lambda path: False, installable=True)
    _button(dialog, tr("update_download")).click()
    assert _wait(qapp, lambda: bool(dialog._file))

    _button(dialog, tr("update_install_now")).click()
    assert dialog.isVisible() or not dialog.result()   # the window is still there


def test_a_failed_download_is_reported_and_offers_the_site(
    qapp, file_server, tmp_path, monkeypatch
):
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "download_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        update_download,
        "asset_for_platform",
        lambda data: (file_server["base"] + "/missing.exe", "missing.exe"),
    )
    dialog = update_download.UpdateDialog(None, "9.9.9", {"version": "9.9.9"})
    try:
        _button(dialog, tr("update_download")).click()
        assert _wait(qapp, lambda: _button(dialog, tr("update_close")) is not None)
        notice = tr("update_download_failed", error="")
        assert dialog.text.text().startswith(notice)
        assert _button(dialog, tr("update_go")) is not None
    finally:
        dialog.close()
        dialog.deleteLater()


def test_while_downloading_it_reports_how_far_it_got(update_dialog):
    """Progress reads below the bar, not on top of the painted part."""
    from easypdf.ui.update_download import MEGA

    build, tr = update_dialog
    dialog = build()
    dialog._progress(5 * MEGA, 20 * MEGA)
    assert dialog.note.text() == tr("update_progress", done="5.0", total="20.0")
    assert dialog.bar.maximum() == 20 * MEGA
    assert dialog.bar.value() == 5 * MEGA

    # Once downloaded the sha256 still has to be checked, and that is said too.
    dialog._progress(20 * MEGA, 20 * MEGA)
    assert dialog.note.text() == tr("update_verifying")


def test_it_keeps_counting_when_the_server_omits_the_size(update_dialog):
    from easypdf.ui.update_download import MEGA

    build, tr = update_dialog
    dialog = build()
    dialog._progress(3 * MEGA, 0)
    assert dialog.note.text() == tr("update_progress_unknown", done="3.0")


# -- the notice on start-up ----------------------------------------------
def test_on_start_up_it_checks_by_itself_and_shows_the_notice(qapp, server, monkeypatch, tmp_path):
    """Without touching anything: open the program and the notice appears."""
    import time

    from PySide6.QtWidgets import QPushButton

    from easypdf.i18n import tr
    from easypdf.ui import update_check, update_download
    from easypdf.ui.main_window import MainWindow

    server["body"] = json.dumps({
        "version": "9.9.9",
        "url": "https://easypdf.surf",
        "setup": "https://easypdf.surf/EasyPDF-9.9.9-Setup.exe",
        "linux": "https://easypdf.surf/EasyPDF-9.9.9-linux-x64.tar.xz",
    })
    monkeypatch.setattr(update_check, "LATEST_URL", server["url"])

    seen = {}

    def fake_exec(self):
        seen["text"] = self.text.text()
        seen["buttons"] = [b.text() for b in self.findChildren(QPushButton)]
        return 0

    monkeypatch.setattr(update_download.UpdateDialog, "exec", fake_exec)

    window = MainWindow()
    try:
        window.settings.set_value("updates/skip", "")
        assert window.act_update_auto.isChecked()   # on by default
        window.show()
        deadline = time.monotonic() + 15
        while "text" not in seen and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert "text" in seen, "the notice did not appear on its own at start-up"
        assert "9.9.9" in seen["text"]
        # and it carries the download button, not just the link to the site
        assert tr("update_download") in seen["buttons"]
    finally:
        window.updater.cancel()
        window._modified = False
        window.view.undo_stack.setClean()
        window.close()


def test_with_the_check_off_it_does_not_bother_you_on_start_up(qapp, server, monkeypatch):
    from easypdf.ui import update_check, update_download
    from easypdf.ui.main_window import MainWindow

    monkeypatch.setattr(update_check, "LATEST_URL", server["url"])
    calls = []
    monkeypatch.setattr(update_download.UpdateDialog, "exec",
                        lambda self: calls.append(1) or 0)

    # The preference is stored before opening the window: it is while building
    # it that it decides whether to schedule the query.
    from easypdf.config import Settings

    Settings().set_value("updates/auto", False)
    window = MainWindow()
    try:
        assert not window.act_update_auto.isChecked()
        import time

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert calls == []
    finally:
        Settings().set_value("updates/auto", True)
        window.updater.cancel()
        window._modified = False
        window.view.undo_stack.setClean()
        window.close()


def test_the_notice_has_no_antivirus_note(update_dialog):
    """It was asked to be removed: the notice only says there is a new version."""
    build, tr = update_dialog
    dialog = build()
    assert "antivirus" not in dialog.note.text().lower()
    assert not dialog.note.isVisible() or dialog.note.text() == ""
