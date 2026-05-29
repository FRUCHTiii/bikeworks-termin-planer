"""Excel-Parser fuer Easywerkstatt Export."""

from __future__ import annotations

import io
import re
import zipfile
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

    Sortiert nach Auftragsnummer aufsteigend (niedrigste = aelteste zuerst).
    Auftraege ohne Zeit-Notiz bekommen default_dauer_stunden.

    Wirft FileNotFoundError oder ValueError bei Problemen.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        raise FileNotFoundError(f"Excel-Datei nicht gefunden: {pfad}")

    df = _read_excel_robust(pfad)

    if "Auftragsnummer" not in df.columns:
        raise ValueError(
            "Spalte 'Auftragsnummer' nicht gefunden. Ist das wirklich ein Easywerkstatt-Export?"
        )

    df = df[df["Auftragsnummer"].notna()].copy()
    df["Auftragsnummer"] = df["Auftragsnummer"].astype(int)
    df = df.sort_values("Auftragsnummer", ascending=True)

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


def _read_excel_robust(pfad: Path) -> pd.DataFrame:
    """Liest die Excel-Datei und repariert bei Bedarf kaputte Style-Definitionen.

    Easywerkstatt erzeugt teilweise xlsx-Dateien mit ungueltigen Farb-Werten
    (z.B. rgb="0xffeca1" statt rgb="FFFFECA1"). openpyxl bricht darauf ab.
    Wenn der normale Read fehlschlaegt, repariert diese Funktion die styles.xml
    in einem In-Memory-Buffer und liest dann erneut.
    """
    try:
        return pd.read_excel(pfad, header=1)
    except ValueError as e:
        # Spezifischer Fehler: kaputte stylesheet.xml
        if "stylesheet" not in str(e).lower() and "argb" not in str(e).lower():
            raise ValueError(f"Excel konnte nicht gelesen werden: {e}") from e

    # Fallback: Datei in Memory reparieren
    try:
        repaired = _repariere_styles_xml(pfad)
        return pd.read_excel(io.BytesIO(repaired), header=1)
    except Exception as e:
        raise ValueError(
            f"Excel konnte auch mit Reparatur-Versuch nicht gelesen werden: {e}"
        ) from e


def _repariere_styles_xml(pfad: Path) -> bytes:
    """Repariert kaputte ARGB-Farbwerte in der styles.xml einer xlsx-Datei.

    Easywerkstatt-Bugs die hier behoben werden:
    - rgb="0xffeca1" -> rgb="FFFFECA1" (0x-Prefix entfernen, FF-Alpha vorne)
    - rgb="ffeca1"   -> rgb="FFFFECA1" (Alpha-Kanal fehlt)
    """

    def fix_color(match: re.Match) -> str:
        wert = match.group(1)
        if wert.lower().startswith("0x"):
            wert = wert[2:]
        if len(wert) == 6:
            wert = "FF" + wert
        elif len(wert) < 8:
            wert = wert.upper().zfill(8)
        return f'rgb="{wert.upper()}"'

    with zipfile.ZipFile(pfad, "r") as zin:
        out_buffer = io.BytesIO()
        with zipfile.ZipFile(out_buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item == "xl/styles.xml":
                    text = data.decode("utf-8")
                    text = re.sub(r'rgb="([^"]*)"', fix_color, text)
                    data = text.encode("utf-8")
                zout.writestr(item, data)
        return out_buffer.getvalue()


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
