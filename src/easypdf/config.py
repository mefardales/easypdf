"""Preferencias persistentes de easypdf.surf (QSettings).

ORG y APP no cambian aunque cambie el nombre mostrado: son la ruta donde el
sistema guarda los ajustes, y moverla haria perder las preferencias.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from . import __app_name__

ORG = "EasyPDF"
APP = "EasyPDF"

MAX_RECENT = 10

#: Paleta rapida que se ofrece en la barra de herramientas.
PALETTE: tuple[tuple[str, str], ...] = (
    ("Rojo", "#d81b1b"),
    ("Azul", "#1565c0"),
    ("Verde", "#2e7d32"),
    ("Naranja", "#ef6c00"),
    ("Morado", "#6a1b9a"),
    ("Negro", "#111111"),
    ("Amarillo", "#ffd400"),
)

DEFAULT_COLOR = "#d81b1b"
DEFAULT_FILL = ""          # cadena vacia = sin relleno
DEFAULT_HIGHLIGHT = "#ffd400"
DEFAULT_WIDTH = 2.0
DEFAULT_OPACITY = 1.0
DEFAULT_FONT_SIZE = 12.0
DEFAULT_ZOOM = 1.0

MIN_ZOOM = 0.10
MAX_ZOOM = 8.0


class Settings:
    """Envoltorio tipado sobre QSettings."""

    def __init__(self) -> None:
        self._s = QSettings(ORG, APP)

    # -- generico --------------------------------------------------------
    def value(self, key: str, default=None, type_=None):
        if type_ is None:
            return self._s.value(key, default)
        return self._s.value(key, default, type=type_)

    def set_value(self, key: str, value) -> None:
        self._s.setValue(key, value)

    def sync(self) -> None:
        self._s.sync()

    # -- archivos recientes ---------------------------------------------
    def recent_files(self) -> list[str]:
        raw = self._s.value("files/recent", [])
        if isinstance(raw, str):
            raw = [raw]
        return [str(p) for p in (raw or [])]

    def push_recent(self, path: str) -> list[str]:
        files = [p for p in self.recent_files() if p.lower() != path.lower()]
        files.insert(0, path)
        del files[MAX_RECENT:]
        self._s.setValue("files/recent", files)
        return files

    def clear_recent(self) -> None:
        self._s.setValue("files/recent", [])

    def last_dir(self) -> str:
        return str(self._s.value("files/last_dir", ""))

    def set_last_dir(self, path: str) -> None:
        self._s.setValue("files/last_dir", path)

    # -- herramientas ----------------------------------------------------
    def tool_color(self) -> str:
        return str(self._s.value("tools/color", DEFAULT_COLOR))

    def set_tool_color(self, value: str) -> None:
        self._s.setValue("tools/color", value)

    def tool_fill(self) -> str:
        return str(self._s.value("tools/fill", DEFAULT_FILL))

    def set_tool_fill(self, value: str) -> None:
        self._s.setValue("tools/fill", value)

    def tool_width(self) -> float:
        return float(self._s.value("tools/width", DEFAULT_WIDTH))

    def set_tool_width(self, value: float) -> None:
        self._s.setValue("tools/width", float(value))

    def tool_opacity(self) -> float:
        return float(self._s.value("tools/opacity", DEFAULT_OPACITY))

    def set_tool_opacity(self, value: float) -> None:
        self._s.setValue("tools/opacity", float(value))

    def tool_font_size(self) -> float:
        return float(self._s.value("tools/font_size", DEFAULT_FONT_SIZE))

    def set_tool_font_size(self, value: float) -> None:
        self._s.setValue("tools/font_size", float(value))

    def tool_font(self) -> str:
        return str(self._s.value("tools/font", "helv"))

    def set_tool_font(self, value: str) -> None:
        self._s.setValue("tools/font", value)

    def tool_bold(self) -> bool:
        return str(self._s.value("tools/bold", "false")).lower() in ("1", "true", "yes")

    def set_tool_bold(self, value: bool) -> None:
        self._s.setValue("tools/bold", bool(value))

    def tool_italic(self) -> bool:
        return str(self._s.value("tools/italic", "false")).lower() in ("1", "true", "yes")

    def set_tool_italic(self, value: bool) -> None:
        self._s.setValue("tools/italic", bool(value))

    def tool_align(self) -> int:
        return int(self._s.value("tools/align", 0))

    def set_tool_align(self, value: int) -> None:
        self._s.setValue("tools/align", int(value))

    def table_rows(self) -> int:
        return int(self._s.value("tools/table_rows", 3))

    def set_table_rows(self, value: int) -> None:
        self._s.setValue("tools/table_rows", int(value))

    def table_cols(self) -> int:
        return int(self._s.value("tools/table_cols", 3))

    def set_table_cols(self, value: int) -> None:
        self._s.setValue("tools/table_cols", int(value))

    # -- ventana ---------------------------------------------------------
    def window_geometry(self) -> bytes | None:
        return self._s.value("window/geometry")

    def set_window_geometry(self, data) -> None:
        self._s.setValue("window/geometry", data)

    def window_state(self) -> bytes | None:
        return self._s.value("window/state")

    def set_window_state(self, data) -> None:
        self._s.setValue("window/state", data)

    def show_thumbnails(self) -> bool:
        return str(self._s.value("window/thumbnails", "true")).lower() in ("1", "true", "yes")

    def set_show_thumbnails(self, value: bool) -> None:
        self._s.setValue("window/thumbnails", bool(value))


__all__ = ["Settings", "PALETTE", "APP", "ORG", "__app_name__"]
