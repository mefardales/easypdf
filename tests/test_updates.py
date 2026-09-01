"""Aviso de version nueva.

Nada de esto toca internet: se levanta un servidor local, para que las
pruebas no dependan de que la web este disponible.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from easypdf.updates import check, fetch_latest, is_newer, parse_version


@pytest.fixture()
def servidor():
    """Servidor local que sirve un latest.json que la prueba decide."""
    state = {"cuerpo": json.dumps({"version": "9.9.9"}), "codigo": 200}

    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self):
            body = state["cuerpo"].encode("utf-8")
            self.send_response(state["codigo"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{servidor.server_address[1]}/latest.json"
    yield state
    servidor.shutdown()


# -- comparacion de versiones -------------------------------------------
def test_parse_version_turns_it_into_numbers():
    assert parse_version("1.2.0") == (1, 2, 0)
    assert parse_version("v1.3") == (1, 3)
    assert parse_version("1.2.0-beta") == (1, 2, 0)


def test_a_version_with_no_digits_loses_to_anything():
    assert parse_version("nada") == (0,)
    assert parse_version("") == (0,)
    assert is_newer("0.0.1", "nada")


def test_it_compares_numbers_not_text():
    """'1.10.0' es posterior a '1.9.0', aunque como texto sea menor."""
    assert is_newer("1.10.0", "1.9.0")
    assert is_newer("2.0.0", "1.99.99")
    assert not is_newer("1.9.0", "1.10.0")


def test_the_same_version_is_not_newer():
    assert not is_newer("1.2.0", "1.2.0")


# -- consulta ------------------------------------------------------------
def test_it_reads_the_file_from_the_site(servidor):
    assert fetch_latest(servidor["url"]) == {"version": "9.9.9"}


def test_it_only_reports_something_newer(servidor):
    assert check("1.0.0", servidor["url"]) == {"version": "9.9.9"}
    assert check("9.9.9", servidor["url"]) is None
    assert check("10.0.0", servidor["url"]) is None


def test_no_internet_does_not_break_it():
    # puerto 1: no hay nadie escuchando
    assert fetch_latest("http://127.0.0.1:1/latest.json", timeout=1) is None
    assert check("1.0.0", "http://127.0.0.1:1/latest.json", timeout=1) is None


def test_a_response_that_is_not_json_does_not_break_it(servidor):
    servidor["cuerpo"] = "<html>pagina de error</html>"
    assert fetch_latest(servidor["url"]) is None
    assert check("1.0.0", servidor["url"]) is None


def test_json_without_a_version_says_nothing(servidor):
    servidor["cuerpo"] = json.dumps({"url": "https://easypdf.surf"})
    assert check("1.0.0", servidor["url"]) is None


def test_json_that_is_not_an_object_does_not_break_it(servidor):
    servidor["cuerpo"] = json.dumps(["1.2.3"])
    assert fetch_latest(servidor["url"]) is None


def test_closing_the_window_mid_check_does_not_break(qapp, servidor):
    """El hilo no puede avisar a una ventana que ya no existe."""
    import time

    from easypdf.ui.update_check import UpdateChecker

    checker = UpdateChecker()
    received = []
    checker.finished.connect(received.append)
    checker.cancel()                      # como al cerrar la ventana
    checker.start(servidor["url"], current="1.0.0")

    fin = time.monotonic() + 5
    while checker.running and time.monotonic() < fin:
        qapp.processEvents()
    qapp.processEvents()
    assert received == []                 # no avisa, y no suelta ningun error


def test_the_check_reports_its_result(qapp, servidor):
    import time

    from easypdf.ui.update_check import UpdateChecker

    checker = UpdateChecker()
    received = []
    checker.finished.connect(received.append)
    checker.start(servidor["url"], current="1.0.0")

    fin = time.monotonic() + 5
    while not received and time.monotonic() < fin:
        qapp.processEvents()
    assert received and received[0]["version"] == "9.9.9"


# -- descarga ------------------------------------------------------------
@pytest.fixture()
def servidor_archivos(tmp_path):
    """Servidor local que sirve archivos de verdad, con su .sha256 al lado."""
    import hashlib
    from http.server import SimpleHTTPRequestHandler

    content = b"esto hace de instalador" * 5000
    (tmp_path / "EasyPDF-9.9.9-Setup.exe").write_bytes(content)
    (tmp_path / "EasyPDF-9.9.9-Setup.exe.sha256").write_text(
        hashlib.sha256(content).hexdigest() + "  EasyPDF-9.9.9-Setup.exe\n"
    )

    class Manejador(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(tmp_path), **kwargs)

        def log_message(self, *args):
            pass

    class Servidor(HTTPServer):
        def handle_error(self, request, client_address):
            pass          # cortar la conexion al cancelar no es un fallo

    servidor = Servidor(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{servidor.server_address[1]}"
    yield {
        "base": base,
        "url": f"{base}/EasyPDF-9.9.9-Setup.exe",
        "contenido": content,
        "dir": tmp_path,
    }
    servidor.shutdown()


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
    assert asset_for_platform(data) is None      # todavia no hay paquete de Mac


def test_no_link_for_this_system_means_no_download(monkeypatch):
    import sys as _sys

    from easypdf.updates import asset_for_platform

    monkeypatch.setattr(_sys, "platform", "win32")
    assert asset_for_platform({"linux": "https://x/a.tar.xz"}) is None
    assert asset_for_platform({}) is None


def test_it_downloads_the_file_and_reports_progress(servidor_archivos, tmp_path):
    from easypdf.updates import download

    avance = []
    target = str(tmp_path / "bajado.exe")
    download(servidor_archivos["url"], target, on_progress=lambda a, b: avance.append((a, b)))

    assert open(target, "rb").read() == servidor_archivos["contenido"]
    assert avance, "no ha avisado del avance ni una vez"
    assert avance[-1][0] == len(servidor_archivos["contenido"])
    assert avance[-1][1] == len(servidor_archivos["contenido"])   # el total del servidor


def test_the_download_checks_the_sha256(servidor_archivos, tmp_path):
    from easypdf.updates import download_verified, sha256_of

    target = str(tmp_path / "bajado.exe")
    download_verified(servidor_archivos["url"], target)
    assert sha256_of(target) == sha256_of(
        str(servidor_archivos["dir"] / "EasyPDF-9.9.9-Setup.exe")
    )


def test_a_mismatched_sha256_throws_the_file_away(servidor_archivos, tmp_path):
    """Lo que se baja se va a ejecutar: si no es lo publicado, no vale."""
    from easypdf.updates import DownloadError, download_verified

    (servidor_archivos["dir"] / "EasyPDF-9.9.9-Setup.exe.sha256").write_text(
        "0" * 64 + "  EasyPDF-9.9.9-Setup.exe\n"
    )
    target = str(tmp_path / "bajado.exe")
    with pytest.raises(DownloadError):
        download_verified(servidor_archivos["url"], target)
    assert not os.path.exists(target)


def test_a_download_without_a_published_sha256_is_still_valid(servidor_archivos, tmp_path):
    """Los paquetes antiguos pueden no llevarlo; no es motivo para no bajarlos."""
    from easypdf.updates import download_verified

    (servidor_archivos["dir"] / "EasyPDF-9.9.9-Setup.exe.sha256").unlink()
    target = str(tmp_path / "bajado.exe")
    download_verified(servidor_archivos["url"], target)
    assert open(target, "rb").read() == servidor_archivos["contenido"]


def test_cancelling_leaves_no_leftovers(servidor_archivos, tmp_path):
    from easypdf.updates import DownloadError, download

    target = str(tmp_path / "bajado.exe")
    with pytest.raises(DownloadError):
        download(servidor_archivos["url"], target, cancelled=lambda: True)
    assert not os.path.exists(target)
    assert not os.path.exists(target + ".parte")


def test_a_url_that_does_not_exist_gives_a_clear_error(servidor_archivos, tmp_path):
    from easypdf.updates import DownloadError, download

    target = str(tmp_path / "bajado.exe")
    with pytest.raises(DownloadError):
        download(servidor_archivos["base"] + "/no-esta.exe", target)
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


# -- la ventana de descarga ----------------------------------------------
def _boton(dialogo, text):
    """Busca un boton por su texto dentro de la botonera del dialogo."""
    from PySide6.QtWidgets import QPushButton

    for button in dialogo.findChildren(QPushButton):
        if button.text() == text:
            return button
    return None


def _esperar(qapp, condition, segundos=10):
    import time

    fin = time.monotonic() + segundos
    while not condition() and time.monotonic() < fin:
        qapp.processEvents()
    qapp.processEvents()
    return condition()


@pytest.fixture()
def update_dialog(qapp, servidor_archivos, tmp_path, monkeypatch):
    """Crea la ventana de aviso apuntando al servidor local."""
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "download_dir", lambda: str(tmp_path / "bajadas"))
    (tmp_path / "bajadas").mkdir()
    monkeypatch.setattr(
        update_download,
        "asset_for_platform",
        lambda data: (servidor_archivos["url"], "EasyPDF-9.9.9-Setup.exe"),
    )

    creados = []

    def crear(install_cb=None, instalable=False):
        monkeypatch.setattr(update_download, "is_installer", lambda path: instalable)
        dialogo = update_download.UpdateDialog(
            None, "9.9.9", {"version": "9.9.9"}, install_cb=install_cb
        )
        creados.append(dialogo)
        return dialogo

    yield crear, tr
    for dialogo in creados:
        dialogo.close()
        dialogo.deleteLater()


def test_the_notice_offers_to_download(update_dialog):
    crear, tr = update_dialog
    dialogo = crear()
    assert _boton(dialogo, tr("update_download")) is not None
    assert _boton(dialogo, tr("update_go")) is not None
    assert _boton(dialogo, tr("update_skip")) is not None


def test_skipping_the_version_is_remembered(update_dialog):
    crear, tr = update_dialog
    dialogo = crear()
    assert not dialogo.skipped
    _boton(dialogo, tr("update_skip")).click()
    assert dialogo.skipped


def test_no_package_for_this_system_means_no_download_button(qapp, monkeypatch):
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "asset_for_platform", lambda data: None)
    dialogo = update_download.UpdateDialog(None, "9.9.9", {"version": "9.9.9"})
    try:
        assert _boton(dialogo, tr("update_download")) is None
        assert _boton(dialogo, tr("update_go")) is not None
        assert dialogo.note.isVisible() or dialogo.note.text() == tr("update_no_asset")
    finally:
        dialogo.close()
        dialogo.deleteLater()


def test_downloading_from_the_window_reports_when_it_is_ready(
    qapp, update_dialog, servidor_archivos
):
    """El caso completo: se pulsa descargar y acaba con el archivo comprobado."""
    crear, tr = update_dialog
    dialogo = crear(instalable=False)
    _boton(dialogo, tr("update_download")).click()

    assert _esperar(qapp, lambda: bool(dialogo._archivo)), "la descarga no termino"
    assert open(dialogo._archivo, "rb").read() == servidor_archivos["contenido"]
    # En un sistema sin instalador se ofrece abrir la carpeta, no ejecutar nada.
    assert _boton(dialogo, tr("update_open_folder")) is not None
    assert _boton(dialogo, tr("update_install_now")) is None
    # Y los botones del primer momento no pueden quedarse pintados detras.
    assert _boton(dialogo, tr("update_download")) is None
    assert _boton(dialogo, tr("update_skip")) is None


def test_when_done_on_windows_it_offers_to_install(qapp, update_dialog):
    crear, tr = update_dialog
    instalados = []
    dialogo = crear(install_cb=lambda path: instalados.append(path) or True, instalable=True)
    _boton(dialogo, tr("update_download")).click()

    assert _esperar(qapp, lambda: bool(dialogo._archivo)), "la descarga no termino"
    button = _boton(dialogo, tr("update_install_now"))
    assert button is not None
    button.click()
    assert instalados == [dialogo._archivo]


def test_backing_out_of_the_close_cancels_the_install(qapp, update_dialog):
    """install_cb devuelve False cuando hay cambios sin guardar y se cancela."""
    crear, tr = update_dialog
    dialogo = crear(install_cb=lambda path: False, instalable=True)
    _boton(dialogo, tr("update_download")).click()
    assert _esperar(qapp, lambda: bool(dialogo._archivo))

    _boton(dialogo, tr("update_install_now")).click()
    assert dialogo.isVisible() or not dialogo.result()   # la ventana sigue ahi


def test_a_failed_download_is_reported_and_offers_the_site(
    qapp, servidor_archivos, tmp_path, monkeypatch
):
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "download_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        update_download,
        "asset_for_platform",
        lambda data: (servidor_archivos["base"] + "/no-esta.exe", "no-esta.exe"),
    )
    dialogo = update_download.UpdateDialog(None, "9.9.9", {"version": "9.9.9"})
    try:
        _boton(dialogo, tr("update_download")).click()
        assert _esperar(qapp, lambda: _boton(dialogo, tr("update_close")) is not None)
        notice = tr("update_download_failed", error="")
        assert dialogo.text.text().startswith(notice)
        assert _boton(dialogo, tr("update_go")) is not None
    finally:
        dialogo.close()
        dialogo.deleteLater()


def test_while_downloading_it_reports_how_far_it_got(update_dialog):
    """El avance se lee debajo de la barra, no encima de la parte pintada."""
    from easypdf.ui.update_download import MEGA

    crear, tr = update_dialog
    dialogo = crear()
    dialogo._progreso(5 * MEGA, 20 * MEGA)
    assert dialogo.note.text() == tr("update_progress", done="5.0", total="20.0")
    assert dialogo.barra.maximum() == 20 * MEGA
    assert dialogo.barra.value() == 5 * MEGA

    # Al acabar de bajar queda comprobar el sha256, y eso tambien se cuenta.
    dialogo._progreso(20 * MEGA, 20 * MEGA)
    assert dialogo.note.text() == tr("update_verifying")


def test_it_keeps_counting_when_the_server_omits_the_size(update_dialog):
    from easypdf.ui.update_download import MEGA

    crear, tr = update_dialog
    dialogo = crear()
    dialogo._progreso(3 * MEGA, 0)
    assert dialogo.note.text() == tr("update_progress_unknown", done="3.0")


# -- el aviso al arrancar -------------------------------------------------
def test_on_start_up_it_checks_by_itself_and_shows_the_notice(qapp, servidor, monkeypatch, tmp_path):
    """Sin tocar nada: se abre el programa y sale el aviso si hay version nueva."""
    import time

    from PySide6.QtWidgets import QPushButton

    from easypdf.i18n import tr
    from easypdf.ui import update_check, update_download
    from easypdf.ui.main_window import MainWindow

    servidor["cuerpo"] = json.dumps({
        "version": "9.9.9",
        "url": "https://easypdf.surf",
        "setup": "https://easypdf.surf/EasyPDF-9.9.9-Setup.exe",
        "linux": "https://easypdf.surf/EasyPDF-9.9.9-linux-x64.tar.xz",
    })
    monkeypatch.setattr(update_check, "LATEST_URL", servidor["url"])

    visto = {}

    def falso_exec(self):
        visto["texto"] = self.text.text()
        visto["botones"] = [b.text() for b in self.findChildren(QPushButton)]
        return 0

    monkeypatch.setattr(update_download.UpdateDialog, "exec", falso_exec)

    window = MainWindow()
    try:
        window.settings.set_value("updates/skip", "")
        assert window.act_update_auto.isChecked()   # activado de serie
        window.show()
        fin = time.monotonic() + 15
        while "texto" not in visto and time.monotonic() < fin:
            qapp.processEvents()
            time.sleep(0.01)
        assert "texto" in visto, "el aviso no ha salido solo al arrancar"
        assert "9.9.9" in visto["texto"]
        # y trae el boton de descargar, no solo el enlace a la web
        assert tr("update_download") in visto["botones"]
    finally:
        window.updater.cancel()
        window._modified = False
        window.view.undo_stack.setClean()
        window.close()


def test_with_the_check_off_it_does_not_bother_you_on_start_up(qapp, servidor, monkeypatch):
    from easypdf.ui import update_check, update_download
    from easypdf.ui.main_window import MainWindow

    monkeypatch.setattr(update_check, "LATEST_URL", servidor["url"])
    calls = []
    monkeypatch.setattr(update_download.UpdateDialog, "exec",
                        lambda self: calls.append(1) or 0)

    # La preferencia se guarda antes de abrir la ventana: es al construirla
    # cuando decide si programa la consulta.
    from easypdf.config import Settings

    Settings().set_value("updates/auto", False)
    window = MainWindow()
    try:
        assert not window.act_update_auto.isChecked()
        import time

        fin = time.monotonic() + 5
        while time.monotonic() < fin:
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
    """Se pidio quitarla: el aviso solo dice que hay version nueva."""
    crear, tr = update_dialog
    dialogo = crear()
    assert "antivirus" not in dialogo.note.text().lower()
    assert not dialogo.note.isVisible() or dialogo.note.text() == ""
