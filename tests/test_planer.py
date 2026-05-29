"""Tests fuer planer.py: Auftraege verteilen auf Slots."""

import datetime as dt

import pytest

from werkstatt_sync.config import AppConfig, DayConfig
from werkstatt_sync.excel_parser import Auftrag
from werkstatt_sync.planer import (
    berechne_startzeitpunkt,
    naechster_halbstunden_slot,
    plane_auftraege,
    tages_slots,
)


def make_auftrag(nummer: int, dauer: float = 1.0, hat_zeit: bool = True) -> Auftrag:
    return Auftrag(
        nummer=nummer,
        kunde=f"Kunde {nummer}",
        dauer_stunden=dauer,
        hat_zeit_notiz=hat_zeit,
    )


@pytest.fixture
def montag():
    """1. Juni 2026 ist ein Montag."""
    return dt.datetime(2026, 6, 1)


@pytest.fixture
def cfg_default():
    return AppConfig.default()


class TestTagesSlots:
    def test_montag_default_9_bis_11(self, cfg_default, montag):
        slots = tages_slots(montag, cfg_default)
        assert len(slots) == 1
        assert slots[0][0].hour == 9
        assert slots[0][1].hour == 11

    def test_mittwoch_zwei_bloecke(self, cfg_default, montag):
        mittwoch = montag + dt.timedelta(days=2)
        slots = tages_slots(mittwoch, cfg_default)
        assert len(slots) == 2
        # Erster Block: 8-12
        assert (slots[0][0].hour, slots[0][1].hour) == (8, 12)
        # Zweiter Block: 13-15
        assert (slots[1][0].hour, slots[1][1].hour) == (13, 15)

    def test_samstag_keine_slots(self, cfg_default, montag):
        samstag = montag + dt.timedelta(days=5)
        assert tages_slots(samstag, cfg_default) == []

    def test_sonntag_keine_slots(self, cfg_default, montag):
        sonntag = montag + dt.timedelta(days=6)
        assert tages_slots(sonntag, cfg_default) == []


class TestPlanerReihenfolge:
    def test_reihenfolge_wird_beibehalten(self, cfg_default, montag):
        """Der erste Auftrag in der Liste bekommt den ersten Slot."""
        auftraege = [make_auftrag(100), make_auftrag(99), make_auftrag(98)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)

        # Erster Termin am Montag um 9 ist Nr. 100
        assert geplant[0].auftrag.nummer == 100
        assert geplant[1].auftrag.nummer == 99
        assert geplant[2].auftrag.nummer == 98


class TestPlanerSlotFuellung:
    def test_montag_2h_slot_fasst_zwei_1h_auftraege(self, cfg_default, montag):
        auftraege = [make_auftrag(1), make_auftrag(2), make_auftrag(3)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)
        # Mo 9-11: 2 Auftraege, dann Di 9-11: 1 Auftrag
        mo = [t for t in geplant if t.start.date() == montag.date()]
        assert len(mo) == 2

    def test_kein_aufteilen_ueber_slot_grenzen(self, cfg_default, montag):
        """Ein 1.5h-Auftrag passt nicht in 1h-Rest, KEIN Backfill verfuegbar -> naechster Slot."""
        auftraege = [make_auftrag(1, dauer=1.0), make_auftrag(2, dauer=1.5)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)

        assert len(geplant) == 2
        assert geplant[0].start.date() == montag.date()
        assert geplant[0].start.hour == 9
        assert geplant[1].start.date() == (montag + dt.timedelta(days=1)).date()
        assert geplant[1].start.hour == 9

    def test_passt_in_aktuellen_slot(self, cfg_default, montag):
        """Ein 30-Min-Auftrag passt in den Rest eines fast-vollen Slots."""
        # Mo 9-11 = 2h. 1h + 0.5h + 0.5h passen alle in den Slot.
        auftraege = [
            make_auftrag(1, dauer=1.0),
            make_auftrag(2, dauer=0.5),
            make_auftrag(3, dauer=0.5),
        ]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)
        # Alle drei am Montag
        for t in geplant:
            assert t.start.date() == montag.date()

    def test_mittwoch_voller_tag_fuellt_beide_bloecke(self, cfg_default, montag):
        # Mi hat 8-12 und 13-15 = 4h + 2h = 6h. 6 1h-Auftraege passen.
        mittwoch = montag + dt.timedelta(days=2)
        auftraege = [make_auftrag(i, dauer=1.0) for i in range(1, 7)]
        # cfg so anpassen, dass nur Mi Slots hat
        cfg = AppConfig(days={i: DayConfig([]) for i in range(7)})
        cfg.days[2] = cfg_default.days[2]  # Mi
        geplant, ungeplant = plane_auftraege(auftraege, cfg, start_datum=mittwoch)

        assert len(geplant) == 6
        assert len(ungeplant) == 0
        # Erster Block: 8-12 = 4 Auftraege
        block1 = [t for t in geplant if t.start.hour < 12]
        assert len(block1) == 4
        # Zweiter Block: 13-15 = 2 Auftraege
        block2 = [t for t in geplant if t.start.hour >= 13]
        assert len(block2) == 2

    def test_mittagspause_wird_respektiert(self, cfg_default, montag):
        """Kein Auftrag laeuft 12-13 Uhr."""
        mittwoch = montag + dt.timedelta(days=2)
        auftraege = [make_auftrag(i, dauer=1.0) for i in range(1, 10)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=mittwoch)

        for t in geplant:
            # Kein Termin darf 12:00-13:00 ueberschneiden
            mittag_start = t.start.replace(hour=12, minute=0)
            mittag_ende = t.start.replace(hour=13, minute=0)
            assert not (t.start < mittag_ende and t.ende > mittag_start), (
                f"Termin #{t.auftrag.nummer} {t.start.time()}-{t.ende.time()} "
                f"ueberschneidet Mittagspause"
            )

    def test_keine_ueberlappenden_termine(self, cfg_default, montag):
        auftraege = [make_auftrag(i, dauer=0.5) for i in range(1, 10)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)

        for a, b in zip(geplant, geplant[1:], strict=False):
            # b muss spaeter oder am gleichen Punkt starten wie a endet
            assert b.start >= a.ende, f"Ueberlappung: {a.ende} vs {b.start}"


class TestPlanerLimits:
    def test_freier_tag_wird_uebersprungen(self, montag):
        # Nur Montag 9-11 frei (= 2h), Rest komplett zu
        cfg = AppConfig(days={i: DayConfig([]) for i in range(7)})
        cfg.days[0] = DayConfig([(9, 11)])
        cfg.max_planungstage = 30

        # 4 1h-Auftraege: 2 am ersten Mo, 2 am Mo der naechsten Woche
        auftraege = [make_auftrag(i, dauer=1.0) for i in range(1, 5)]
        geplant, _ = plane_auftraege(auftraege, cfg, start_datum=montag)

        assert len(geplant) == 4
        # Tag 1+2 am Mo, Tag 3+4 am Mo eine Woche spaeter
        assert geplant[0].start.date() == montag.date()
        assert geplant[1].start.date() == montag.date()
        assert geplant[2].start.date() == (montag + dt.timedelta(days=7)).date()
        assert geplant[3].start.date() == (montag + dt.timedelta(days=7)).date()

    def test_ueberzaehlige_auftraege_landen_in_ungeplant(self, montag):
        # Nur Mo 9-10 = 1h Slot, max 7 Tage Planung
        cfg = AppConfig(days={i: DayConfig([]) for i in range(7)})
        cfg.days[0] = DayConfig([(9, 10)])
        cfg.max_planungstage = 6  # nur ein Montag in dem Fenster

        auftraege = [make_auftrag(i, dauer=1.0) for i in range(1, 5)]
        geplant, ungeplant = plane_auftraege(auftraege, cfg, start_datum=montag)

        assert len(geplant) == 1
        assert len(ungeplant) == 3
        assert ungeplant[0].nummer == 2  # Reihenfolge bleibt


class TestPlanerDauerEdgeCases:
    def test_15_minuten_dauer(self, cfg_default, montag):
        """0.25h = 15 Minuten, ungewoehnlich aber muss laufen."""
        auftraege = [make_auftrag(1, dauer=0.25)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)
        assert len(geplant) == 1
        assert (geplant[0].ende - geplant[0].start).total_seconds() == 15 * 60

    def test_auftrag_groesser_als_jeder_slot_landet_in_ungeplant(self, montag):
        cfg = AppConfig(days={i: DayConfig([(9, 10)]) for i in range(5)})
        auftraege = [make_auftrag(1, dauer=3.0)]  # 3h aber max 1h Slots
        geplant, ungeplant = plane_auftraege(auftraege, cfg, start_datum=montag)

        assert len(geplant) == 0
        assert len(ungeplant) == 1


class TestNaechsterHalbstundenSlot:
    """Tests fuer das Aufrunden auf 30/60-Minuten-Grenzen."""

    def test_volle_stunde_bleibt(self):
        assert naechster_halbstunden_slot(dt.datetime(2026, 6, 1, 14, 0, 0)) == dt.datetime(
            2026, 6, 1, 14, 0
        )

    def test_halbe_stunde_bleibt(self):
        assert naechster_halbstunden_slot(dt.datetime(2026, 6, 1, 14, 30, 0)) == dt.datetime(
            2026, 6, 1, 14, 30
        )

    def test_eine_sekunde_nach_voll_geht_zur_halben(self):
        assert naechster_halbstunden_slot(dt.datetime(2026, 6, 1, 14, 0, 1)) == dt.datetime(
            2026, 6, 1, 14, 30
        )

    def test_14_29_geht_zur_halben(self):
        assert naechster_halbstunden_slot(dt.datetime(2026, 6, 1, 14, 29)) == dt.datetime(
            2026, 6, 1, 14, 30
        )

    def test_14_31_geht_zur_naechsten_vollen(self):
        assert naechster_halbstunden_slot(dt.datetime(2026, 6, 1, 14, 31)) == dt.datetime(
            2026, 6, 1, 15, 0
        )

    def test_14_59_geht_zur_naechsten_vollen(self):
        assert naechster_halbstunden_slot(dt.datetime(2026, 6, 1, 14, 59)) == dt.datetime(
            2026, 6, 1, 15, 0
        )

    def test_23_31_geht_zum_naechsten_tag(self):
        assert naechster_halbstunden_slot(dt.datetime(2026, 6, 1, 23, 31)) == dt.datetime(
            2026, 6, 2, 0, 0
        )


class TestStartzeitpunkt:
    def test_ab_morgen_ignoriert_uhrzeit(self):
        cfg = AppConfig.default()
        cfg.planung_ab_morgen = True
        jetzt = dt.datetime(2026, 6, 1, 14, 37, 22)
        ergebnis = berechne_startzeitpunkt(cfg, jetzt=jetzt)
        assert ergebnis == dt.datetime(2026, 6, 2, 0, 0)

    def test_ab_heute_nimmt_naechste_halbe_stunde(self):
        cfg = AppConfig.default()
        cfg.planung_ab_morgen = False
        jetzt = dt.datetime(2026, 6, 1, 14, 12)
        ergebnis = berechne_startzeitpunkt(cfg, jetzt=jetzt)
        assert ergebnis == dt.datetime(2026, 6, 1, 14, 30)


class TestPlanerStartetNichtInVergangenheit:
    """Bug-Regression: erster Sync nachmittags hat rueckwirkend ab 8 Uhr geplant.

    Loesung: start_datum kann mitten in einem Slot liegen und schneidet ihn an.
    """

    def test_start_mitten_im_slot_schneidet_ab(self):
        # Mittwoch hat Slot 8-12 und 13-15
        cfg = AppConfig.default()
        # Start: Mittwoch 11:00 (mitten im ersten Slot)
        start = dt.datetime(2026, 6, 3, 11, 0)
        # 4 Auftraege je 0.5h
        auftraege = [make_auftrag(i, dauer=0.5) for i in range(1, 5)]
        geplant, _ = plane_auftraege(auftraege, cfg, start_datum=start)

        # Erster Termin darf nicht vor 11:00 starten
        assert geplant[0].start >= start
        # Die ersten beiden landen im Slot 11:00-12:00
        assert geplant[0].start == dt.datetime(2026, 6, 3, 11, 0)
        assert geplant[1].start == dt.datetime(2026, 6, 3, 11, 30)
        # Dann Mittagspause - naechster Termin ab 13:00
        assert geplant[2].start == dt.datetime(2026, 6, 3, 13, 0)

    def test_vorbei_an_allen_slots_geht_naechster_tag(self):
        # Mittwoch 16:00, alle Slots heute (8-12, 13-15) vorbei
        cfg = AppConfig.default()
        start = dt.datetime(2026, 6, 3, 16, 0)
        auftraege = [make_auftrag(1, dauer=1.0)]
        geplant, _ = plane_auftraege(auftraege, cfg, start_datum=start)

        # Donnerstag ist Neben-Tag (9-11)
        assert geplant[0].start == dt.datetime(2026, 6, 4, 9, 0)

    def test_start_in_mittagspause_geht_zum_nachmittag(self):
        # Mittwoch 12:30 - in der Mittagspause
        cfg = AppConfig.default()
        start = dt.datetime(2026, 6, 3, 12, 30)
        auftraege = [make_auftrag(1, dauer=1.0)]
        geplant, _ = plane_auftraege(auftraege, cfg, start_datum=start)

        assert geplant[0].start == dt.datetime(2026, 6, 3, 13, 0)


class TestBackfill:
    """Tests fuer das Backfill-Feature: kleinere Auftraege fuellen Reste."""

    def test_kleiner_auftrag_fuellt_reste(self, cfg_default, montag):
        # Mo 9-11 = 2h Slot. Reihenfolge:
        # #3 (1.5h), #2 (1h), #1 (0.5h)
        # Strikte FIFO: #3 nimmt 9-10:30, #2 passt nicht (nur 30 Min Rest),
        # also: #1 (0.5h) wird vorgezogen und fuellt 10:30-11:00. #2 kommt Di.
        auftraege = [
            make_auftrag(3, dauer=1.5),
            make_auftrag(2, dauer=1.0),
            make_auftrag(1, dauer=0.5),
        ]
        geplant, ungeplant = plane_auftraege(auftraege, cfg_default, start_datum=montag)

        mo_termine = [t for t in geplant if t.start.date() == montag.date()]
        assert len(mo_termine) == 2
        assert mo_termine[0].auftrag.nummer == 3
        assert mo_termine[0].start.hour == 9
        # #1 wurde vorgezogen, weil #2 nicht in 30-Min-Rest passt
        assert mo_termine[1].auftrag.nummer == 1
        assert mo_termine[1].start == dt.datetime(2026, 6, 1, 10, 30)
        # #2 ist erst am Dienstag
        di_termine = [t for t in geplant if t.start.date() != montag.date()]
        assert di_termine[0].auftrag.nummer == 2

    def test_keine_aenderung_wenn_alle_passen(self, cfg_default, montag):
        """Wenn die natuerliche Reihenfolge passt, wird nichts umsortiert."""
        auftraege = [make_auftrag(3, dauer=1.0), make_auftrag(2, dauer=1.0)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)
        # Mo 9-11: #3 dann #2
        assert geplant[0].auftrag.nummer == 3
        assert geplant[1].auftrag.nummer == 2

    def test_kein_passender_auftrag_slot_bleibt_teilweise_leer(self, cfg_default, montag):
        """Wenn KEIN noch offener Auftrag in den Rest passt, bleibt der Rest leer."""
        # Mo 9-11 = 2h Slot. Auftrag #3: 1.5h. Auftrag #2: 1h.
        # #3 nimmt 9-10:30, #2 (1h) passt nicht in 30 Min Rest - kein kleinerer
        # da, also bleibt 30 Min frei. #2 kommt am Dienstag.
        auftraege = [make_auftrag(3, dauer=1.5), make_auftrag(2, dauer=1.0)]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)

        mo_termine = [t for t in geplant if t.start.date() == montag.date()]
        assert len(mo_termine) == 1
        assert mo_termine[0].auftrag.nummer == 3
        # #2 wandert auf Dienstag
        di_termine = [t for t in geplant if t.start.date() != montag.date()]
        assert di_termine[0].auftrag.nummer == 2

    def test_reihenfolge_innerhalb_passender_kandidaten(self, cfg_default, montag):
        """Bei mehreren passenden Kandidaten gewinnt der mit niedrigerem Index
        (= hoechste Auftragsnummer = neuester)."""
        # Mo 9-11 = 2h. Reihenfolge:
        # #5 (1.5h), #4 (0.5h), #3 (0.5h)
        # #5 nimmt 9-10:30. Rest 30 Min. Beide #4 und #3 passen.
        # #4 hat den kleineren Index -> wird gewaehlt.
        auftraege = [
            make_auftrag(5, dauer=1.5),
            make_auftrag(4, dauer=0.5),
            make_auftrag(3, dauer=0.5),
        ]
        geplant, _ = plane_auftraege(auftraege, cfg_default, start_datum=montag)

        mo_termine = [t for t in geplant if t.start.date() == montag.date()]
        assert mo_termine[1].auftrag.nummer == 4  # nicht 3


class TestUngeplantBehaeltOriginalReihenfolge:
    def test_ungeplante_in_original_reihenfolge(self, montag):
        # Nur Mo 9-10 Slot (1h), max_planungstage = 1 -> nur ein Tag
        cfg = AppConfig(days={i: DayConfig([]) for i in range(7)})
        cfg.days[0] = DayConfig([(9, 10)])
        cfg.max_planungstage = 1

        # Reihenfolge: 5 (2h), 4 (0.5h), 3 (1h), 2 (0.5h), 1 (1h)
        # Slot ist 1h. 5 passt nicht (2h). 4 wird vorgezogen (0.5h passt).
        # Rest 30 Min: 3 (1h) passt nicht, 2 (0.5h) passt -> 2.
        # Slot voll. Rest: 5, 3, 1 ungeplant.
        auftraege = [
            make_auftrag(5, dauer=2.0),
            make_auftrag(4, dauer=0.5),
            make_auftrag(3, dauer=1.0),
            make_auftrag(2, dauer=0.5),
            make_auftrag(1, dauer=1.0),
        ]
        geplant, ungeplant = plane_auftraege(auftraege, cfg, start_datum=montag)

        assert len(geplant) == 2
        assert [t.auftrag.nummer for t in geplant] == [4, 2]
        # Ungeplant in ORIGINAL-Reihenfolge (nicht: groesste zuerst)
        assert [a.nummer for a in ungeplant] == [5, 3, 1]
