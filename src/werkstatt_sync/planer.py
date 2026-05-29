"""Planer: verteilt Auftraege auf Zeit-Slots gemaess Wochenplan."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .config import AppConfig
from .excel_parser import Auftrag


@dataclass
class Termin:
    auftrag: Auftrag
    start: dt.datetime
    ende: dt.datetime


def tages_slots(datum: dt.datetime, cfg: AppConfig) -> list[tuple[dt.datetime, dt.datetime]]:
    """Gibt Zeit-Slots fuer ein konkretes Datum zurueck.

    Schaut den Wochentag in cfg.days nach und macht aus den (start_h, ende_h)
    Tupeln konkrete datetime-Bereiche fuer diesen Tag.
    """
    day_cfg = cfg.days.get(datum.weekday())
    if not day_cfg or not day_cfg.slots:
        return []
    base = datum.replace(hour=0, minute=0, second=0, microsecond=0)
    return [(base.replace(hour=start), base.replace(hour=ende)) for start, ende in day_cfg.slots]


def plane_auftraege(
    auftraege: list[Auftrag],
    cfg: AppConfig,
    start_datum: dt.datetime | None = None,
) -> tuple[list[Termin], list[Auftrag]]:
    """Verteilt Auftraege auf Slots.

    Reihenfolge: wie in der Liste (excel_einlesen sortiert nach Auftragsnummer
    absteigend - hoechste/neueste zuerst).

    Wenn ein Auftrag nicht mehr in den aktuellen Slot passt, wandert er komplett
    in den naechsten Slot (kein Aufteilen).

    Returns: (geplante_termine, ungeplante_auftraege)
    """
    if start_datum is None:
        start_datum = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if cfg.planung_ab_morgen:
            start_datum += dt.timedelta(days=1)

    geplant: list[Termin] = []
    auftrag_idx = 0

    for tag_offset in range(cfg.max_planungstage):
        if auftrag_idx >= len(auftraege):
            break
        tag = start_datum + dt.timedelta(days=tag_offset)
        for slot_start, slot_ende in tages_slots(tag, cfg):
            cursor = slot_start
            while auftrag_idx < len(auftraege):
                a = auftraege[auftrag_idx]
                dauer = dt.timedelta(hours=a.dauer_stunden)
                if cursor + dauer <= slot_ende:
                    geplant.append(Termin(auftrag=a, start=cursor, ende=cursor + dauer))
                    cursor += dauer
                    auftrag_idx += 1
                else:
                    break  # passt nicht -> naechster Slot

    ungeplant = auftraege[auftrag_idx:]
    return geplant, ungeplant
