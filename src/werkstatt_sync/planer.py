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
    belegte_zeiten: list[tuple[dt.datetime, dt.datetime]] | None = None,
) -> tuple[list[Termin], list[Auftrag]]:
    """Verteilt Auftraege auf Slots gemaess Wochenplan.

    Strategie: FIFO mit Backfill. Auftraege mit Prioritaet (P1-P4) werden
    vor normalen Auftraegen eingeplant (P1 vor P2 vor P3 vor P4 vor normal).
    Innerhalb einer Prioritaetsstufe bleibt die Auftrags-Reihenfolge erhalten.

    belegte_zeiten: Liste von (start, ende) aus anderen Kalendern. Slots die
    sich mit einem belegten Zeitraum ueberschneiden werden uebersprungen.

    Returns: (geplante_termine, ungeplante_auftraege - in Original-Reihenfolge)
    """
    if start_datum is None:
        start_datum = berechne_startzeitpunkt(cfg)
    if belegte_zeiten is None:
        belegte_zeiten = []

    # Prioritaets-Sortierung: P1 zuerst, dann P2, P3, P4, dann normal (0).
    # Stabile sort: Reihenfolge innerhalb gleicher Prio bleibt erhalten.
    planungs_reihenfolge = sorted(
        range(len(auftraege)),
        key=lambda i: auftraege[i].prioritaet if auftraege[i].prioritaet > 0 else 999,
    )

    geplant: list[Termin] = []
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
            while True:
                # Cursor vorruecken falls aktueller Zeitpunkt durch externen
                # Termin belegt ist.
                cursor = _naechster_freier_zeitpunkt(cursor, slot_ende, belegte_zeiten)
                if cursor >= slot_ende:
                    break
                rest = _freie_dauer_bis(cursor, slot_ende, belegte_zeiten)
                gewaehlt_idx = _waehle_naechsten_auftrag(
                    auftraege, erledigt, rest, planungs_reihenfolge
                )
                if gewaehlt_idx is None:
                    break
                a = auftraege[gewaehlt_idx]
                dauer = dt.timedelta(hours=a.dauer_stunden)
                geplant.append(Termin(auftrag=a, start=cursor, ende=cursor + dauer))
                cursor += dauer
                erledigt[gewaehlt_idx] = True

    ungeplant = [a for a, fertig in zip(auftraege, erledigt, strict=True) if not fertig]
    return geplant, ungeplant


def _waehle_naechsten_auftrag(
    auftraege: list[Auftrag],
    erledigt: list[bool],
    max_dauer: dt.timedelta,
    reihenfolge: list[int],
) -> int | None:
    """Sucht den ersten nicht-erledigten Auftrag (gemaess reihenfolge), der in max_dauer passt."""
    for idx in reihenfolge:
        if erledigt[idx]:
            continue
        if dt.timedelta(hours=auftraege[idx].dauer_stunden) <= max_dauer:
            return idx
    return None


def _naechster_freier_zeitpunkt(
    ab: dt.datetime,
    bis: dt.datetime,
    belegte_zeiten: list[tuple[dt.datetime, dt.datetime]],
) -> dt.datetime:
    """Schiebt 'ab' hinter alle belegten Zeitraeume, die ab ueberschneiden."""
    changed = True
    while changed:
        changed = False
        for belegt_start, belegt_ende in belegte_zeiten:
            if belegt_start <= ab and belegt_ende > ab:
                ab = belegt_ende
                changed = True
    return ab


def _freie_dauer_bis(
    ab: dt.datetime,
    bis: dt.datetime,
    belegte_zeiten: list[tuple[dt.datetime, dt.datetime]],
) -> dt.timedelta:
    """Gibt die Dauer vom Zeitpunkt 'ab' bis zum naechsten belegten Zeitraum (oder 'bis') zurueck."""
    naechste_blockierung = bis
    for belegt_start, _belegt_ende in belegte_zeiten:
        if belegt_start > ab and belegt_start < naechste_blockierung:
            naechste_blockierung = belegt_start
    return naechste_blockierung - ab
