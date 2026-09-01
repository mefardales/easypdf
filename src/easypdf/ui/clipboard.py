"""Copy and paste annotations through the system clipboard.

The real clipboard is used, rather than an internal variable, so you can copy
in one window and paste in another. What is copied carries a marker of its own
inside, so a plain text copied from some other program never turns into
annotations by accident.
"""

from __future__ import annotations

import json

from PySide6.QtGui import QGuiApplication

from ..model import Annotation
from ..templates import TemplateError, annotation_from_dict, annotation_to_dict

#: Custom MIME type kept only to read what older versions copied.
MIME = "application/x-easypdf-annotations"

#: Format version, in case what gets stored ever changes.
FORMAT = 1


def _clipboard():
    application = QGuiApplication.instance()
    return application.clipboard() if application is not None else None


def encode(annotations) -> str:
    """Serialise the annotations into the text that travels the clipboard."""
    return json.dumps(
        {"easypdf": FORMAT, "annotations": [annotation_to_dict(a) for a in annotations]},
        ensure_ascii=False,
    )


def decode(text: str) -> list[Annotation]:
    """Read whatever was copied. Returns [] if it is not ours."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict) or "easypdf" not in data:
        return []
    result = []
    for entry in data.get("annotations") or []:
        try:
            result.append(annotation_from_dict(entry))
        except (TemplateError, TypeError, ValueError, KeyError):
            continue          # one broken annotation must not sink the rest
    return result


def copy_annotations(annotations) -> int:
    """Leave the annotations on the clipboard. Returns how many."""
    items = list(annotations)
    clipboard = _clipboard()
    if not items or clipboard is None:
        return 0
    # Sent as plain text rather than with a custom MIME type on purpose. A
    # QMimeData built here is taken over by the clipboard, but the Python
    # wrapper also believes it owns it, and both delete it: the program
    # crashed on exit once anything had been copied. Text has no such problem
    # and nothing is lost: what is copied carries its own marker and decode()
    # checks it, so another program's text still cannot slip in.
    clipboard.setText(encode(items))
    return len(items)


def clipboard_annotations() -> list[Annotation]:
    """What was copied from this program, or [] if there is nothing of ours."""
    clipboard = _clipboard()
    if clipboard is None:
        return []
    data = clipboard.mimeData()
    if data is not None and data.hasFormat(MIME):
        # Copied by an older version, which did use a custom type.
        return decode(bytes(data.data(MIME)).decode("utf-8", "replace"))
    return decode(clipboard.text())


def has_annotations() -> bool:
    return bool(clipboard_annotations())


__all__ = [
    "FORMAT", "MIME", "clipboard_annotations", "copy_annotations", "decode",
    "encode", "has_annotations",
]
