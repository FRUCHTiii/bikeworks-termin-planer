"""Tkinter GUI: zwei Tabs (Sync + Einstellungen) + Drag&Drop."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Drag&Drop ist optional - faellt zurueck auf Datei-Picker wenn nicht installiert
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_VERFUEGBAR = True
except ImportError:
    DND_VERFUEGBAR = False

from . import __version__
from .config import (
    DayConfig,
    format_zeitfenster,
    load_config,
    parse_zeitfenster,
    save_config,
)
from .kalender_sync import (
    CredentialsFehlt,
    credentials_installieren,
    credentials_loeschen,
    credentials_vorhanden,
    google_login,
    token_vorhanden,
)
from .orchestrator import fuehre_sync_durch
from .update_checker import pruefe_update_im_hintergrund

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class WerkstattSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Werkstatt Sync")
        self.root.geometry("760x620")
        self.root.minsize(720, 580)

        self.cfg = load_config()
        self.excel_pfad: str | None = self.cfg.letzte_excel_datei or None
        self.sync_laeuft = False

        self._baue_ui()
        self._aktualisiere_status()
        self._pruefe_update()

    def _pruefe_update(self):
        def _zeige_hinweis(neuester_tag: str):
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Update verfuegbar",
                    f"Eine neue Version ist verfuegbar: {neuester_tag}\n"
                    f"(Aktuell installiert: v{__version__})\n\n"
                    "Bitte lade die neueste Version von GitHub herunter.",
                ),
            )

        pruefe_update_im_hintergrund(__version__, _zeige_hinweis)

    def _baue_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self.sync_tab = ttk.Frame(notebook)
        self.einstellungen_tab = ttk.Frame(notebook)
        notebook.add(self.sync_tab, text="  Sync  ")
        notebook.add(self.einstellungen_tab, text="  Einstellungen  ")

        self._baue_sync_tab()
        self._baue_einstellungen_tab()

    # ===================================================================
    # SYNC TAB
    # ===================================================================
    def _baue_sync_tab(self):
        frame = self.sync_tab

        # Header
        ttk.Label(
            frame, text="Easywerkstatt → Google Kalender", font=("Segoe UI", 14, "bold")
        ).pack(pady=(16, 4))
        ttk.Label(
            frame, text="Excel-Datei hier hineinziehen oder per Klick auswaehlen", foreground="#666"
        ).pack(pady=(0, 12))

        # Drop-Zone
        self.drop_zone = tk.Frame(
            frame,
            bg="#f0f0f0",
            relief="solid",
            borderwidth=2,
            highlightbackground="#bbb",
            highlightthickness=1,
        )
        self.drop_zone.pack(fill="x", padx=20, pady=8, ipady=24)

        self.drop_label = tk.Label(
            self.drop_zone,
            bg="#f0f0f0",
            fg="#555",
            font=("Segoe UI", 11),
            text="📂 Excel-Datei hier hineinziehen\n(oder klicken zum Auswaehlen)",
            cursor="hand2",
            justify="center",
        )
        self.drop_label.pack(pady=20, padx=20)
        self.drop_label.bind("<Button-1>", lambda e: self._datei_auswaehlen())

        if DND_VERFUEGBAR:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)

        # Status & Button
        status_frame = ttk.Frame(frame)
        status_frame.pack(fill="x", padx=20, pady=(8, 4))

        self.status_label = ttk.Label(status_frame, text="", font=("Segoe UI", 10))
        self.status_label.pack(side="left")

        self.sync_button = ttk.Button(
            status_frame,
            text="Jetzt synchronisieren",
            command=self._sync_starten,
            state="disabled",
        )
        self.sync_button.pack(side="right")

        # Log-Fenster
        ttk.Label(frame, text="Protokoll:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=20, pady=(12, 4)
        )

        log_frame = ttk.Frame(frame)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.log_text = tk.Text(
            log_frame,
            height=14,
            wrap="word",
            state="disabled",
            bg="#fafafa",
            font=("Consolas", 9),
        )
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def _on_drop(self, event):
        # Pfade aus DND_FILES kommen in geschweiften Klammern wenn Leerzeichen drin
        pfad = event.data.strip()
        if pfad.startswith("{") and pfad.endswith("}"):
            pfad = pfad[1:-1]
        self._setze_excel_pfad(pfad)

    def _datei_auswaehlen(self):
        pfad = filedialog.askopenfilename(
            title="Easywerkstatt Excel-Export auswaehlen",
            filetypes=[("Excel-Dateien", "*.xlsx *.xls"), ("Alle Dateien", "*.*")],
        )
        if pfad:
            self._setze_excel_pfad(pfad)

    def _setze_excel_pfad(self, pfad: str):
        p = Path(pfad)
        if not p.exists():
            messagebox.showerror("Fehler", f"Datei nicht gefunden:\n{pfad}")
            return
        if p.suffix.lower() not in (".xlsx", ".xls"):
            messagebox.showerror("Fehler", "Bitte eine .xlsx oder .xls Datei auswaehlen.")
            return

        self.excel_pfad = str(p)
        self.cfg.letzte_excel_datei = self.excel_pfad
        save_config(self.cfg)

        self.drop_label.configure(
            text=f"✓ {p.name}\n{p.parent}",
            fg="#2a7",
        )
        self._aktualisiere_status()

    def _aktualisiere_status(self):
        bereit_excel = self.excel_pfad is not None and Path(self.excel_pfad or "").exists()
        bereit_google = credentials_vorhanden() and token_vorhanden()

        if not bereit_excel and not bereit_google:
            self.status_label.configure(
                text="⚠ Keine Excel-Datei, Google-Konto nicht verbunden",
                foreground="#c33",
            )
        elif not bereit_excel:
            self.status_label.configure(text="⚠ Keine Excel-Datei ausgewaehlt", foreground="#c33")
        elif not bereit_google:
            self.status_label.configure(
                text="⚠ Google-Konto nicht verbunden (siehe Einstellungen)",
                foreground="#c33",
            )
        else:
            self.status_label.configure(text="✓ Bereit", foreground="#2a7")

        self.sync_button.configure(
            state="normal"
            if (bereit_excel and bereit_google and not self.sync_laeuft)
            else "disabled"
        )

    def _log(self, text: str):
        """Thread-sicher in Log-Fenster schreiben."""

        def schreiben():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, schreiben)

    def _log_loeschen(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _sync_starten(self):
        if self.sync_laeuft:
            return
        self.sync_laeuft = True
        self._aktualisiere_status()
        self._log_loeschen()

        # In Thread ausfuehren damit GUI nicht einfriert
        threading.Thread(target=self._sync_thread, daemon=True).start()

    def _sync_thread(self):
        try:
            ergebnis = fuehre_sync_durch(self.excel_pfad, self.cfg, log=self._log)
            if ergebnis.fehler:
                self._log(f"\nFEHLER: {ergebnis.fehler}")
                self.root.after(
                    0, lambda: messagebox.showerror("Sync fehlgeschlagen", ergebnis.fehler)
                )
            else:
                zusammenfassung = (
                    f"\n--- Zusammenfassung ---\n"
                    f"Auftraege gesamt: {ergebnis.auftraege_gesamt}\n"
                    f"Davon ohne Zeit-Notiz: {ergebnis.auftraege_ohne_zeit}\n"
                    f"Alte Termine geloescht: {ergebnis.termine_geloescht}\n"
                    f"Neue Termine erstellt: {ergebnis.termine_erstellt}\n"
                )
                if ergebnis.ungeplant > 0:
                    zusammenfassung += f"NICHT eingeplant: {ergebnis.ungeplant}\n"
                self._log(zusammenfassung)
        except Exception as e:
            fehler_text = str(e)
            self._log(f"\nUnerwarteter Fehler: {fehler_text}")
            self.root.after(0, lambda: messagebox.showerror("Fehler", fehler_text))
        finally:
            self.sync_laeuft = False
            self.root.after(0, self._aktualisiere_status)

    # ===================================================================
    # EINSTELLUNGEN TAB
    # ===================================================================
    def _baue_einstellungen_tab(self):
        frame = self.einstellungen_tab

        # Scrollbarer Container fuer kleinere Bildschirme
        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=720)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mausrad
        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _scroll)

        # === Sektion: Arbeitszeiten ===
        sek = ttk.LabelFrame(inner, text=" Arbeitszeiten pro Wochentag ", padding=12)
        sek.pack(fill="x", padx=16, pady=(16, 8))

        ttk.Label(
            sek,
            foreground="#666",
            text="Format: '9-11' fuer einen Block, '8-12; 13-15' fuer zwei Bloecke "
            "(z.B. mit Mittagspause), 'frei' fuer geschlossen.",
        ).pack(anchor="w", pady=(0, 8))

        self.tag_entries: dict[int, ttk.Entry] = {}
        for wd in range(7):
            row = ttk.Frame(sek)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=WOCHENTAGE[wd], width=12).pack(side="left")
            entry = ttk.Entry(row, width=40)
            entry.insert(0, format_zeitfenster(self.cfg.days.get(wd, DayConfig()).slots))
            entry.pack(side="left", padx=8)
            self.tag_entries[wd] = entry

        # === Sektion: Allgemein ===
        sek2 = ttk.LabelFrame(inner, text=" Allgemein ", padding=12)
        sek2.pack(fill="x", padx=16, pady=8)

        row = ttk.Frame(sek2)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text="Default-Dauer (Stunden):", width=30).pack(side="left")
        self.default_dauer_var = tk.StringVar(value=str(self.cfg.default_dauer_stunden))
        ttk.Entry(row, textvariable=self.default_dauer_var, width=10).pack(side="left")
        ttk.Label(row, text=" - genutzt wenn Auftrag keine Zeit-Notiz hat", foreground="#666").pack(
            side="left", padx=(8, 0)
        )

        row = ttk.Frame(sek2)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text="Google Kalender ID:", width=30).pack(side="left")
        self.kalender_id_var = tk.StringVar(value=self.cfg.kalender_id)
        ttk.Entry(row, textvariable=self.kalender_id_var, width=44).pack(side="left")

        row = ttk.Frame(sek2)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text="", width=30).pack(side="left")
        ttk.Label(
            row,
            foreground="#666",
            text="'primary' = Hauptkalender, oder ID eines Unterkalenders",
        ).pack(side="left")

        row = ttk.Frame(sek2)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text="Planung beginnt:", width=30).pack(side="left")
        self.ab_morgen_var = tk.BooleanVar(value=self.cfg.planung_ab_morgen)
        ttk.Radiobutton(row, text="ab morgen", variable=self.ab_morgen_var, value=True).pack(
            side="left"
        )
        ttk.Radiobutton(row, text="ab heute", variable=self.ab_morgen_var, value=False).pack(
            side="left", padx=(12, 0)
        )

        # Speichern-Button fuer alle obigen Einstellungen
        ttk.Button(
            inner, text="Einstellungen speichern", command=self._einstellungen_speichern
        ).pack(pady=8)

        # === Sektion: Google API ===
        sek3 = ttk.LabelFrame(inner, text=" Google API Verbindung ", padding=12)
        sek3.pack(fill="x", padx=16, pady=8)

        self.google_status_label = ttk.Label(sek3, text="", font=("Segoe UI", 10))
        self.google_status_label.pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(sek3)
        btn_row.pack(fill="x")
        ttk.Button(
            btn_row, text="credentials.json auswaehlen...", command=self._credentials_auswaehlen
        ).pack(side="left")
        ttk.Button(btn_row, text="Mit Google verbinden", command=self._google_verbinden).pack(
            side="left", padx=8
        )
        ttk.Button(
            btn_row, text="Verbindung zuruecksetzen", command=self._verbindung_zuruecksetzen
        ).pack(side="left")

        ttk.Label(
            sek3,
            foreground="#666",
            wraplength=680,
            justify="left",
            text="Anleitung zur Erstellung der credentials.json siehe ANLEITUNG.md "
            "(einmaliger Vorgang, ~10 Minuten).",
        ).pack(anchor="w", pady=(8, 0))

        self._aktualisiere_google_status()

    def _einstellungen_speichern(self):
        # Tage parsen
        new_days = {}
        for wd in range(7):
            txt = self.tag_entries[wd].get()
            try:
                slots = parse_zeitfenster(txt)
            except ValueError as e:
                messagebox.showerror(
                    "Ungueltiges Zeitfenster",
                    f"{WOCHENTAGE[wd]}: {e}\n\nFormat: '9-11' oder '8-12; 13-15' oder 'frei'",
                )
                return
            new_days[wd] = DayConfig(slots)
        self.cfg.days = new_days

        # Default-Dauer
        try:
            d = float(self.default_dauer_var.get().replace(",", "."))
            if d <= 0 or d > 24:
                raise ValueError
            self.cfg.default_dauer_stunden = d
        except ValueError:
            messagebox.showerror("Fehler", "Default-Dauer muss eine Zahl zwischen 0 und 24 sein.")
            return

        self.cfg.kalender_id = self.kalender_id_var.get().strip() or "primary"
        self.cfg.planung_ab_morgen = self.ab_morgen_var.get()

        save_config(self.cfg)
        messagebox.showinfo("Gespeichert", "Einstellungen gespeichert.")

    def _aktualisiere_google_status(self):
        if not credentials_vorhanden():
            self.google_status_label.configure(text="✗ credentials.json fehlt", foreground="#c33")
        elif not token_vorhanden():
            self.google_status_label.configure(
                text="○ credentials.json vorhanden, aber noch kein Login erfolgt", foreground="#c80"
            )
        else:
            self.google_status_label.configure(text="✓ Mit Google verbunden", foreground="#2a7")
        self._aktualisiere_status()

    def _credentials_auswaehlen(self):
        pfad = filedialog.askopenfilename(
            title="credentials.json auswaehlen",
            filetypes=[("JSON-Dateien", "*.json"), ("Alle Dateien", "*.*")],
        )
        if not pfad:
            return
        try:
            credentials_installieren(pfad)
        except (ValueError, FileNotFoundError) as e:
            messagebox.showerror("Fehler", str(e))
            return
        messagebox.showinfo(
            "credentials.json installiert",
            "Datei wurde gespeichert. Klicke jetzt auf 'Mit Google verbinden'.",
        )
        self._aktualisiere_google_status()

    def _google_verbinden(self):
        if not credentials_vorhanden():
            messagebox.showerror("Fehler", "Bitte zuerst credentials.json auswaehlen.")
            return
        try:
            google_login()
        except CredentialsFehlt as e:
            messagebox.showerror("Fehler", str(e))
            return
        except Exception as e:
            messagebox.showerror(
                "Login fehlgeschlagen", f"Der OAuth-Vorgang konnte nicht abgeschlossen werden:\n{e}"
            )
            return
        messagebox.showinfo("Verbunden", "Erfolgreich mit Google verbunden!")
        self._aktualisiere_google_status()

    def _verbindung_zuruecksetzen(self):
        if not messagebox.askyesno(
            "Zuruecksetzen?", "Alle gespeicherten Google-Credentials und Token loeschen?"
        ):
            return
        credentials_loeschen()
        self._aktualisiere_google_status()


def main():
    root = TkinterDnD.Tk() if DND_VERFUEGBAR else tk.Tk()
    WerkstattSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
