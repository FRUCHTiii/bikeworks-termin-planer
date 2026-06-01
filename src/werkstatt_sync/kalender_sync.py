"""Google Calendar Sync: OAuth, Termine anlegen, alte loeschen."""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import CREDENTIALS_PATH, TOKEN_PATH, AppConfig
from .planer import Termin

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CredentialsFehlt(Exception):
    """credentials.json wurde noch nicht vom Nutzer bereitgestellt."""


class AuthAbgebrochen(Exception):
    """User hat OAuth-Flow abgebrochen."""


def credentials_vorhanden() -> bool:
    return CREDENTIALS_PATH.exists()


def token_vorhanden() -> bool:
    return TOKEN_PATH.exists()


def credentials_installieren(quell_pfad: str | Path) -> None:
    """Kopiert eine vom Nutzer ausgewaehlte credentials.json ins AppData.

    Validiert auch grob, dass es eine Desktop-OAuth-Datei ist.
    """
    quell_pfad = Path(quell_pfad)
    if not quell_pfad.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {quell_pfad}")

    # Grobe Validierung
    import json

    try:
        with open(quell_pfad, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        raise ValueError("Die Datei ist keine gueltige JSON-Datei.") from err

    if "installed" not in data and "web" not in data:
        raise ValueError(
            "Das ist keine Google OAuth Client Credentials Datei. "
            "Erwarte 'installed' oder 'web' Schluessel."
        )
    if "web" in data and "installed" not in data:
        raise ValueError(
            "Das sind 'Web Application' Credentials. Es muessen "
            "'Desktop App' Credentials sein. Siehe Anleitung."
        )

    shutil.copy2(quell_pfad, CREDENTIALS_PATH)


def credentials_loeschen() -> None:
    """Loescht gespeicherte credentials.json und token.json (Reset)."""
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()


def google_login() -> Credentials:
    """Fuehrt OAuth durch (oeffnet Browser) und speichert Token.

    Wirft CredentialsFehlt wenn keine credentials.json da ist.
    """
    if not CREDENTIALS_PATH.exists():
        raise CredentialsFehlt("credentials.json fehlt. Bitte in den Einstellungen auswaehlen.")

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def get_service():
    """Stellt Verbindung zu Google Calendar her.

    Nutzt gespeicherten Token. Wirft CredentialsFehlt wenn noch kein
    Login durchgefuehrt wurde.
    """
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            # Kein Token oder nicht refreshbar -> neuer Login noetig
            creds = google_login()

    return build("calendar", "v3", credentials=creds)


def alte_termine_loeschen(
    service, cfg: AppConfig, ab_zeitpunkt: dt.datetime | None = None, log=print
) -> int:
    """Loescht alle vom Skript erstellten Termine ab dem gegebenen Zeitpunkt.

    Erkennt sie am cfg.termin_tag in der Beschreibung. Manuelle Termine
    bleiben unangetastet.

    Args:
        ab_zeitpunkt: Loesche Termine ab diesem Zeitpunkt (als naive lokale
            Zeit oder mit Timezone). Default: jetzt.
            Sollte mit dem Planungs-Startdatum uebereinstimmen, sonst
            entstehen Duplikate (wenn die Planung in der Vergangenheit beginnt
            und das Loeschen erst ab jetzt sucht).
    """
    if ab_zeitpunkt is None:
        ab_zeitpunkt = dt.datetime.now()

    # Google-API erwartet ISO-Format mit Timezone-Info.
    # Naive datetimes (Default vom Planer) werden als lokale Zeit interpretiert
    # und in UTC umgerechnet. Bewusste Z-Strings einfach durchreichen.
    if ab_zeitpunkt.tzinfo is None:
        ab_zeitpunkt = ab_zeitpunkt.astimezone()  # haengt die lokale Timezone an
    time_min = ab_zeitpunkt.replace(microsecond=0).isoformat()

    geloescht = 0
    page_token = None
    while True:
        result = (
            service.events()
            .list(
                calendarId=cfg.kalender_id,
                timeMin=time_min,
                q=cfg.termin_tag,
                maxResults=2500,
                singleEvents=True,
                pageToken=page_token,
            )
            .execute()
        )

        for ev in result.get("items", []):
            # Sicherheits-Check: Tag wirklich in Beschreibung
            if cfg.termin_tag in (ev.get("description") or ""):
                service.events().delete(calendarId=cfg.kalender_id, eventId=ev["id"]).execute()
                geloescht += 1

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return geloescht


def hole_belegte_zeiten(
    service,
    ab: dt.datetime,
    bis: dt.datetime,
    cfg: AppConfig,
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Gibt alle belegten Zeitraeume aus allen (oder nur dem eigenen) Kalender zurueck.

    Nutzt die FreeBusy-API, die alle Kalender des Accounts auf einmal abfragen kann.
    Ignoriert Termine die vom Sync selbst angelegt wurden ([EW-AUTO]).

    cfg.alle_kalender_pruefen=True:  alle Kalender des Accounts werden geprüft
    cfg.alle_kalender_pruefen=False: nur cfg.kalender_id wird geprueft
    """
    if ab.tzinfo is None:
        ab = ab.astimezone()
    if bis.tzinfo is None:
        bis = bis.astimezone()

    if cfg.alle_kalender_pruefen:
        # Alle Kalender-IDs aus dem Account ermitteln
        kalender_liste = service.calendarList().list().execute()
        kalender_ids = [k["id"] for k in kalender_liste.get("items", [])]
    else:
        kalender_ids = [cfg.kalender_id]

    body = {
        "timeMin": ab.replace(microsecond=0).isoformat(),
        "timeMax": bis.replace(microsecond=0).isoformat(),
        "items": [{"id": kid} for kid in kalender_ids],
    }
    result = service.freebusy().query(body=body).execute()

    belegte_zeiten: list[tuple[dt.datetime, dt.datetime]] = []
    for kid in kalender_ids:
        for periode in result.get("calendars", {}).get(kid, {}).get("busy", []):
            start = dt.datetime.fromisoformat(periode["start"].replace("Z", "+00:00"))
            ende = dt.datetime.fromisoformat(periode["end"].replace("Z", "+00:00"))
            # In naive lokale Zeit umwandeln (wie der Planer arbeitet)
            belegte_zeiten.append((
                start.astimezone().replace(tzinfo=None),
                ende.astimezone().replace(tzinfo=None),
            ))

    return belegte_zeiten


def termin_anlegen(service, termin: Termin, cfg: AppConfig) -> None:
    """Legt einen einzelnen Termin im Google Kalender an."""
    a = termin.auftrag
    titel = f"#{a.nummer} - {a.kunde}"
    beschreibung_zeilen = [
        cfg.termin_tag,
        f"Auftragsnummer: {a.nummer}",
        f"Kunde: {a.kunde}",
    ]
    if a.kunden_nr:
        beschreibung_zeilen.append(f"KundenNr: {a.kunden_nr}")
    if a.betrag:
        beschreibung_zeilen.append(f"Betrag: {a.betrag}")
    beschreibung_zeilen.append(f"Geschaetzte Dauer: {a.dauer_stunden}h")
    if not a.hat_zeit_notiz:
        beschreibung_zeilen.append("(Default-Dauer verwendet - keine Zeit-Notiz in Excel)")

    event = {
        "summary": titel,
        "description": "\n".join(beschreibung_zeilen),
        "start": {"dateTime": termin.start.isoformat(), "timeZone": cfg.zeitzone},
        "end": {"dateTime": termin.ende.isoformat(), "timeZone": cfg.zeitzone},
        # Keine E-Mail-Benachrichtigungen - nur App-Erinnerungen unterdruecken
        "reminders": {"useDefault": False, "overrides": []},
    }
    service.events().insert(calendarId=cfg.kalender_id, body=event).execute()
