"""Orchestrator: bindet Excel + Planer + Kalender zusammen."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .excel_parser import excel_einlesen
from .kalender_sync import (
    alte_termine_loeschen,
    credentials_vorhanden,
    get_service,
    hole_belegte_zeiten,
    termin_anlegen,
)
from .planer import berechne_startzeitpunkt, plane_auftraege


@dataclass
class SyncErgebnis:
    auftraege_gesamt: int
    auftraege_ohne_zeit: int
    termine_geloescht: int
    termine_erstellt: int
    ungeplant: int
    fehler: str | None = None


def fuehre_sync_durch(
    excel_pfad: str | Path,
    cfg: AppConfig,
    log: Callable[[str], None] = print,
) -> SyncErgebnis:
    """Kompletter Sync-Workflow.

    log: Callback fuer Statusmeldungen (in der GUI ans Log-Fenster gebunden).
    """
    if not credentials_vorhanden():
        return SyncErgebnis(
            0,
            0,
            0,
            0,
            0,
            fehler="Keine Google-Credentials installiert. Bitte in den Einstellungen einrichten.",
        )

    log(f"Lese Excel: {excel_pfad}")
    try:
        auftraege = excel_einlesen(excel_pfad, cfg.default_dauer_stunden)
    except (FileNotFoundError, ValueError) as e:
        return SyncErgebnis(0, 0, 0, 0, 0, fehler=str(e))

    ohne_zeit = sum(1 for a in auftraege if not a.hat_zeit_notiz)
    log(
        f"-> {len(auftraege)} Auftraege geladen ({ohne_zeit} ohne Zeit-Notiz, "
        f"nutzen Default {cfg.default_dauer_stunden}h)"
    )

    log("Verbinde mit Google Kalender...")
    try:
        service = get_service()
    except Exception as e:
        return SyncErgebnis(
            len(auftraege), ohne_zeit, 0, 0, 0, fehler=f"Google-Login fehlgeschlagen: {e}"
        )

    # Startzeitpunkt EINMAL berechnen, dann fuer Loeschen UND Planen nutzen.
    # Wenn diese auseinander laufen, entstehen Duplikate (siehe AGENTS.md).
    start_datum = berechne_startzeitpunkt(cfg)
    log(f"Planung startet: {start_datum.strftime('%a %d.%m.%Y %H:%M')}")

    log("Loesche alte automatische Termine im Planungs-Zeitraum...")
    try:
        geloescht = alte_termine_loeschen(service, cfg, ab_zeitpunkt=start_datum, log=log)
    except Exception as e:
        return SyncErgebnis(
            len(auftraege), ohne_zeit, 0, 0, 0, fehler=f"Loeschen fehlgeschlagen: {e}"
        )
    log(f"-> {geloescht} alte Termine entfernt")

    log("Lese belegte Zeiten aus Google Kalender...")
    ende_datum = start_datum + dt.timedelta(days=cfg.max_planungstage)
    try:
        belegte_zeiten = hole_belegte_zeiten(service, start_datum, ende_datum, cfg)
        kalender_hinweis = "allen Kalendern" if cfg.alle_kalender_pruefen else cfg.kalender_id
        log(f"-> {len(belegte_zeiten)} belegte Zeitraeume aus {kalender_hinweis} gefunden")
    except Exception as e:
        log(f"WARNUNG: Belegte Zeiten konnten nicht gelesen werden: {e}")
        belegte_zeiten = []

    log("Plane Auftraege...")
    geplant, ungeplant = plane_auftraege(
        auftraege, cfg, start_datum=start_datum, belegte_zeiten=belegte_zeiten
    )
    if ungeplant:
        log(
            f"WARNUNG: {len(ungeplant)} Auftraege konnten in {cfg.max_planungstage} "
            f"Tagen nicht geplant werden."
        )

    log(f"Erstelle {len(geplant)} Termine...")
    erstellt = 0
    for t in geplant:
        try:
            termin_anlegen(service, t, cfg)
            erstellt += 1
            log(
                f"  + {t.start.strftime('%a %d.%m %H:%M')}  "
                f"#{t.auftrag.nummer}  {t.auftrag.kunde}  ({t.auftrag.dauer_stunden}h)"
            )
        except Exception as e:
            log(f"  ! Fehler bei #{t.auftrag.nummer}: {e}")

    log("Fertig.")
    return SyncErgebnis(
        auftraege_gesamt=len(auftraege),
        auftraege_ohne_zeit=ohne_zeit,
        termine_geloescht=geloescht,
        termine_erstellt=erstellt,
        ungeplant=len(ungeplant),
    )
