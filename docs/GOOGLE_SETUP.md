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

## 3. OAuth-Zustimmungsbildschirm konfigurieren (Google Auth Platform)

Hinweis: Google hat dieses Menue 2025 umbenannt - es heisst jetzt "Google Auth Platform"
statt "OAuth-Zustimmungsbildschirm". Die Schritte sind ein gefuehrter Wizard.

1. Im Menue links: "APIs und Dienste" -> "OAuth-Zustimmungsbildschirm"
   (oder direkt: "Google Auth Platform")
2. Falls die Plattform noch nicht eingerichtet ist, siehst du eine Uebersichts-Seite.
   Klicke auf **"Erste Schritte"** (engl. "Get started")
3. **App-Informationen** ausfuellen:
   - App-Name: "Werkstatt Sync" (oder beliebig)
   - Nutzer-Support-Email: deine Email auswaehlen
   - "Weiter"
4. **Zielgruppe** auswaehlen:
   - **Extern** auswaehlen (Intern geht nur mit Google Workspace Konten)
   - "Weiter"
5. **Kontaktdaten** ausfuellen:
   - Email-Adresse des Entwicklers: deine Email
   - "Weiter"
6. **Fertig**: AGB akzeptieren und "Erstellen" / "Fertig" klicken

Nach dem Wizard landest du auf der "Google Auth Platform" Uebersicht.

### Testnutzer hinzufuegen (nur bei "Extern")

Wenn du "Extern" gewaehlt hast (also kein Google Workspace), musst du dich selbst
als Testnutzer eintragen - sonst kannst du dich spaeter nicht anmelden:

1. Im linken Menue: **"Zielgruppe"** anklicken
2. Bereich "Testnutzer" suchen
3. **"+ Add users"** / "Nutzer hinzufuegen" klicken
4. Deine Google-Email eingeben (die mit dem Kalender)
5. "Speichern"

## 4. OAuth-Client-ID erstellen

1. Im Menue links: "APIs und Dienste" -> **"Anmeldedaten"**
   (in der neuen UI auch unter "Google Auth Platform" -> "Clients" zu finden)
2. Oben **"+ Anmeldedaten erstellen"** -> "OAuth-Client-ID"
3. Anwendungstyp: **Desktop-App** (WICHTIG - nicht "Webanwendung")
4. Name: "Werkstatt Sync Desktop"
5. "Erstellen"
6. Popup erscheint mit Client-ID und Client-Secret
7. Auf **"JSON HERUNTERLADEN"** klicken
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

## Wichtig: Token laeuft nach 7 Tagen ab (im Test-Modus)

Im Standard-Modus ("Test-Modus") gibt Google Tokens nur **7 Tage lang** gueltig
aus - danach musst du dich neu anmelden. Das wird auf Dauer nervig.

**Loesung: App auf "In Produktion" umstellen.** Das ist EIN Klick, danach laufen
deine Tokens dauerhaft (bis du sie selbst widerrufst).

### Was bedeutet "In Produktion" hier?

In der Google-Welt gibt es zwei separate Konzepte, die oft verwechselt werden:

- **Publishing Status**: Test-Modus oder In Produktion (= der Knopf den wir gleich
  druecken)
- **Verifizierung**: App wird von Google manuell geprueft (mehrere Wochen Aufwand,
  Datenschutzerklaerung, Demo-Video, ...)

Wir machen nur die erste Sache. **Die App muss NICHT verifiziert werden** - das
ist ein offiziell von Google unterstuetzter Modus. Status "In Produktion" ohne
Verifizierung bedeutet:

| Punkt | Vorher (Test) | Nachher (Produktion, nicht verifiziert) |
|-------|---------------|----------------------------------------|
| Token-Ablauf | 7 Tage | Unbegrenzt (bis manueller Widerruf) |
| Testnutzer-Liste | Pflicht | Nicht mehr noetig |
| "App nicht verifiziert"-Screen | Bei jedem Login | Nur beim allerersten Login |
| Limit auf 100 Nutzer | Ja | Nein |
| Verifizierungs-Aufwand | Keiner | Keiner |

### So stellst du um (~30 Sekunden)

1. Im Google Cloud Console: **Google Auth Platform** -> **"Zielgruppe"** (engl. "Audience")
2. Oben auf der Seite siehst du den Bereich **"Veroeffentlichungsstatus"** (engl. "Publishing status")
3. Aktueller Status: **"Testen"** (engl. "Testing")
4. Knopf **"App veroeffentlichen"** (engl. "Publish app") klicken
5. Ein Bestaetigungs-Dialog erscheint mit Hinweisen zur Verifizierung
   - **Nicht abschrecken lassen** - du musst die App NICHT zur Verifizierung
     einreichen, nur den Status aendern
6. **"Bestaetigen"** klicken
7. Status wechselt zu **"In Produktion"** (engl. "In production") - fertig

### Danach: einmal in der App neu verbinden

Das alte 7-Tage-Token bleibt erstmal gueltig, aber damit du das neue dauerhafte
Token bekommst, einmal:

1. In der Werkstatt Sync App: Tab "Einstellungen"
2. "Verbindung zuruecksetzen" klicken
3. "Mit Google verbinden" klicken
4. Anmelden (der Browser zeigt jetzt einmalig die "App nicht verifiziert"-Warnung -
   "Erweitert" -> "Trotzdem fortfahren")
5. Fertig - das neue Token laeuft dauerhaft

### Wichtig zu wissen

- Diese Aenderung gilt nur fuer **dein** Google-Cloud-Projekt. Sie hat keine
  Auswirkung auf andere Werkstatt-Sync-Nutzer, deren GitHub-User oder das Repo
  selbst. Jeder Nutzer macht das selbst fuer sein eigenes Projekt.
- Google koennte dich theoretisch irgendwann zur Verifizierung auffordern. In der
  Praxis passiert das bei Apps mit einer Handvoll Nutzer praktisch nie - und wenn
  doch, wird vorher per Email gewarnt.
- Solltest du verifizieren wollen (z.B. wenn du die App weitergeben moechtest und
  den "unverified app"-Screen vermeiden willst), siehe
  https://support.google.com/cloud/answer/9110914 - das ist aber ein Wochen-
  Projekt mit Datenschutzerklaerung und Demo-Video.

## Troubleshooting

**"Diese App ist blockiert" oder "Access blocked"**: Du bist nicht als Testnutzer
eingetragen. Geh in der Google Cloud Console zu "Google Auth Platform" ->
"Zielgruppe" und fuege deine Email unter "Testnutzer" hinzu (siehe Schritt 3).

**"Das sind Web Application Credentials"**: Falscher Anwendungstyp gewaehlt.
In Schritt 4 muss "Desktop-App" ausgewaehlt sein, nicht "Webanwendung".
OAuth-Client neu erstellen.

**"Login funktioniert spaeter nicht mehr" / Token laeuft staendig ab**:
Im Test-Modus laeuft das Token nach 7 Tagen ab. Loesung: App auf "In Produktion"
umstellen (siehe Sektion oben "Wichtig: Token laeuft nach 7 Tagen ab"). Falls
das gerade nicht moeglich ist - in der App "Verbindung zuruecksetzen" und neu
verbinden.

**Ich finde "OAuth-Zustimmungsbildschirm" nicht im Menue**: Google hat das Menue
2025 umbenannt. Es heisst jetzt **"Google Auth Platform"** und liegt im linken
Menue unter "APIs und Dienste" oder direkt als eigener Menuepunkt.

## Eigener Werkstatt-Kalender (empfohlen)

Damit Werkstatt-Termine nicht den Hauptkalender ueberladen:

1. https://calendar.google.com oeffnen
2. Links bei "Weitere Kalender" auf "+" -> "Neuen Kalender erstellen"
3. Name z.B. "Werkstatt", erstellen
4. In den Kalender-Einstellungen ganz unten findest du die "Kalender-ID"
   (sieht aus wie `abc123...@group.calendar.google.com`)
5. In der Werkstatt-Sync-App: Einstellungen -> "Google Kalender ID" -> dort einfuegen
6. Speichern
