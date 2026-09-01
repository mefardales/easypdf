"""Application entry point."""

from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from . import __app_name__, __version__
from .config import APP, ORG


def _set_windows_app_id() -> None:
    """Group the window under its own icon in the Windows taskbar."""
    if sys.platform != "win32":  # pragma: no cover - Windows only
        return
    try:  # pragma: no cover - Windows only
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"EasyPDF.{__app_name__}.{__version__}"
        )
    except Exception:
        pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="easypdf",
        description="easypdf.surf: PDF reader with simple annotations.",
    )
    parser.add_argument("file", nargs="?", help="PDF to open on start-up")
    parser.add_argument(
        "--version", action="version", version=f"{__app_name__} {__version__}"
    )
    return parser.parse_args(argv)


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create (or reuse) the QApplication with easypdf.surf's settings."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP)
    app.setOrganizationName(ORG)
    app.setApplicationDisplayName(__app_name__)
    app.setApplicationVersion(__version__)
    from .ui import icons

    app.setWindowIcon(icons.app_icon())
    return app


def main(argv: list[str] | None = None) -> int:
    """Start the graphical interface. Returns the exit code."""
    argv = list(sys.argv if argv is None else argv)
    args = parse_args(argv[1:])

    if hasattr(Qt, "AA_UseHighDpiPixmaps"):  # Qt 6 already does this
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    _set_windows_app_id()

    app = create_application(argv)

    from .ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    if args.file:
        path = os.path.abspath(os.path.expanduser(args.file))
        window.open_path(path)

    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
