"""Consulta en segundo plano si hay una version nueva."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from .. import __version__
from ..updates import LATEST_URL, check


class UpdateChecker(QObject):
    """Pregunta a la web oficial sin entretener a la interfaz.

    La consulta va en un hilo aparte: si la web tarda o no hay internet, el
    programa sigue funcionando como si nada.
    """

    #: Se emite con los datos de la version nueva, o con None si no hay.
    finished = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._cancelled = False

    @property
    def running(self) -> bool:
        return self._running

    def cancel(self) -> None:
        """Deja de avisar del resultado. Se llama al cerrar la ventana."""
        self._cancelled = True

    def start(self, url: str = LATEST_URL, current: str | None = None) -> None:
        if self._running:
            return
        self._running = True
        version = current or __version__

        def trabajo() -> None:
            try:
                datos = check(version, url)
            except Exception:  # pragma: no cover - defensivo
                datos = None
            self._running = False
            if self._cancelled:
                return
            try:
                self.finished.emit(datos)
            except RuntimeError:
                # La ventana se cerro mientras se consultaba: ya no hay a
                # quien avisar, y no es motivo para soltar un error.
                pass

        hilo = threading.Thread(target=trabajo, daemon=True, name="easypdf-updates")
        hilo.start()


__all__ = ["UpdateChecker"]
