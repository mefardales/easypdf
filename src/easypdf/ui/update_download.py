"""Downloading the new version from inside the program.

When the notice finds a newer version, this is the button that fetches and
installs it without having to go through the web page. The download runs on a
separate thread and is checked against the published sha256 before anything is
executed.
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

#: One megabyte, to show progress in units people understand.
MEGA = 1024 * 1024


def download_dir() -> str:
    """Where to leave the file: the user's downloads folder.

    That way it stays at hand if they later want to install it again or keep
    it. If the system does not say which folder that is, the temporary folder
    is used.
    """
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    if path and os.path.isdir(path) and os.access(path, os.W_OK):
        return path
    return tempfile.gettempdir()


class Downloader(QObject):
    """Fetches a file in the background and reports how far along it is."""

    #: (bytes downloaded, total bytes). The total is 0 if the server does not say.
    progress = Signal(int, int)
    #: Path of the file, already verified.
    finished = Signal(str)
    #: Why it failed, already turned into something readable.
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

    def start(self, url: str, target: str) -> None:
        if self._running:
            return
        self._running = True
        self._cancelled = False

        def work() -> None:
            try:
                path = download_verified(
                    url,
                    target,
                    on_progress=self._advance,
                    cancelled=lambda: self._cancelled,
                )
            except DownloadError as exc:
                self._running = False
                self._notify(self.failed, str(exc))
            except Exception as exc:                # pragma: no cover - defensive
                self._running = False
                self._notify(self.failed, str(exc))
            else:
                self._running = False
                self._notify(self.finished, path)

        threading.Thread(target=work, daemon=True, name="easypdf-download").start()

    def _advance(self, downloaded: int, total: int) -> None:
        self._notify(self.progress, downloaded, total)

    def _notify(self, signal, *args) -> None:
        if self._cancelled:
            return
        try:
            signal.emit(*args)
        except RuntimeError:
            # The window closed while downloading: there is nobody to tell.
            pass


class UpdateDialog(QDialog):
    """New version notice with download and install.

    Three moments in the same window: it is offered, it is downloaded, and
    once ready it is installed. The window is not swapped so that it stays
    clear that all of it is part of the same thing.
    """

    def __init__(self, parent, new_version: str, data: dict, install_cb=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("update_title"))
        self.setMinimumWidth(440)
        self._new_version = new_version
        self._data = data or {}
        self._install_cb = install_cb
        self._web = str(self._data.get("url") or __url__)
        self._downloader: Downloader | None = None
        self._file = ""
        #: The main window reads this so it does not warn about this version again.
        self.skipped = False

        layout = QVBoxLayout(self)
        self.text = QLabel(tr("update_body", new=new_version, old=__version__))
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setWordWrap(True)
        layout.addWidget(self.text)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#666")
        self.note.hide()
        layout.addWidget(self.note)

        self.bar = QProgressBar()
        self.bar.hide()
        layout.addWidget(self.bar)

        self.button_row = QHBoxLayout()
        self.button_row.addStretch(1)
        layout.addLayout(self.button_row)

        self._offer()

    # -------------------------------------------------------------- buttons
    def _clear_buttons(self) -> None:
        while self.button_row.count() > 1:            # the stretch stays
            entry = self.button_row.takeAt(1)
            widget = entry.widget()
            if widget is not None:
                # Taking it out of the layout is not enough: it is still a
                # child of the dialog and stays painted where it was. And
                # deleteLater() does not remove it until the event loop comes
                # back around, so the parent is dropped as well to make it
                # disappear right away.
                widget.setParent(None)
                widget.deleteLater()

    def _button(self, text: str, slot, main: bool = False) -> QPushButton:
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        button.setDefault(main)
        button.setAutoDefault(main)
        self.button_row.addWidget(button)
        return button

    # --------------------------------------------------------------- states
    def _offer(self) -> None:
        """First moment: say there is a new version and offer to fetch it."""
        self._clear_buttons()
        package = asset_for_platform(self._data)
        if package is not None:
            self.download_button = self._button(
                tr("update_download"), self._download, main=True
            )
        else:
            self.note.setText(tr("update_no_asset"))
            self.note.show()
        self._button(tr("update_go"), self._open_web)
        self._button(tr("update_later"), self.reject)
        self._button(tr("update_skip"), self._skip)
        self._fit()

    def _download(self) -> None:
        """Second moment: fetch the package this system needs."""
        package = asset_for_platform(self._data)
        if package is None:                          # pragma: no cover - no button
            return
        url, name = package
        target = os.path.join(download_dir(), name)

        self._clear_buttons()
        self.text.setText(tr("update_downloading", name=name))
        self.note.hide()
        self.bar.setRange(0, 0)                      # indeterminate until the total is known
        # The text goes below, not inside: over a half-painted bar it reads
        # badly exactly where the colour changes.
        self.bar.setTextVisible(False)
        self.bar.show()
        self.note.setText("")
        self.note.show()
        self._button(tr("update_cancel"), self._cancel)

        self._downloader = Downloader(self)
        self._downloader.progress.connect(self._progress)
        self._downloader.finished.connect(self._ready)
        self._downloader.failed.connect(self._failure)
        self._downloader.start(url, target)
        self._fit()

    def _progress(self, downloaded: int, total: int) -> None:
        done = downloaded / MEGA
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(downloaded)
            self.note.setText(
                tr("update_progress", done=f"{done:.1f}", total=f"{total / MEGA:.1f}")
            )
        else:
            self.note.setText(tr("update_progress_unknown", done=f"{done:.1f}"))
        if total > 0 and downloaded >= total:
            # The sha256 still has to be checked, which shows on a 40 MB file.
            self.note.setText(tr("update_verifying"))

    def _ready(self, path: str) -> None:
        """Third moment: the file is downloaded and verified."""
        self._file = path
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.bar.hide()
        self._clear_buttons()
        if is_installer(path):
            self.text.setText(tr("update_ready_install"))
            self.note.hide()
            self._button(tr("update_install_now"), self._install, main=True)
        else:
            # On Linux a portable package is published: there is nothing to
            # run, it is unpacked over the copy the user already has.
            self.text.setText(tr("update_ready_file", path=path))
            self.note.hide()
            self._button(tr("update_open_folder"), self._open_folder, main=True)
        self._button(tr("update_close"), self.accept)
        self._fit()

    def _failure(self, reason: str) -> None:
        self.bar.hide()
        self.text.setText(tr("update_download_failed", error=reason))
        self.note.hide()
        self._clear_buttons()
        self._button(tr("update_go"), self._open_web)
        self._button(tr("update_close"), self.reject, main=True)
        self._fit()

    def _fit(self) -> None:
        """Each moment takes its own room; let the window follow."""
        self.layout().activate()
        self.adjustSize()

    # --------------------------------------------------------------- actions
    def _install(self) -> None:
        if self._install_cb is not None and not self._install_cb(self._file):
            return                                   # the user backed out
        if self._install_cb is None:                 # pragma: no cover - no window
            launch_installer(self._file)
        self.accept()

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self._file)))

    def _open_web(self) -> None:
        QDesktopServices.openUrl(QUrl(self._web))
        self.accept()

    def _skip(self) -> None:
        self.skipped = True
        self.reject()

    def _cancel(self) -> None:
        if self._downloader is not None:
            self._downloader.cancel()
        self.reject()

    def closeEvent(self, event) -> None:
        if self._downloader is not None:
            self._downloader.cancel()
        super().closeEvent(event)


__all__ = ["Downloader", "UpdateDialog", "download_dir", "MEGA"]
