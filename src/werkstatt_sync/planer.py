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


def naechster_halbstunden_slot(jetzt: dt.datetime) -> dt.datetime:
    """Rundet einen Zeitpunkt auf die naechste halbe oder volle Stunde hoch.

    14:00:00 -> 14:00 (schon Slot-Anfang, keine Aenderung)
    14:00:01 -> 14:30
    14:14    -> 14:30
    14:30    -> 14:30 (schon Slot-Anfang)
    14:31    -> 15:00
    23:31    -> nächster Tag 00:00
    """
    minute = jetzt.minute
    if jetzt.second == 0 and jetzt.microsecond == 0 and minute in (0, 30):
        return jetzt
    basis = jetzt.replace(second=0, microsecond=0)
    if minute < 30:
        return basis.replace(minute=30)
    # 31-59: hoch zur naechsten vollen Stunde
    return (basis + dt.timedelta(hours=1)).replace(minute=0)


def berechne_startzeitpunkt(cfg: AppConfig, jetzt: dt.datetime | None = None) -> dt.datetime:
    """Berechnet, ab welchem Zeitpunkt geplant werden darf.

    - cfg.planung_ab_morgen=True:  morgen, 00:00
    - cfg.planung_ab_morgen=False: heute, ab naechster halber oder voller Stunde

    Wird von plane_auftraege() UND vom Orchestrator zum Loeschen alter Termine
    genutzt - so ist garantiert, dass Loesch-Fenster und Plan-Fenster synchron
    sind und keine Duplikate entstehen.
    """
    if jetzt is None:
        jetzt = dt.datetime.now()
    if cfg.planung_ab_morgen:
        morgen = jetzt.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)
        return morgen
    return naechster_halbstunden_slot(jetzt)


def plane_auftraege(
    auftraege: list[Auftrag],
    cfg: AppConfig,
    start_datum: dt.datetime | None = None,
) -> tuple[list[Termin], list[Auftrag]]:
    """Verteilt Auftraege auf Slots gemaess Wochenplan.

    Strategie: FIFO mit Backfill.

    1. Die Auftrags-Reihenfolge wird grundsaetzlich respektiert (hoechste Nummer
       = neueste = zuerst). Der naechste passende Auftrag wird in den naechsten
       freien Platz gelegt.
    2. WENN der naechste Auftrag NICHT in die Restzeit eines Slots passt, sucht
       der Planer in den nachfolgenden Auftraegen einen, der passt (Backfill).
       Erster passender gewinnt - das bleibt am naechsten an der Reihenfolge.
    3. Aufgeteilt wird nie - ein Auftrag wandert immer als Ganzes in einen Slot.

    Beispiel: Restzeit 30 Min. Naechster Auftrag #192 (1h) passt nicht. Statt den
    Slot zu verschwenden, wird ein spaeterer 30-Min-Auftrag vorgezogen. Der
    1h-Auftrag bleibt fuer den naechsten Slot reserviert.

    Wenn start_datum mitten in einem Slot liegt (z.B. 11:00 bei Slot 8-12), wird
    der Slot effektiv ab start_datum begonnen. Slots komplett in der Vergangenheit
    werden uebersprungen.

    Returns: (geplante_termine, ungeplante_auftraege - in Original-Reihenfolge)
    """
    if start_datum is None:
        start_datum = berechne_startzeitpunkt(cfg)

    geplant: list[Termin] = []
    # Wir nutzen einen Index-basierten "remaining"-Ansatz: jeder Auftrag hat
    # einen festen Index, und wir markieren "fertig geplant" durch eine
    # parallele bool-Liste. So bleibt die Original-Reihenfolge der Liste
    # erhalten fuer ungeplant-Output.
    erledigt = [False] * len(auftraege)

    for tag_offset in range(cfg.max_planungstage):
        if all(erledigt):
            break
        tag = start_datum + dt.timedelta(days=tag_offset)
        for slot_start, slot_ende in tages_slots(tag, cfg):
            if slot_ende <= start_datum:
                continue
            if slot_start < start_datum:
                slot_start = start_datum
            cursor = slot_start
            # In dieser Schleife fuellen wir den Slot von vorne nach hinten.
            # Bei jeder Iteration: nimm den ersten noch nicht erledigten
            # Auftrag, der in (slot_ende - cursor) passt.
            while True:
                rest = slot_ende - cursor
                gewaehlt_idx = _waehle_naechsten_auftrag(auftraege, erledigt, rest)
                if gewaehlt_idx is None:
                    break  # nichts passt mehr in diesen Slot
                a = auftraege[gewaehlt_idx]
                dauer = dt.timedelta(hours=a.dauer_stunden)
                geplant.append(Termin(auftrag=a, start=cursor, ende=cursor + dauer))
                cursor += dauer
                erledigt[gewaehlt_idx] = True

    ungeplant = [a for a, fertig in zip(auftraege, erledigt, strict=True) if not fertig]
    return geplant, ungeplant


def _waehle_naechsten_auftrag(
    auftraege: list[Auftrag], erledigt: list[bool], max_dauer: dt.timedelta
) -> int | None:
    """Sucht den ersten nicht-erledigten Auftrag, der in max_dauer passt.

    "Erster" = niedrigster Index = hoechste Auftragsnummer (Liste ist
    absteigend sortiert). Damit bleibt die Reihenfolge so weit wie moeglich
    erhalten - es wird nur uebersprungen, wenn der naechste Auftrag schlicht
    nicht mehr passt.
    """
    for idx, (a, fertig) in enumerate(zip(auftraege, erledigt, strict=True)):
        if fertig:
            continue
        if dt.timedelta(hours=a.dauer_stunden) <= max_dauer:
            return idx
    return None
