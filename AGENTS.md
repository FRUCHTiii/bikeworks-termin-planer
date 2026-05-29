# AGENTS.md

Anleitung fuer KI-Agenten (Claude Code, Cursor, etc.) und menschliche Entwickler,
die an diesem Projekt weiterarbeiten.

---

## Was die App macht (in einem Satz)

Sie liest den Excel-Export aus [Easywerkstatt](https://easywerkstatt.com/), plant
alle offenen Auftraege nach einem konfigurierbaren Wochenplan in Zeit-Slots ein,
und legt diese als Termine in einem Google Kalender an. Bei erneutem Lauf werden
alle eigenen Zukunfts-Termine geloescht und neu erzeugt; manuelle Termine bleiben
unangetastet.

## Projekt-Struktur

```
werkstatt-sync/
├── src/werkstatt_sync/        ← Python-Paket (Source of Truth)
│   ├── config.py              ← AppConfig, Pfade, JSON-Persistenz, Zeitfenster-Parser
│   ├── excel_parser.py        ← Easywerkstatt-Excel → Auftrag-Liste
│   ├── planer.py              ← Auftraege → Termine (rein funktional, ohne I/O)
│   ├── kalender_sync.py       ← Google OAuth + Calendar-API-Aufrufe
│   ├── orchestrator.py        ← bindet Excel + Planer + Kalender zusammen
│   ├── gui.py                 ← Tkinter UI (zwei Tabs)
│   ├── __init__.py            ← Version
│   └── __main__.py            ← python -m werkstatt_sync
├── tests/                     ← pytest, laeuft in CI
├── docs/GOOGLE_SETUP.md       ← User-Anleitung Google-Projekt anlegen
├── .github/workflows/build.yml← CI: Lint + Tests + Windows EXE
├── werkstatt_sync_app.py      ← PyInstaller Entry-Point (wrappt gui.main)
├── werkstatt_sync.spec        ← PyInstaller-Konfiguration
├── requirements.txt           ← Runtime-Dependencies
└── requirements-dev.txt       ← + ruff, pytest
```

## Architektur-Prinzipien

**Schichten von innen nach aussen**, keine umgekehrten Imports:

```
config  ←  excel_parser  ←  planer  ←  orchestrator  ←  gui
                                            ↑
                                       kalender_sync
```

- `config.py` haengt von nichts ab (ausser Stdlib)
- `excel_parser.py` und `planer.py` sind **rein** — keine Netzwerk-/Datei-I/O ausser dem Excel-Read selbst, keine GUI-Imports
- `kalender_sync.py` ist die **einzige** Stelle mit Google-API-Aufrufen
- `orchestrator.py` ist das einzige Modul das ueber alle Schichten redet
- `gui.py` ruft nur `orchestrator.fuehre_sync_durch()` und die `kalender_sync`-Helfer fuer OAuth-Setup auf. **Keine Geschaeftslogik in der GUI.**

Diese Trennung ist nicht nur Hygiene — sie ist Grund dass Tests ohne Tkinter
und ohne Google-API laufen koennen.

## Daten-Persistenz

Alles unter `%APPDATA%\WerkstattSync\` (Windows) bzw. `~/.config/WerkstattSync/`:

- `config.json` — vom User editierbar via GUI
- `credentials.json` — OAuth-Client-Secrets (sensibel, vom User installiert)
- `token.json` — OAuth-Refresh-Token (entsteht beim ersten Login)

Diese drei Dateien sind in `.gitignore` UND werden bei einem `credentials_loeschen()`-Reset zusammen entfernt. Wenn du eine vierte sensible Datei einfuehrst: beide Stellen aktualisieren.

## Wichtige Konzepte

### Zeit-Slots
Ein "Slot" ist ein `(start_h, ende_h)` Tupel mit ganzen Stunden, z.B. `(8, 12)`.
Pro Wochentag (0=Mo..6=So) gibt es eine Liste davon. Leere Liste = freier Tag.

Der Zeitfenster-Parser akzeptiert `"frei"`, `""`, `"9-11"`, `"8-12; 13-15"`, auch
mit Komma als Trenner und Geviertstrich `"9–11"`. Das ist absichtlich tolerant —
beim Bearbeiten der Funktion bitte alle existierenden Tests gruen lassen.

### Termin-Tag
Die Konstante `cfg.termin_tag` (Default `[EW-AUTO]`) wird in jede Termin-Beschreibung
geschrieben. **Nur Termine mit diesem Tag werden beim naechsten Sync geloescht.**
Wenn du den Tag aenderst, verlieren existierende Kalender deine "Identitaet" -
alte Termine werden Waisen. Default beibehalten oder Migrations-Logik bauen.

### Reihenfolge der Auftraege
`excel_einlesen()` sortiert IMMER nach Auftragsnummer **absteigend** (hoechste = neueste zuerst). Das ist die Geschaefts-Anforderung. Wenn du das aenderst, brichst du das mentale Modell des Users.

### Aufteilen verboten
Der Planer **teilt Auftraege niemals** ueber Slot-Grenzen. Passt ein 2h-Auftrag nicht mehr in einen 1h-Rest, wandert er komplett in den naechsten Slot. Wenn du Aufteilen einfuehrst: User fragen, neue Test-Faelle, dokumentieren.

## Konventionen

- **Python 3.12+** (CI nutzt 3.12, lokal auch ok ab 3.11 wegen `from __future__ import annotations`)
- Type-Hints wo sinnvoll, aber kein mypy-Zwang
- **Deutsch** in Variablen-/Funktionsnamen und Doc-Strings (entspricht dem User-Vokabular: "Auftrag", "Kalender", "Werkstatt") — bewusster Stilbruch zugunsten von Lesbarkeit fuer einen deutschen Nutzer. Nicht "uebersetzen" beim Refactoren.
- **Keine Umlaute in Code-Identifiern** (Funktions-, Variablen-, Klassennamen) — kompatibel mit Encoding-Edge-Cases bei PyInstaller. Umlaute in Strings und Doc-Strings sind ok (alle Dateien sind UTF-8).
- Ruff formatiert+lintet — `ruff check . && ruff format .` muss clean sein
- Zeilenlaenge 100 (in `ruff.toml`)
- Tests fuer alles in `config/excel_parser/planer` (rein, einfach testbar). `kalender_sync` wird wegen Google-API nicht getestet. `gui` wird nicht getestet ausser per Smoke-Import.

## Tests ausfuehren

```bash
pip install -r requirements-dev.txt
pytest                   # alle Tests
pytest tests/test_planer.py -v   # einzeln, verbose
ruff check .             # Lint
ruff format .            # Format-Fix
ruff format --check .    # Format-Check (das macht CI)
```

## Wie eine EXE entsteht

1. Lokal: `pip install pyinstaller && pyinstaller werkstatt_sync.spec --noconfirm`
2. CI: Push eines Tags `v*` → GitHub Actions baut auf `windows-latest` → EXE wird ans Release angehaengt
3. CI ohne Tag: `workflow_dispatch` aus GitHub-UI → EXE landet als Artifact (30 Tage Aufbewahrung)

Die `werkstatt_sync.spec` listet `hiddenimports` — das sind Module die PyInstaller nicht automatisch findet (typisch fuer dynamisch geladene Imports). Wenn du eine neue Dependency einfuehrst die spaeter im Build fehlt, dort eintragen.

## Test-Philosophie

**Tests pruefen Verhalten, nicht Daten.** Insbesondere die Tests in `tests/test_excel_parser.py::TestEchteFixture` laufen gegen `tests/fixtures/invoices.xlsx`. Diese Datei wird vom Repo-Maintainer mit anonymisierten Daten gepflegt und kann sich aendern. Tests gegen die Fixture duerfen **niemals** konkrete Werte erwarten ("Auftrag 35 hat eine Notiz", "es gibt 30 Auftraege"), sondern nur Invarianten ("alle Auftraege haben positive Dauer", "Sortierung ist absteigend").

Hintergrund: Wir hatten initial Tests die konkrete Kundennamen und Auftragsnummern aus der ersten Beispiel-Datei hart kodierten. Als jemand die Fixture mit anonymisierten Daten ersetzt hat, brach die CI - aber der Code war korrekt. Lesson: konkrete Werte in Test-Daten sind keine Test-Erwartungen.

## Stolperfallen, die schon mal jemandem passiert sind

### `tkinterdnd2` macht beim PyInstaller-Build Aerger
DnD ist als **optional** implementiert (`try/except ImportError`). Wenn der Build aus irgendeinem Grund nicht klappt, kann man `tkinterdnd2` aus den Hidden-Imports nehmen — die App laeuft dann ohne Drag&Drop, alles andere weiter.

### Google "App nicht verifiziert"-Warnung
Ist kein Bug. Solange das Google-Projekt im Test-Modus ist, sehen Nutzer beim Login eine Warnseite. Workaround steht in `docs/GOOGLE_SETUP.md`. Pro Tester laeuft das Refresh-Token nach 7 Tagen ab. Wenn das stoert: User soll die App-Verifizierung beantragen (oder zumindest "publish" in der Cloud Console druecken).

### Excel-Parser
- `pandas.read_excel` mit `header=1` weil Zeile 0 nur "Rechnungen" steht. Wenn Easywerkstatt das Export-Format aendert, ist das das Erste was bricht.
- Notiz-Spalte heisst "Notizen", Komma als Dezimal-Trenner wird unterstuetzt
- `KundenNr.` (mit Punkt!) — wenn das auch mal anders heisst, hier anpassen

### `kalender_sync.alte_termine_loeschen` paginiert
Google's `events().list()` gibt max 2500 Events pro Page. Wir paginieren mit `pageToken`. Wenn dein Kumpel mal sehr viele Auftraege hat: trotzdem ok, schreitet einfach durch Seiten.

## Wenn du Features hinzufuegst

**Reihenfolge zum Hinzufuegen einer neuen Config-Option** (z.B. "max Auftraege pro Tag"):

1. Feld in `AppConfig` dataclass + `default()` + `to_dict`/`from_dict`
2. Im `planer.plane_auftraege()` die Logik anpassen
3. Test in `tests/test_planer.py` mit dem neuen Verhalten
4. GUI-Feld im Einstellungen-Tab + Speichern-Handler in `gui.py`
5. README + GOOGLE_SETUP.md ggf. updaten

**Wenn du eine neue externe Abhaengigkeit einfuehrst:**

1. `requirements.txt` mit Versions-Pin (`>=X.Y,<X+1`)
2. Falls dynamisch importiert: in `werkstatt_sync.spec` unter `hiddenimports` eintragen
3. Falls Native-DLLs: in `werkstatt_sync.spec` unter `binaries` oder `datas`
4. Build lokal mit PyInstaller einmal pruefen

## Was wir bewusst NICHT machen

- **Keine Telemetrie/Analytics** — die App phoned nicht heim
- **Keine Auto-Updates** — User laedt neue EXE manuell aus Releases. Spart 80% Komplexitaet, kostet 10s pro Update.
- **Kein Code-Signing** — kostet ~200€/Jahr fuer 1 Zertifikat. User klickt die SmartScreen-Warnung einmal weg. Falls die App eine groessere Verbreitung bekommt: dann signieren.
- **Kein Caching von Excel-Daten** — jeder Sync liest die Excel frisch ein. Stale-State-Bugs vermieden.
- **Keine Konflikt-Erkennung** bei manuellen Kalender-Eintraegen — wir kuemmern uns nicht darum, ob unsere generierten Termine sich mit privaten Terminen ueberschneiden. User-Verantwortung.

## Bei groesseren Aenderungen

- Architektur-Diagramm in der README ggf. updaten
- Wenn sich das Excel-Format aendert: Beispiel-Excel ins Repo legen (`tests/fixtures/`)
- Wenn `cfg.termin_tag` ge-default-aendert wird: Migrations-Strategie ueberlegen (User mit alten Termine im Kalender behalten Waisen)
- Vor Release: `pytest && ruff check . && ruff format --check .` lokal gruen, dann `git tag vX.Y.Z`
