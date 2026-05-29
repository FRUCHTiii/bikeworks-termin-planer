# Werkstatt Sync

Liest den Excel-Export aus [Easywerkstatt](https://easywerkstatt.com/) und plant alle offenen Auftraege automatisch in einen Google Kalender ein.

- Neueste Auftragsnummer zuerst
- Volle Werkstatt-Tage werden komplett gefuellt (z.B. Mi + Fr)
- An anderen Tagen nur definierte Zeitfenster (z.B. 9-11 Uhr)
- Geschaetzte Dauer wird aus dem Notiz-Feld in Easywerkstatt gelesen
- Bei erneutem Lauf werden veraltete Termine automatisch durch aktuelle ersetzt
- Manuell angelegte Kalender-Termine bleiben unangetastet

## Installation

1. Neueste `WerkstattSync.exe` von [Releases](../../releases) herunterladen
2. In einen Ordner deiner Wahl legen, z.B. `C:\WerkstattSync\`
3. Doppelklick zum Starten

Beim ersten Start: einmalig Google API einrichten (siehe unten).

## Erste Einrichtung der Google-Verbindung

Einmaliger Vorgang, ~10 Minuten. Detaillierte Anleitung in [docs/GOOGLE_SETUP.md](docs/GOOGLE_SETUP.md).

Kurz gesagt:
1. Im Google Cloud Console ein Projekt anlegen
2. Google Calendar API aktivieren
3. OAuth-Client-ID fuer Desktop-App erstellen
4. `credentials.json` herunterladen
5. In der App: Tab "Einstellungen" -> "credentials.json auswaehlen..."
6. "Mit Google verbinden" klicken -> Browser oeffnet sich -> anmelden

Die `credentials.json` wird sicher in `%APPDATA%\WerkstattSync\` gespeichert.

## Taeglicher Workflow

1. In Easywerkstatt: Excel-Export der offenen Auftraege
2. App oeffnen
3. Excel-Datei in das Drop-Feld ziehen (oder per Klick auswaehlen)
4. "Jetzt synchronisieren"
5. Fertig - alle Auftraege sind im Google Kalender geplant

## Was bedeutet das Notiz-Feld in Easywerkstatt?

Trage die geschaetzte Bearbeitungszeit in das Notiz-Feld ein:
- `1` = 1 Stunde
- `0.5` oder `0,5` = 30 Minuten
- `1.5` = 1 Stunde 30 Minuten

Auftraege ohne Notiz bekommen die Default-Dauer (Standard: 1h, anpassbar in den Einstellungen).

## Eigene Arbeitszeiten konfigurieren

Tab "Einstellungen" -> "Arbeitszeiten pro Wochentag":

- `9-11` = ein Block von 9 bis 11 Uhr
- `8-12; 13-15` = zwei Bloecke (z.B. mit Mittagspause)
- `frei` = an diesem Tag keine Werkstattzeit
- Leeres Feld = wie 'frei'

## Entwicklung

```bash
git clone <repo-url>
cd werkstatt-sync
pip install -r requirements-dev.txt
python werkstatt_sync_app.py
```

Lint, Format, Tests:
```bash
ruff check .              # Lint
ruff format .             # Format-Fix
ruff format --check .     # Format-Check (CI nutzt das)
pytest                    # Tests
```

Vor Commit alles auf einen Schlag:
```bash
ruff check . && ruff format --check . && pytest
```

Fuer Architektur-Hinweise, Konventionen und Stolperfallen siehe [AGENTS.md](AGENTS.md).

EXE bauen:
```bash
pip install pyinstaller
pyinstaller werkstatt_sync.spec --noconfirm
# Ergebnis: dist/WerkstattSync.exe
```

## Release-Prozess

GitHub Actions baut bei jedem Tag-Push automatisch eine Windows-EXE und haengt sie an ein Release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Lizenz

MIT
