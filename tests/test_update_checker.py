"""Tests fuer update_checker.py."""

from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from werkstatt_sync.update_checker import parse_version, pruefe_update_im_hintergrund


class TestParseVersion:
    def test_mit_v_praefix(self):
        assert parse_version("v1.2.3") == (1, 2, 3)

    def test_ohne_v_praefix(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_zweistellig(self):
        assert parse_version("v2.0") == (2, 0)

    def test_einstellig(self):
        assert parse_version("v2") == (2,)

    def test_vergleich_neuer(self):
        assert parse_version("v1.1.0") > parse_version("v1.0.0")

    def test_vergleich_gleich(self):
        assert parse_version("v1.0.0") == parse_version("1.0.0")

    def test_vergleich_aelter(self):
        assert parse_version("v0.9.9") < parse_version("v1.0.0")

    def test_major_schlaegt_minor(self):
        assert parse_version("v2.0.0") > parse_version("v1.99.99")


def _fake_urlopen(tag_name: str):
    """Gibt einen Context-Manager zurueck, der eine GitHub-API-Antwort simuliert."""
    payload = json.dumps({"tag_name": tag_name}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestPruefUpdateImHintergrund:
    def _warte_auf_thread(self, timeout=2.0):
        """Wartet kurz, bis der Hintergrund-Thread abgeschlossen ist."""
        # Alle nicht-Haupt-Daemon-Threads joinen
        for t in threading.enumerate():
            if t is not threading.main_thread() and t.daemon:
                t.join(timeout=timeout)

    def test_callback_bei_neuerer_version(self):
        ergebnis = []
        with patch(
            "werkstatt_sync.update_checker.urlopen",
            return_value=_fake_urlopen("v2.0.0"),
        ):
            pruefe_update_im_hintergrund("1.0.0", ergebnis.append)
            self._warte_auf_thread()

        assert ergebnis == ["v2.0.0"]

    def test_kein_callback_bei_gleicher_version(self):
        ergebnis = []
        with patch(
            "werkstatt_sync.update_checker.urlopen",
            return_value=_fake_urlopen("v1.0.0"),
        ):
            pruefe_update_im_hintergrund("1.0.0", ergebnis.append)
            self._warte_auf_thread()

        assert ergebnis == []

    def test_kein_callback_bei_aelterer_version(self):
        ergebnis = []
        with patch(
            "werkstatt_sync.update_checker.urlopen",
            return_value=_fake_urlopen("v0.9.0"),
        ):
            pruefe_update_im_hintergrund("1.0.0", ergebnis.append)
            self._warte_auf_thread()

        assert ergebnis == []

    def test_kein_callback_bei_netzwerkfehler(self):
        ergebnis = []
        with patch(
            "werkstatt_sync.update_checker.urlopen",
            side_effect=URLError("kein Netz"),
        ):
            pruefe_update_im_hintergrund("1.0.0", ergebnis.append)
            self._warte_auf_thread()

        assert ergebnis == []

    def test_kein_callback_bei_leerem_tag(self):
        ergebnis = []
        with patch(
            "werkstatt_sync.update_checker.urlopen",
            return_value=_fake_urlopen(""),
        ):
            pruefe_update_im_hintergrund("1.0.0", ergebnis.append)
            self._warte_auf_thread()

        assert ergebnis == []

    def test_kein_callback_bei_ungueltigem_json(self):
        ergebnis = []
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"kein json{"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("werkstatt_sync.update_checker.urlopen", return_value=mock_resp):
            pruefe_update_im_hintergrund("1.0.0", ergebnis.append)
            self._warte_auf_thread()

        assert ergebnis == []
