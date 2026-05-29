# Google Calendar API Einrichten

Einmaliger Vorgang, ca. 10 Minuten. Du brauchst nur ein Google-Konto.

## 1. Projekt anlegen

1. https://console.cloud.google.com/ aufrufen und mit deinem Google-Konto anmelden
2. Oben in der Leiste auf den Projekt-Namen klicken (links neben der Suche)
3. Im Popup "Neues Projekt" anklicken
4. Name z.B. "Werkstatt Sync"
5. "Erstellen" klicken
6. Warte bis das Projekt erstellt ist, dann oben sicherstellen dass es ausgewaehlt ist

## 2. Calendar API aktivieren

1. Im Menue links (Hamburger oben links): "APIs und Dienste" -> "Bibliothek"
2. In der Suchleiste "Google Calendar API" eingeben
3. Eintrag anklicken
4. "Aktivieren" klicken

## 3. OAuth-Zustimmungsbildschirm konfigurieren

1. Im Menue links: "APIs und Dienste" -> "OAuth-Zustimmungsbildschirm"
2. Nutzertyp: **Extern** auswaehlen, dann "Erstellen"
3. Im Formular ausfuellen:
   - App-Name: "Werkstatt Sync" (oder beliebig)
   - Nutzer-Support-Email: deine Email
   - Email des Entwicklers: deine Email
   - Alle anderen Felder leer lassen
4. "Speichern und fortfahren"
5. Bei "Bereiche": einfach "Speichern und fortfahren"
6. Bei "Testnutzer":
   - "+ Add Users" klicken
   - Deine Google-Email eingeben (die mit dem Kalender)
   - "Hinzufuegen"
   - "Speichern und fortfahren"
7. Zusammenfassung: "Zum Dashboard"

## 4. OAuth-Client-ID erstellen

1. Im Menue: "APIs und Dienste" -> "Anmeldedaten"
2. Oben "+ Anmeldedaten erstellen" -> "OAuth-Client-ID"
3. Anwendungstyp: **Desktop-App** (WICHTIG - nicht "Webanwendung")
4. Name: "Werkstatt Sync Desktop"
5. "Erstellen"
6. Popup erscheint mit Client-ID und Client-Secret
7. Auf "JSON HERUNTERLADEN" klicken
8. Datei in einen sicheren Ordner speichern (z.B. `Dokumente/`)

## 5. In der App einbinden

1. Werkstatt Sync App oeffnen
2. Tab "Einstellungen"
3. Unten bei "Google API Verbindung":
   - "credentials.json auswaehlen..." klicken
   - Die heruntergeladene Datei auswaehlen
   - Bestaetigung erscheint
4. "Mit Google verbinden" klicken
5. Browser oeffnet sich:
   - Mit deinem Google-Konto anmelden (das du als Testnutzer hinzugefuegt hast)
   - **Es erscheint eine Warnung "Google hat diese App nicht verifiziert"** -
     das ist normal, weil die App nur fuer dich privat ist:
     - "Erweitert" klicken
     - "Weiter zu Werkstatt Sync (unsicher)" klicken
   - Berechtigung "Kalender ansehen und verwalten" erlauben
6. Der Browser zeigt "Authentifizierung war erfolgreich" - du kannst ihn schliessen
7. In der App erscheint "✓ Mit Google verbunden"

## Fertig!

Du kannst jetzt synchronisieren. Den Login musst du nicht wieder machen, das Token
wird gespeichert.

## Troubleshooting

**"Diese App ist blockiert"**: Email nicht als Testnutzer hinzugefuegt.
Schritt 3.6 wiederholen.

**"Das sind Web Application Credentials"**: Falscher Anwendungstyp gewaehlt.
Schritt 4.3 muss "Desktop-App" sein. OAuth-Client neu erstellen.

**"Login funktioniert spaeter nicht mehr"**: Test-Token laeuft nach 7 Tagen ab
(typisch fuer nicht-verifizierte Apps). In der App "Verbindung zuruecksetzen"
und neu verbinden.

## Eigener Werkstatt-Kalender (empfohlen)

Damit Werkstatt-Termine nicht den Hauptkalender ueberladen:

1. https://calendar.google.com oeffnen
2. Links bei "Weitere Kalender" auf "+" -> "Neuen Kalender erstellen"
3. Name z.B. "Werkstatt", erstellen
4. In den Kalender-Einstellungen ganz unten findest du die "Kalender-ID"
   (sieht aus wie `abc123...@group.calendar.google.com`)
5. In der Werkstatt-Sync-App: Einstellungen -> "Google Kalender ID" -> dort einfuegen
6. Speichern
