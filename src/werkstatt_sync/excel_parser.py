"""Excel-Parser fuer Easywerkstatt Export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class Auftrag:
    nummer: int
    kunde: str
    dauer_stunden: float
    kunden_nr: str = ""
    betrag: str = ""
    notiz_original: str = ""  # Was im Notizfeld stand (zum Debuggen)
    hat_zeit_notiz: bool = False  # False -> Default-Dauer wurde verwendet


def excel_einlesen(pfad: str | Path, default_dauer_stunden: float = 1.0) -> list[Auftrag]:
    """Liest Easywerkstatt-Excel und gibt Auftragsliste zurueck.

    Sortiert nach Auftragsnummer absteigend (hoechste = neueste zuerst).
    Auftraege ohne Zeit-Notiz bekommen default_dauer_stunden.

    Wirft FileNotFoundError oder ValueError bei Problemen.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        raise FileNotFoundError(f"Excel-Datei nicht gefunden: {pfad}")

    try:
        df = pd.read_excel(pfad, header=1)
    except Exception as e:
        raise ValueError(f"Excel konnte nicht gelesen werden: {e}") from e

    if "Auftragsnummer" not in df.columns:
        raise ValueError(
            "Spalte 'Auftragsnummer' nicht gefunden. Ist das wirklich ein Easywerkstatt-Export?"
        )

    df = df[df["Auftragsnummer"].notna()].copy()
    df["Auftragsnummer"] = df["Auftragsnummer"].astype(int)
    df = df.sort_values("Auftragsnummer", ascending=False)

    auftraege = []
    for _, row in df.iterrows():
        notiz = row.get("Notizen")
        notiz_str = "" if pd.isna(notiz) else str(notiz)

        dauer, hat_zeit = _parse_dauer(notiz, default_dauer_stunden)

        kunde = row.get("Kundenname")
        if pd.isna(kunde) or not str(kunde).strip():
            kunde = "(kein Kundenname)"

        kunden_nr = row.get("KundenNr.")
        kunden_nr_str = "" if pd.isna(kunden_nr) else _format_zahl(kunden_nr)

        betrag = row.get("inkl. Steuer")
        betrag_str = "" if pd.isna(betrag) else _format_zahl(betrag, decimals=2)

        auftraege.append(
            Auftrag(
                nummer=int(row["Auftragsnummer"]),
                kunde=str(kunde).strip(),
                dauer_stunden=dauer,
                kunden_nr=kunden_nr_str,
                betrag=betrag_str,
                notiz_original=notiz_str,
                hat_zeit_notiz=hat_zeit,
            )
        )
    return auftraege


def _parse_dauer(notiz, default: float) -> tuple[float, bool]:
    """Versucht aus dem Notizfeld eine Stundenzahl zu lesen.

    Returns (dauer_stunden, hat_zeit_notiz).
    """
    if notiz is None or pd.isna(notiz):
        return default, False
    try:
        dauer = float(str(notiz).replace(",", "."))
        if dauer <= 0:
            return default, False
        return dauer, True
    except (ValueError, TypeError):
        return default, False


def _format_zahl(v, decimals: int = 0) -> str:
    """Formatiert numerischen Wert ohne stoerende '.0' am Ende."""
    try:
        f = float(v)
        if decimals == 0 and f.is_integer():
            return str(int(f))
        return f"{f:.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)
