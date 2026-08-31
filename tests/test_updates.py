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
    estado = {"cuerpo": json.dumps({"version": "9.9.9"}), "codigo": 200}

    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self):
            cuerpo = estado["cuerpo"].encode("utf-8")
            self.send_response(estado["codigo"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    estado["url"] = f"http://127.0.0.1:{servidor.server_address[1]}/latest.json"
    yield estado
    servidor.shutdown()


# -- comparacion de versiones -------------------------------------------
def test_parse_version_convierte_a_numeros():
    assert parse_version("1.2.0") == (1, 2, 0)
    assert parse_version("v1.3") == (1, 3)
    assert parse_version("1.2.0-beta") == (1, 2, 0)


def test_una_version_sin_numeros_pierde_contra_cualquiera():
    assert parse_version("nada") == (0,)
    assert parse_version("") == (0,)
    assert is_newer("0.0.1", "nada")


def test_compara_los_numeros_no_el_texto():
    """'1.10.0' es posterior a '1.9.0', aunque como texto sea menor."""
    assert is_newer("1.10.0", "1.9.0")
    assert is_newer("2.0.0", "1.99.99")
    assert not is_newer("1.9.0", "1.10.0")


def test_la_misma_version_no_es_mas_nueva():
    assert not is_newer("1.2.0", "1.2.0")


# -- consulta ------------------------------------------------------------
def test_lee_el_archivo_de_la_web(servidor):
    assert fetch_latest(servidor["url"]) == {"version": "9.9.9"}


def test_avisa_solo_si_hay_algo_mas_nuevo(servidor):
    assert check("1.0.0", servidor["url"]) == {"version": "9.9.9"}
    assert check("9.9.9", servidor["url"]) is None
    assert check("10.0.0", servidor["url"]) is None


def test_sin_internet_no_rompe():
    # puerto 1: no hay nadie escuchando
    assert fetch_latest("http://127.0.0.1:1/latest.json", timeout=1) is None
    assert check("1.0.0", "http://127.0.0.1:1/latest.json", timeout=1) is None


def test_una_respuesta_que_no_es_json_no_rompe(servidor):
    servidor["cuerpo"] = "<html>pagina de error</html>"
    assert fetch_latest(servidor["url"]) is None
    assert check("1.0.0", servidor["url"]) is None


def test_un_json_sin_version_no_avisa(servidor):
    servidor["cuerpo"] = json.dumps({"url": "https://easypdf.surf"})
    assert check("1.0.0", servidor["url"]) is None


def test_un_json_que_no_es_un_objeto_no_rompe(servidor):
    servidor["cuerpo"] = json.dumps(["1.2.3"])
    assert fetch_latest(servidor["url"]) is None


def test_cerrar_la_ventana_mientras_se_consulta_no_rompe(qapp, servidor):
    """El hilo no puede avisar a una ventana que ya no existe."""
    import time

    from easypdf.ui.update_check import UpdateChecker

    checker = UpdateChecker()
    recibido = []
    checker.finished.connect(recibido.append)
    checker.cancel()                      # como al cerrar la ventana
    checker.start(servidor["url"], current="1.0.0")

    fin = time.monotonic() + 5
    while checker.running and time.monotonic() < fin:
        qapp.processEvents()
    qapp.processEvents()
    assert recibido == []                 # no avisa, y no suelta ningun error


def test_la_consulta_avisa_del_resultado(qapp, servidor):
    import time

    from easypdf.ui.update_check import UpdateChecker

    checker = UpdateChecker()
    recibido = []
    checker.finished.connect(recibido.append)
    checker.start(servidor["url"], current="1.0.0")

    fin = time.monotonic() + 5
    while not recibido and time.monotonic() < fin:
        qapp.processEvents()
    assert recibido and recibido[0]["version"] == "9.9.9"


# -- descarga ------------------------------------------------------------
@pytest.fixture()
def servidor_archivos(tmp_path):
    """Servidor local que sirve archivos de verdad, con su .sha256 al lado."""
    import hashlib
    from http.server import SimpleHTTPRequestHandler

    contenido = b"esto hace de instalador" * 5000
    (tmp_path / "EasyPDF-9.9.9-Setup.exe").write_bytes(contenido)
    (tmp_path / "EasyPDF-9.9.9-Setup.exe.sha256").write_text(
        hashlib.sha256(contenido).hexdigest() + "  EasyPDF-9.9.9-Setup.exe\n"
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
        "contenido": contenido,
        "dir": tmp_path,
    }
    servidor.shutdown()


def test_elige_el_paquete_que_toca_en_cada_sistema(monkeypatch):
    import sys as _sys

    from easypdf.updates import asset_for_platform

    datos = {
        "setup": "https://easypdf.surf/EasyPDF-2.0.0-Setup.exe",
        "linux": "https://easypdf.surf/EasyPDF-2.0.0-linux-x64.tar.xz",
    }
    monkeypatch.setattr(_sys, "platform", "win32")
    assert asset_for_platform(datos) == (datos["setup"], "EasyPDF-2.0.0-Setup.exe")
    monkeypatch.setattr(_sys, "platform", "linux")
    assert asset_for_platform(datos) == (datos["linux"], "EasyPDF-2.0.0-linux-x64.tar.xz")
    monkeypatch.setattr(_sys, "platform", "darwin")
    assert asset_for_platform(datos) is None      # todavia no hay paquete de Mac


def test_sin_enlace_para_este_sistema_no_hay_descarga(monkeypatch):
    import sys as _sys

    from easypdf.updates import asset_for_platform

    monkeypatch.setattr(_sys, "platform", "win32")
    assert asset_for_platform({"linux": "https://x/a.tar.xz"}) is None
    assert asset_for_platform({}) is None


def test_descarga_el_archivo_y_va_contando(servidor_archivos, tmp_path):
    from easypdf.updates import download

    avance = []
    destino = str(tmp_path / "bajado.exe")
    download(servidor_archivos["url"], destino, on_progress=lambda a, b: avance.append((a, b)))

    assert open(destino, "rb").read() == servidor_archivos["contenido"]
    assert avance, "no ha avisado del avance ni una vez"
    assert avance[-1][0] == len(servidor_archivos["contenido"])
    assert avance[-1][1] == len(servidor_archivos["contenido"])   # el total del servidor


def test_la_descarga_comprueba_el_sha256(servidor_archivos, tmp_path):
    from easypdf.updates import download_verified, sha256_of

    destino = str(tmp_path / "bajado.exe")
    download_verified(servidor_archivos["url"], destino)
    assert sha256_of(destino) == sha256_of(
        str(servidor_archivos["dir"] / "EasyPDF-9.9.9-Setup.exe")
    )


def test_si_el_sha256_no_cuadra_se_tira_el_archivo(servidor_archivos, tmp_path):
    """Lo que se baja se va a ejecutar: si no es lo publicado, no vale."""
    from easypdf.updates import DownloadError, download_verified

    (servidor_archivos["dir"] / "EasyPDF-9.9.9-Setup.exe.sha256").write_text(
        "0" * 64 + "  EasyPDF-9.9.9-Setup.exe\n"
    )
    destino = str(tmp_path / "bajado.exe")
    with pytest.raises(DownloadError):
        download_verified(servidor_archivos["url"], destino)
    assert not os.path.exists(destino)


def test_sin_sha256_publicado_la_descarga_sigue_valiendo(servidor_archivos, tmp_path):
    """Los paquetes antiguos pueden no llevarlo; no es motivo para no bajarlos."""
    from easypdf.updates import download_verified

    (servidor_archivos["dir"] / "EasyPDF-9.9.9-Setup.exe.sha256").unlink()
    destino = str(tmp_path / "bajado.exe")
    download_verified(servidor_archivos["url"], destino)
    assert open(destino, "rb").read() == servidor_archivos["contenido"]


def test_al_cancelar_no_queda_ningun_resto(servidor_archivos, tmp_path):
    from easypdf.updates import DownloadError, download

    destino = str(tmp_path / "bajado.exe")
    with pytest.raises(DownloadError):
        download(servidor_archivos["url"], destino, cancelled=lambda: True)
    assert not os.path.exists(destino)
    assert not os.path.exists(destino + ".parte")


def test_una_url_que_no_existe_da_un_error_claro(servidor_archivos, tmp_path):
    from easypdf.updates import DownloadError, download

    destino = str(tmp_path / "bajado.exe")
    with pytest.raises(DownloadError):
        download(servidor_archivos["base"] + "/no-esta.exe", destino)
    assert not os.path.exists(destino)


def test_solo_se_instala_el_exe_de_windows(monkeypatch):
    from easypdf.updates import is_installer

    monkeypatch.setattr(os, "name", "nt")
    assert is_installer("C:/Users/x/EasyPDF-2.0.0-Setup.exe")
    assert not is_installer("C:/Users/x/EasyPDF-2.0.0-linux-x64.tar.xz")
    monkeypatch.setattr(os, "name", "posix")
    assert not is_installer("/home/x/EasyPDF-2.0.0-Setup.exe")


def test_no_se_intenta_ejecutar_un_paquete_que_no_es_instalador():
    from easypdf.updates import DownloadError, launch_installer

    with pytest.raises(DownloadError):
        launch_installer("/home/x/EasyPDF-2.0.0-linux-x64.tar.xz")


# -- la ventana de descarga ----------------------------------------------
def _boton(dialogo, texto):
    """Busca un boton por su texto dentro de la botonera del dialogo."""
    from PySide6.QtWidgets import QPushButton

    for boton in dialogo.findChildren(QPushButton):
        if boton.text() == texto:
            return boton
    return None


def _esperar(qapp, condicion, segundos=10):
    import time

    fin = time.monotonic() + segundos
    while not condicion() and time.monotonic() < fin:
        qapp.processEvents()
    qapp.processEvents()
    return condicion()


@pytest.fixture()
def dialogo_de_actualizacion(qapp, servidor_archivos, tmp_path, monkeypatch):
    """Crea la ventana de aviso apuntando al servidor local."""
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "download_dir", lambda: str(tmp_path / "bajadas"))
    (tmp_path / "bajadas").mkdir()
    monkeypatch.setattr(
        update_download,
        "asset_for_platform",
        lambda datos: (servidor_archivos["url"], "EasyPDF-9.9.9-Setup.exe"),
    )

    creados = []

    def crear(install_cb=None, instalable=False):
        monkeypatch.setattr(update_download, "is_installer", lambda ruta: instalable)
        dialogo = update_download.UpdateDialog(
            None, "9.9.9", {"version": "9.9.9"}, install_cb=install_cb
        )
        creados.append(dialogo)
        return dialogo

    yield crear, tr
    for dialogo in creados:
        dialogo.close()
        dialogo.deleteLater()


def test_el_aviso_ofrece_descargar(dialogo_de_actualizacion):
    crear, tr = dialogo_de_actualizacion
    dialogo = crear()
    assert _boton(dialogo, tr("update_download")) is not None
    assert _boton(dialogo, tr("update_go")) is not None
    assert _boton(dialogo, tr("update_skip")) is not None


def test_saltar_la_version_queda_apuntado(dialogo_de_actualizacion):
    crear, tr = dialogo_de_actualizacion
    dialogo = crear()
    assert not dialogo.skipped
    _boton(dialogo, tr("update_skip")).click()
    assert dialogo.skipped


def test_sin_paquete_para_este_sistema_no_hay_boton_de_descarga(qapp, monkeypatch):
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "asset_for_platform", lambda datos: None)
    dialogo = update_download.UpdateDialog(None, "9.9.9", {"version": "9.9.9"})
    try:
        assert _boton(dialogo, tr("update_download")) is None
        assert _boton(dialogo, tr("update_go")) is not None
        assert dialogo.nota.isVisible() or dialogo.nota.text() == tr("update_no_asset")
    finally:
        dialogo.close()
        dialogo.deleteLater()


def test_descarga_desde_la_ventana_y_avisa_de_que_esta_lista(
    qapp, dialogo_de_actualizacion, servidor_archivos
):
    """El caso completo: se pulsa descargar y acaba con el archivo comprobado."""
    crear, tr = dialogo_de_actualizacion
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


def test_al_terminar_en_windows_ofrece_instalar(qapp, dialogo_de_actualizacion):
    crear, tr = dialogo_de_actualizacion
    instalados = []
    dialogo = crear(install_cb=lambda ruta: instalados.append(ruta) or True, instalable=True)
    _boton(dialogo, tr("update_download")).click()

    assert _esperar(qapp, lambda: bool(dialogo._archivo)), "la descarga no termino"
    boton = _boton(dialogo, tr("update_install_now"))
    assert boton is not None
    boton.click()
    assert instalados == [dialogo._archivo]


def test_si_el_usuario_se_echa_atras_al_cerrar_no_se_instala(qapp, dialogo_de_actualizacion):
    """install_cb devuelve False cuando hay cambios sin guardar y se cancela."""
    crear, tr = dialogo_de_actualizacion
    dialogo = crear(install_cb=lambda ruta: False, instalable=True)
    _boton(dialogo, tr("update_download")).click()
    assert _esperar(qapp, lambda: bool(dialogo._archivo))

    _boton(dialogo, tr("update_install_now")).click()
    assert dialogo.isVisible() or not dialogo.result()   # la ventana sigue ahi


def test_una_descarga_fallida_se_cuenta_y_deja_ir_a_la_web(
    qapp, servidor_archivos, tmp_path, monkeypatch
):
    from easypdf.i18n import tr
    from easypdf.ui import update_download

    monkeypatch.setattr(update_download, "download_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        update_download,
        "asset_for_platform",
        lambda datos: (servidor_archivos["base"] + "/no-esta.exe", "no-esta.exe"),
    )
    dialogo = update_download.UpdateDialog(None, "9.9.9", {"version": "9.9.9"})
    try:
        _boton(dialogo, tr("update_download")).click()
        assert _esperar(qapp, lambda: _boton(dialogo, tr("update_close")) is not None)
        aviso = tr("update_download_failed", error="")
        assert dialogo.texto.text().startswith(aviso)
        assert _boton(dialogo, tr("update_go")) is not None
    finally:
        dialogo.close()
        dialogo.deleteLater()


def test_mientras_baja_dice_cuanto_lleva(dialogo_de_actualizacion):
    """El avance se lee debajo de la barra, no encima de la parte pintada."""
    from easypdf.ui.update_download import MEGA

    crear, tr = dialogo_de_actualizacion
    dialogo = crear()
    dialogo._progreso(5 * MEGA, 20 * MEGA)
    assert dialogo.nota.text() == tr("update_progress", done="5.0", total="20.0")
    assert dialogo.barra.maximum() == 20 * MEGA
    assert dialogo.barra.value() == 5 * MEGA

    # Al acabar de bajar queda comprobar el sha256, y eso tambien se cuenta.
    dialogo._progreso(20 * MEGA, 20 * MEGA)
    assert dialogo.nota.text() == tr("update_verifying")


def test_si_el_servidor_no_dice_el_tamano_sigue_contando(dialogo_de_actualizacion):
    from easypdf.ui.update_download import MEGA

    crear, tr = dialogo_de_actualizacion
    dialogo = crear()
    dialogo._progreso(3 * MEGA, 0)
    assert dialogo.nota.text() == tr("update_progress_unknown", done="3.0")
