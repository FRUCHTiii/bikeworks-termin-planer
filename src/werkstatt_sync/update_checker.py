"""Update-Pruefung: vergleicht laufende Version mit neuestem GitHub-Release."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

GITHUB_API_URL = "https://api.github.com/repos/FRUCHTiii/bikeworks-termin-planer/releases/latest"
_TIMEOUT = 5  # Sekunden


def parse_version(tag: str) -> tuple[int, ...]:
    """Wandelt 'v1.2.3' oder '1.2.3' in (1, 2, 3) um."""
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def pruefe_update_im_hintergrund(
    aktuelle_version: str,
    callback: Callable[[str], None],
) -> None:
    """Startet einen Daemon-Thread, der die neuste GitHub-Release-Version abruft.

    callback wird mit dem neusten Tag-String aufgerufen, falls eine neuere
    Version verfuegbar ist. Bei Netzwerkfehlern passiert nichts (stilles Fail).
    """

    def _check():
        try:
            req = Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github+json"})
            with urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            neuester_tag = data.get("tag_name", "")
            if not neuester_tag:
                return
            if parse_version(neuester_tag) > parse_version(aktuelle_version):
                callback(neuester_tag)
        except (URLError, ValueError, KeyError, OSError):
            pass  # Kein Netz, API-Fehler o.ae. - einfach ignorieren

    threading.Thread(target=_check, daemon=True).start()
