"""Check for a new version in the background."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from .. import __version__
from ..updates import LATEST_URL, check


class UpdateChecker(QObject):
    """Ask the official site without holding up the interface.

    The query runs on a separate thread: if the site is slow or there is no
    internet, the program carries on as if nothing happened.
    """

    #: Emitted with the new version's data, or with None if there is none.
    finished = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._cancelled = False

    @property
    def running(self) -> bool:
        return self._running

    def cancel(self) -> None:
        """Stop reporting the result. Called when the window closes."""
        self._cancelled = True

    def start(self, url: str | None = None, current: str | None = None) -> None:
        # The address is read when called, not when the module is imported:
        # as a default argument it froze to whatever it was back then and
        # there was no way to point it elsewhere (in the tests, for example).
        if self._running:
            return
        self._running = True
        target = url or LATEST_URL
        version = current or __version__

        def work() -> None:
            try:
                data = check(version, target)
            except Exception:  # pragma: no cover - defensive
                data = None
            self._running = False
            if self._cancelled:
                return
            try:
                self.finished.emit(data)
            except RuntimeError:
                # The window closed while the query was running: there is no
                # one left to tell, and that is no reason to raise an error.
                pass

        thread = threading.Thread(target=work, daemon=True, name="easypdf-updates")
        thread.start()


__all__ = ["UpdateChecker"]
