"""Descarga de la version nueva desde dentro del programa.

Cuando el aviso encuentra una version mas reciente, aqui esta el boton que la
baja y la instala sin tener que pasar por la pagina web. La descarga va en un
hilo aparte y se comprueba con el sha256 publicado antes de ejecutar nada.
"""

from __future__ import annotations

import os
import tempfile
import threading

from PySide6.QtCore import QObject, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .. import __url__, __version__
from ..i18n import tr
from ..updates import (
    DownloadError,
    asset_for_platform,
    download_verified,
    is_installer,
    launch_installer,
)

#: Un mega, para ensenar el avance en unidades que se entienden.
MEGA = 1024 * 1024


def download_dir() -> str:
    """Donde dejar el archivo: la carpeta de descargas del usuario.

    Asi queda a mano si luego quiere volver a instalarlo o guardarlo. Si el
    sistema no dice cual es, se usa la carpeta temporal.
    """
    ruta = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    if ruta and os.path.isdir(ruta) and os.access(ruta, os.W_OK):
        return ruta
    return tempfile.gettempdir()


class Downloader(QObject):
    """Baja un archivo en segundo plano y va contando por donde va."""

    #: (bytes bajados, bytes totales). El total es 0 si el servidor no lo dice.
    progress = Signal(int, int)
    #: Ruta del archivo ya comprobado.
    finished = Signal(str)
    #: Motivo del fallo, ya traducido a algo legible.
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancelled = False
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def cancel(self) -> None:
        self._cancelled = True

    def start(self, url: str, destino: str) -> None:
        if self._running:
            return
        self._running = True
        self._cancelled = False

        def trabajo() -> None:
            try:
                ruta = download_verified(
                    url,
                    destino,
                    on_progress=self._avanzar,
                    cancelled=lambda: self._cancelled,
                )
            except DownloadError as exc:
                self._running = False
                self._avisar(self.failed, str(exc))
            except Exception as exc:                # pragma: no cover - defensivo
                self._running = False
                self._avisar(self.failed, str(exc))
            else:
                self._running = False
                self._avisar(self.finished, ruta)

        threading.Thread(target=trabajo, daemon=True, name="easypdf-download").start()

    def _avanzar(self, bajado: int, total: int) -> None:
        self._avisar(self.progress, bajado, total)

    def _avisar(self, senal, *args) -> None:
        if self._cancelled:
            return
        try:
            senal.emit(*args)
        except RuntimeError:
            # La ventana se cerro mientras se descargaba: no hay a quien avisar.
            pass


class UpdateDialog(QDialog):
    """Aviso de version nueva con descarga e instalacion.

    Tres momentos en la misma ventana: se ofrece, se descarga, y cuando esta
    lista se instala. No se cambia de ventana para que quede claro que todo
    forma parte de lo mismo.
    """

    def __init__(self, parent, nueva: str, datos: dict, install_cb=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("update_title"))
        self.setMinimumWidth(440)
        self._nueva = nueva
        self._datos = datos or {}
        self._install_cb = install_cb
        self._web = str(self._datos.get("url") or __url__)
        self._descarga: Downloader | None = None
        self._archivo = ""
        #: Lo lee la ventana principal para no volver a avisar de esta version.
        self.skipped = False

        layout = QVBoxLayout(self)
        self.texto = QLabel(tr("update_body", new=nueva, old=__version__))
        self.texto.setTextFormat(Qt.TextFormat.RichText)
        self.texto.setWordWrap(True)
        layout.addWidget(self.texto)

        self.nota = QLabel()
        self.nota.setWordWrap(True)
        self.nota.setStyleSheet("color:#666")
        self.nota.hide()
        layout.addWidget(self.nota)

        self.barra = QProgressBar()
        self.barra.hide()
        layout.addWidget(self.barra)

        self.botonera = QHBoxLayout()
        self.botonera.addStretch(1)
        layout.addLayout(self.botonera)

        self._ofrecer()

    # -------------------------------------------------------------- botones
    def _limpiar_botones(self) -> None:
        while self.botonera.count() > 1:            # el stretch se queda
            elemento = self.botonera.takeAt(1)
            widget = elemento.widget()
            if widget is not None:
                # Sacarlo del layout no basta: sigue siendo hijo del dialogo y
                # se sigue viendo donde estaba. Y deleteLater() no lo quita
                # hasta que vuelve el bucle de eventos, asi que ademas se le
                # quita el padre para que desaparezca ya.
                widget.setParent(None)
                widget.deleteLater()

    def _boton(self, texto: str, slot, principal: bool = False) -> QPushButton:
        boton = QPushButton(texto, self)
        boton.clicked.connect(slot)
        boton.setDefault(principal)
        boton.setAutoDefault(principal)
        self.botonera.addWidget(boton)
        return boton

    # --------------------------------------------------------------- estados
    def _ofrecer(self) -> None:
        """Primer momento: se cuenta que hay version nueva y se ofrece bajarla."""
        self._limpiar_botones()
        paquete = asset_for_platform(self._datos)
        if paquete is not None:
            self.boton_descargar = self._boton(
                tr("update_download"), self._descargar, principal=True
            )
        else:
            self.nota.setText(tr("update_no_asset"))
            self.nota.show()
        self._boton(tr("update_go"), self._abrir_web)
        self._boton(tr("update_later"), self.reject)
        self._boton(tr("update_skip"), self._saltar)
        self._ajustar()

    def _descargar(self) -> None:
        """Segundo momento: baja el paquete que le toca a este sistema."""
        paquete = asset_for_platform(self._datos)
        if paquete is None:                          # pragma: no cover - sin boton
            return
        url, nombre = paquete
        destino = os.path.join(download_dir(), nombre)

        self._limpiar_botones()
        self.texto.setText(tr("update_downloading", name=nombre))
        self.nota.hide()
        self.barra.setRange(0, 0)                    # indeterminada hasta saber el total
        # El texto va debajo, no dentro: encima de la barra medio pintada se
        # lee mal justo donde cambia el color.
        self.barra.setTextVisible(False)
        self.barra.show()
        self.nota.setText("")
        self.nota.show()
        self._boton(tr("update_cancel"), self._cancelar)

        self._descarga = Downloader(self)
        self._descarga.progress.connect(self._progreso)
        self._descarga.finished.connect(self._listo)
        self._descarga.failed.connect(self._fallo)
        self._descarga.start(url, destino)
        self._ajustar()

    def _progreso(self, bajado: int, total: int) -> None:
        hechos = bajado / MEGA
        if total > 0:
            self.barra.setRange(0, total)
            self.barra.setValue(bajado)
            self.nota.setText(
                tr("update_progress", done=f"{hechos:.1f}", total=f"{total / MEGA:.1f}")
            )
        else:
            self.nota.setText(tr("update_progress_unknown", done=f"{hechos:.1f}"))
        if total > 0 and bajado >= total:
            # Queda comprobar el sha256, que con un archivo de 40 MB se nota.
            self.nota.setText(tr("update_verifying"))

    def _listo(self, ruta: str) -> None:
        """Tercer momento: el archivo esta bajado y comprobado."""
        self._archivo = ruta
        self.barra.setRange(0, 1)
        self.barra.setValue(1)
        self.barra.hide()
        self._limpiar_botones()
        if is_installer(ruta):
            self.texto.setText(tr("update_ready_install"))
            self.nota.hide()
            self._boton(tr("update_install_now"), self._instalar, principal=True)
        else:
            # En Linux se publica un paquete portable: no hay nada que
            # ejecutar, se descomprime encima de la copia que ya se tenga.
            self.texto.setText(tr("update_ready_file", path=ruta))
            self.nota.hide()
            self._boton(tr("update_open_folder"), self._abrir_carpeta, principal=True)
        self._boton(tr("update_close"), self.accept)
        self._ajustar()

    def _fallo(self, motivo: str) -> None:
        self.barra.hide()
        self.texto.setText(tr("update_download_failed", error=motivo))
        self.nota.hide()
        self._limpiar_botones()
        self._boton(tr("update_go"), self._abrir_web)
        self._boton(tr("update_close"), self.reject, principal=True)
        self._ajustar()

    def _ajustar(self) -> None:
        """Cada momento ocupa lo suyo; que la ventana se acomode."""
        self.layout().activate()
        self.adjustSize()

    # --------------------------------------------------------------- acciones
    def _instalar(self) -> None:
        if self._install_cb is not None and not self._install_cb(self._archivo):
            return                                   # el usuario se ha echado atras
        if self._install_cb is None:                 # pragma: no cover - sin ventana
            launch_installer(self._archivo)
        self.accept()

    def _abrir_carpeta(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self._archivo)))

    def _abrir_web(self) -> None:
        QDesktopServices.openUrl(QUrl(self._web))
        self.accept()

    def _saltar(self) -> None:
        self.skipped = True
        self.reject()

    def _cancelar(self) -> None:
        if self._descarga is not None:
            self._descarga.cancel()
        self.reject()

    def closeEvent(self, event) -> None:
        if self._descarga is not None:
            self._descarga.cancel()
        super().closeEvent(event)


__all__ = ["Downloader", "UpdateDialog", "download_dir", "MEGA"]
