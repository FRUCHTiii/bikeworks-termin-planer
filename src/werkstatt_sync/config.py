"""Konfiguration: Pfade, Defaults, JSON-Persistenz."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def app_data_dir() -> Path:
    """%APPDATA%\\WerkstattSync auf Windows, ~/.config/werkstatt-sync sonst."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / "WerkstattSync"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH = app_data_dir() / "config.json"
CREDENTIALS_PATH = app_data_dir() / "credentials.json"
TOKEN_PATH = app_data_dir() / "token.json"
LOG_PATH = app_data_dir() / "werkstatt_sync.log"


@dataclass
class DayConfig:
    """Arbeitszeiten fuer einen Wochentag.

    slots: Liste von (start_h, end_h) Tupeln. Leere Liste = freier Tag.
    Beispiel: [(9, 12), (13, 15)] = 9-12 und 13-15 Uhr (Mittagspause dazwischen).
    """

    slots: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class AppConfig:
    # Wochentage: 0=Mo, 1=Di, ..., 6=So
    days: dict[int, DayConfig] = field(default_factory=dict)
    default_dauer_stunden: float = 1.0
    kalender_id: str = "primary"
    planung_ab_morgen: bool = True
    max_planungstage: int = 60
    zeitzone: str = "Europe/Berlin"
    termin_tag: str = "[EW-AUTO]"
    letzte_excel_datei: str = ""
    alle_kalender_pruefen: bool = True  # Externe Termine in allen Kalendern beachten

    @classmethod
    def default(cls) -> AppConfig:
        """Werkseinstellungen wie vom Nutzer beschrieben."""
        return cls(
            days={
                0: DayConfig([(9, 11)]),  # Mo
                1: DayConfig([(9, 11)]),  # Di
                2: DayConfig([(8, 12), (13, 15)]),  # Mi
                3: DayConfig([(9, 11)]),  # Do
                4: DayConfig([(8, 12), (13, 15)]),  # Fr
                5: DayConfig([]),  # Sa
                6: DayConfig([]),  # So
            },
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        # Tuples werden in JSON zu Listen, dict-Keys zu Strings - alles ok
        d["days"] = {str(k): {"slots": [list(s) for s in v.slots]} for k, v in self.days.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> AppConfig:
        days_raw = d.get("days", {})
        days = {}
        for k, v in days_raw.items():
            slots = [tuple(s) for s in v.get("slots", [])]
            days[int(k)] = DayConfig(slots)
        return cls(
            days=days,
            default_dauer_stunden=d.get("default_dauer_stunden", 1.0),
            kalender_id=d.get("kalender_id", "primary"),
            planung_ab_morgen=d.get("planung_ab_morgen", True),
            max_planungstage=d.get("max_planungstage", 60),
            zeitzone=d.get("zeitzone", "Europe/Berlin"),
            termin_tag=d.get("termin_tag", "[EW-AUTO]"),
            letzte_excel_datei=d.get("letzte_excel_datei", ""),
            alle_kalender_pruefen=d.get("alle_kalender_pruefen", True),
        )


def load_config() -> AppConfig:
    """Laedt Config aus Datei oder gibt Default zurueck."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return AppConfig.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass  # Bei Fehler -> Default
    return AppConfig.default()


def save_config(cfg: AppConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2, ensure_ascii=False)


def parse_zeitfenster(text: str) -> list[tuple[int, int]]:
    """Parst 'frei' / leeren String / '9-11' / '8-12; 13-15' zu Slot-Liste.

    Akzeptiert: '-', '–', ';', ',' als Trenner. Whitespace egal.
    Wirft ValueError bei ungueltigem Format.
    """
    text = text.strip().lower()
    if not text or text in ("frei", "free", "-", "geschlossen"):
        return []

    # Trenner normalisieren
    text = text.replace("–", "-").replace(",", ";")
    slots = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            raise ValueError(f"Ungueltiges Zeitfenster: '{part}' (erwartet z.B. '9-11')")
        a, b = part.split("-", 1)
        try:
            start = int(a.strip())
            ende = int(b.strip())
        except ValueError as err:
            raise ValueError(f"Ungueltige Zahl in '{part}'") from err
        if not (0 <= start < ende <= 24):
            raise ValueError(f"Ungueltige Zeit in '{part}' (0 <= start < ende <= 24)")
        slots.append((start, ende))
    return slots


def format_zeitfenster(slots: list[tuple[int, int]]) -> str:
    """Umkehrung: Slot-Liste zu 'frei' oder '9-11' oder '8-12; 13-15'."""
    if not slots:
        return "frei"
    return "; ".join(f"{s}-{e}" for s, e in slots)
