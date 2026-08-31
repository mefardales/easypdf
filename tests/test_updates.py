"""Aviso de version nueva.

Nada de esto toca internet: se levanta un servidor local, para que las
pruebas no dependan de que la web este disponible.
"""

from __future__ import annotations

import json
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
