"""Tests fuer excel_parser.py mit der echten Beispiel-Excel."""

from pathlib import Path

import pandas as pd
import pytest

from werkstatt_sync.excel_parser import excel_einlesen

FIXTURES = Path(__file__).parent / "fixtures"


def make_test_excel(tmp_path: Path, rows: list[dict]) -> Path:
    """Baut eine Easywerkstatt-aehnliche Excel-Datei zum Testen.

    Easywerkstatt schreibt 'Rechnungen' in A1 und die echten Header in Zeile 2,
    deshalb wird das hier nachgebaut.
    """
    pfad = tmp_path / "test.xlsx"
    # Erste Zeile = "Rechnungen", dann Header in Zeile 2
    columns = [
        "Nummer",
        "Auftragsnummer",
        "Status",
        "Rechnungsdatum",
        "Kundenname",
        "KundenNr.",
        "Fahrzeug",
        "Kennzeichen",
        "inkl. Steuer",
        "Notizen",
    ]

    # Build DataFrame: erste row = header repeat, weil wir header=1 lesen
    data_rows = []
    for row in rows:
        data_rows.append([row.get(col, None) for col in columns])

    df = pd.DataFrame(data_rows, columns=columns)
    # Zeile 0 ist "Rechnungen" + leere Spalten, Header steht in Zeile 1
    with pd.ExcelWriter(pfad, engine="openpyxl") as writer:
        # Erste Zeile mit 'Rechnungen', dann Header, dann Daten
        header_df = pd.DataFrame([["Rechnungen"] + [None] * (len(columns) - 1)])
        header_df.to_excel(writer, index=False, header=False, startrow=0)
        df.to_excel(writer, index=False, startrow=1)
    return pfad


class TestExcelEinlesen:
    def test_fehlende_datei(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            excel_einlesen(tmp_path / "doesnt_exist.xlsx")

    def test_einfache_excel(self, tmp_path):
        pfad = make_test_excel(
            tmp_path,
            [
                {"Auftragsnummer": 100, "Kundenname": "Müller", "Notizen": 1.5},
                {"Auftragsnummer": 101, "Kundenname": "Schmidt", "Notizen": 2},
            ],
        )
        auftraege = excel_einlesen(pfad)
        assert len(auftraege) == 2
        # Sortiert absteigend nach Auftragsnummer
        assert auftraege[0].nummer == 101
        assert auftraege[1].nummer == 100

    def test_dauer_komma_dezimal(self, tmp_path):
        """Easywerkstatt kann '0,5' statt '0.5' enthalten."""
        pfad = make_test_excel(
            tmp_path,
            [
                {"Auftragsnummer": 1, "Kundenname": "Test", "Notizen": "0,5"},
            ],
        )
        auftraege = excel_einlesen(pfad)
        assert auftraege[0].dauer_stunden == 0.5
        assert auftraege[0].hat_zeit_notiz is True

    def test_dauer_default_bei_fehlender_notiz(self, tmp_path):
        pfad = make_test_excel(
            tmp_path,
            [
                {"Auftragsnummer": 1, "Kundenname": "Test"},  # keine Notiz
            ],
        )
        auftraege = excel_einlesen(pfad, default_dauer_stunden=2.5)
        assert auftraege[0].dauer_stunden == 2.5
        assert auftraege[0].hat_zeit_notiz is False

    def test_dauer_default_bei_unparsbar(self, tmp_path):
        pfad = make_test_excel(
            tmp_path,
            [
                {"Auftragsnummer": 1, "Kundenname": "Test", "Notizen": "ungueltig"},
            ],
        )
        auftraege = excel_einlesen(pfad, default_dauer_stunden=1.0)
        assert auftraege[0].dauer_stunden == 1.0
        assert auftraege[0].hat_zeit_notiz is False

    def test_dauer_negativ_wird_default(self, tmp_path):
        pfad = make_test_excel(
            tmp_path,
            [
                {"Auftragsnummer": 1, "Kundenname": "Test", "Notizen": -1},
            ],
        )
        auftraege = excel_einlesen(pfad, default_dauer_stunden=1.0)
        assert auftraege[0].dauer_stunden == 1.0
        assert auftraege[0].hat_zeit_notiz is False

    def test_fehlender_kundenname(self, tmp_path):
        pfad = make_test_excel(
            tmp_path,
            [
                {"Auftragsnummer": 1, "Notizen": 1.0},
            ],
        )
        auftraege = excel_einlesen(pfad)
        assert "kein Kundenname" in auftraege[0].kunde

    def test_zeilen_ohne_auftragsnummer_uebersprungen(self, tmp_path):
        """Leere Zeilen oder Summen-Zeilen ohne Auftragsnummer."""
        pfad = make_test_excel(
            tmp_path,
            [
                {"Auftragsnummer": 100, "Kundenname": "A", "Notizen": 1},
                {"Kundenname": "leer", "Notizen": 1},  # keine Nummer
                {"Auftragsnummer": 101, "Kundenname": "B", "Notizen": 1},
            ],
        )
        auftraege = excel_einlesen(pfad)
        assert len(auftraege) == 2
        assert {a.nummer for a in auftraege} == {100, 101}

    def test_falsche_spalte_wirft_value_error(self, tmp_path):
        """Wenn 'Auftragsnummer' nicht da ist, klare Fehlermeldung."""
        pfad = tmp_path / "wrong.xlsx"
        pd.DataFrame({"FalscheSpalte": [1, 2, 3]}).to_excel(pfad, index=False)
        with pytest.raises(ValueError, match="Auftragsnummer"):
            excel_einlesen(pfad)


# Optionaler Test gegen die echte Beispiel-Excel - laeuft nur lokal
@pytest.mark.skipif(
    not (FIXTURES / "invoices.xlsx").exists(), reason="fixtures/invoices.xlsx nicht vorhanden"
)
class TestEchteFixture:
    """Tests gegen die echte Fixture - bleiben absichtlich datenagnostisch.

    Konkrete Werte (Kundennamen, welche Auftraege Zeit-Notizen haben) duerfen
    sich in der Fixture aendern, ohne dass die Tests brechen. Wir testen das
    Verhalten des Parsers, nicht den Inhalt der Datei.
    """

    def test_fixture_laesst_sich_einlesen(self):
        """Die Fixture-Datei wird ohne Fehler geparst und liefert Auftraege."""
        auftraege = excel_einlesen(FIXTURES / "invoices.xlsx")
        assert len(auftraege) > 0

    def test_sortierung_absteigend_nach_nummer(self):
        auftraege = excel_einlesen(FIXTURES / "invoices.xlsx")
        nummern = [a.nummer for a in auftraege]
        assert nummern == sorted(nummern, reverse=True)

    def test_alle_auftraege_haben_gueltige_dauer(self):
        """Egal ob Zeit-Notiz vorhanden oder nicht: jede Dauer ist positiv."""
        auftraege = excel_einlesen(FIXTURES / "invoices.xlsx", default_dauer_stunden=1.0)
        for a in auftraege:
            assert a.dauer_stunden > 0, f"Auftrag #{a.nummer} hat keine positive Dauer"

    def test_default_dauer_wird_respektiert(self):
        """Auftraege ohne Zeit-Notiz bekommen die default_dauer."""
        auftraege = excel_einlesen(FIXTURES / "invoices.xlsx", default_dauer_stunden=2.5)
        ohne_notiz = [a for a in auftraege if not a.hat_zeit_notiz]
        for a in ohne_notiz:
            assert a.dauer_stunden == 2.5
