"""New version notice.

The installed program reads a small file from the official site and, if a
newer version is out, says so and offers to download and install it. None of
that happens on its own: the download only starts if the user presses the
button.

The query is a GET request that sends no data: no identifier, no list of open
documents, nothing. With no internet it fails silently.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

#: Where the latest published version is read from. The site generates it.
LATEST_URL = "https://easypdf.surf/latest.json"

#: How long to wait before giving up, in seconds. Deliberately short: this
#: must not hold up the program's start-up.
TIMEOUT = 6.0


def parse_version(text: str) -> tuple[int, ...]:
    """Turn '1.2.0' into (1, 2, 0) so versions can be compared.

    Anything that is not a digit is ignored, so '1.2.0-beta' counts as
    (1, 2, 0). A string with no digits at all gives (0,), which loses against
    any version.
    """
    parts: list[int] = []
    for piece in str(text).strip().lstrip("vV").split("."):
        digits = ""
        for character in piece:
            if not character.isdigit():
                break
            digits += character
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def is_newer(candidate: str, current: str) -> bool:
    """True if ``candidate`` is a later version than ``current``."""
    return parse_version(candidate) > parse_version(current)


def fetch_latest(url: str = LATEST_URL, timeout: float = TIMEOUT) -> dict | None:
    """Read the file from the site. Returns None if it cannot."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "easypdf.surf", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError, TimeoutError):
        return None            # no internet, or the site is not answering
    return data if isinstance(data, dict) else None


def check(current: str, url: str = LATEST_URL, timeout: float = TIMEOUT) -> dict | None:
    """Return the new version's data, or None if there is nothing newer."""
    data = fetch_latest(url, timeout)
    if not data:
        return None
    version = str(data.get("version", "")).strip()
    if not version or not is_newer(version, current):
        return None
    return data


# ---------------------------------------------------------------- download
#: How much is read at a time while downloading.
CHUNK = 256 * 1024


class DownloadError(RuntimeError):
    """The download failed or the file did not arrive intact."""


def asset_for_platform(data: dict) -> tuple[str, str] | None:
    """Return (url, file name) of the package this system needs."""
    if sys.platform.startswith("win"):
        key = "setup"
    elif sys.platform.startswith("linux"):
        key = "linux"
    else:
        return None                    # there is no Mac package yet
    url = str(data.get(key) or "")
    if not url:
        return None
    return (url, url.rsplit("/", 1)[-1])


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_sha256(url: str, timeout: float = TIMEOUT) -> str | None:
    """Read the .sha256 published next to every download."""
    data = _get(url + ".sha256", timeout)
    if data is None:
        return None
    first = data.decode("utf-8", "replace").strip().split()
    return first[0].lower() if first else None


def _get(url: str, timeout: float) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "easypdf.surf"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def download(url: str, target: str, on_progress=None, cancelled=None,
             timeout: float = 30.0) -> str:
    """Download a file and return its path.

    ``on_progress(done, total)`` is called as it advances (total may be 0 if
    the server does not say), and ``cancelled()`` allows aborting.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "easypdf.surf"})
    partial = target + ".part"
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(partial, "wb") as fh:
                while True:
                    if cancelled is not None and cancelled():
                        raise DownloadError("cancelled")
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if on_progress is not None:
                        on_progress(done, total)
        os.replace(partial, target)
    except DownloadError:
        _remove(partial)
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _remove(partial)
        raise DownloadError(str(exc)) from exc
    return target


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def download_verified(url: str, target: str, on_progress=None, cancelled=None,
                      timeout: float = 30.0) -> str:
    """Download and check the sha256 before treating the file as good.

    This is essential: what is downloaded here gets executed to install, so we
    have to be sure it is exactly what was published.
    """
    expected = expected_sha256(url, timeout=TIMEOUT)
    download(url, target, on_progress, cancelled, timeout)
    if expected:
        current = sha256_of(target)
        if current != expected:
            _remove(target)
            raise DownloadError(
                f"the download does not match the published one "
                f"({current[:12]} != {expected[:12]})"
            )
    return target


def is_installer(path: str) -> bool:
    """True if what was downloaded can be run to install.

    Only the Windows .exe: on Linux a portable package is published, which is
    unpacked by hand over the copy the user already has.
    """
    return os.name == "nt" and path.lower().endswith(".exe")


def launch_installer(path: str) -> None:
    """Start the installer and let it carry on by itself.

    It is launched detached on purpose: the program closes right afterwards,
    because the installer has to be able to replace its own files.
    """
    if not is_installer(path):
        raise DownloadError(f"cannot install {path}")
    os.startfile(path)  # type: ignore[attr-defined]  # Windows only


__all__ = [
    "CHUNK", "DownloadError", "LATEST_URL", "TIMEOUT", "asset_for_platform",
    "check", "download", "download_verified", "expected_sha256", "fetch_latest",
    "is_installer", "is_newer", "launch_installer", "parse_version", "sha256_of",
]
