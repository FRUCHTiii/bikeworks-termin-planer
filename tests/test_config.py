"""Tests fuer config.py: Parser, Defaults, Persistenz."""

import json

import pytest

from werkstatt_sync.config import (
    AppConfig,
    format_zeitfenster,
    parse_zeitfenster,
)


class TestParseZeitfenster:
    def test_einzelner_block(self):
        assert parse_zeitfenster("9-11") == [(9, 11)]

    def test_zwei_bloecke_mit_semikolon(self):
        assert parse_zeitfenster("8-12; 13-15") == [(8, 12), (13, 15)]

    def test_whitespace_egal(self):
        assert parse_zeitfenster("  8 - 12 ; 13 - 15  ") == [(8, 12), (13, 15)]

    def test_komma_als_trenner(self):
        assert parse_zeitfenster("8-12, 13-15") == [(8, 12), (13, 15)]

    def test_geviertstrich(self):
        # Manche Tastatur-Layouts produzieren – statt -
        assert parse_zeitfenster("9–17") == [(9, 17)]

    def test_frei(self):
        assert parse_zeitfenster("frei") == []

    def test_leerer_string(self):
        assert parse_zeitfenster("") == []

    def test_geschlossen(self):
        assert parse_zeitfenster("geschlossen") == []

    def test_grossschreibung_egal(self):
        assert parse_zeitfenster("FREI") == []

    def test_ungueltig_kein_bindestrich(self):
        with pytest.raises(ValueError):
            parse_zeitfenster("9 bis 11")

    def test_ungueltig_keine_zahl(self):
        with pytest.raises(ValueError):
            parse_zeitfenster("abc-def")

    def test_ungueltig_start_groesser_ende(self):
        with pytest.raises(ValueError):
            parse_zeitfenster("11-9")

    def test_ungueltig_negative_zeit(self):
        with pytest.raises(ValueError):
            parse_zeitfenster("-1-5")

    def test_ungueltig_ueber_24(self):
        with pytest.raises(ValueError):
            parse_zeitfenster("9-25")


class TestFormatZeitfenster:
    def test_leer_wird_frei(self):
        assert format_zeitfenster([]) == "frei"

    def test_einzelner_block(self):
        assert format_zeitfenster([(9, 11)]) == "9-11"

    def test_mehrere_bloecke(self):
        assert format_zeitfenster([(8, 12), (13, 15)]) == "8-12; 13-15"


class TestRoundtrip:
    @pytest.mark.parametrize(
        "text",
        [
            "9-11",
            "8-12; 13-15",
            "frei",
            "",
            "9–17",  # mit Geviertstrich
            "10-14",
        ],
    )
    def test_parse_format_parse(self, text):
        """parse -> format -> parse muss stabile Slots ergeben."""
        slots_1 = parse_zeitfenster(text)
        formatted = format_zeitfenster(slots_1)
        slots_2 = parse_zeitfenster(formatted)
        assert slots_1 == slots_2


class TestAppConfig:
    def test_default_hat_alle_wochentage(self):
        cfg = AppConfig.default()
        for wd in range(7):
            assert wd in cfg.days, f"Wochentag {wd} fehlt"

    def test_default_mittwoch_und_freitag_voll(self):
        cfg = AppConfig.default()
        assert cfg.days[2].slots == [(8, 12), (13, 15)]  # Mi
        assert cfg.days[4].slots == [(8, 12), (13, 15)]  # Fr

    def test_default_wochenende_frei(self):
        cfg = AppConfig.default()
        assert cfg.days[5].slots == []  # Sa
        assert cfg.days[6].slots == []  # So

    def test_roundtrip_to_dict_from_dict(self):
        cfg = AppConfig.default()
        cfg.default_dauer_stunden = 1.5
        cfg.kalender_id = "abc@group.calendar.google.com"
        cfg.planung_ab_morgen = False

        d = cfg.to_dict()
        # JSON-fest? (kein dict-int-key-Stolpern)
        json_str = json.dumps(d)
        d_back = json.loads(json_str)
        cfg_back = AppConfig.from_dict(d_back)

        assert cfg_back.default_dauer_stunden == 1.5
        assert cfg_back.kalender_id == "abc@group.calendar.google.com"
        assert cfg_back.planung_ab_morgen is False
        assert cfg_back.days[2].slots == [(8, 12), (13, 15)]
        assert cfg_back.days[5].slots == []

    def test_from_dict_mit_fehlenden_feldern_nutzt_defaults(self):
        # Minimales Dict (z.B. alte Config-Version)
        cfg = AppConfig.from_dict({"days": {}})
        assert cfg.default_dauer_stunden == 1.0
        assert cfg.kalender_id == "primary"
