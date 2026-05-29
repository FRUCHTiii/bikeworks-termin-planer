"""Smoke-Tests: alle Module importieren, Architektur-Grenzen respektiert."""

import importlib


def test_alle_module_importieren():
    """Wenn ein Modul Syntax-Fehler oder fehlende Imports hat, faengt es das."""
    for mod in [
        "werkstatt_sync",
        "werkstatt_sync.config",
        "werkstatt_sync.excel_parser",
        "werkstatt_sync.planer",
        "werkstatt_sync.kalender_sync",
        "werkstatt_sync.orchestrator",
    ]:
        importlib.import_module(mod)


def test_planer_haengt_nicht_von_kalender_ab():
    """planer.py darf KEINE Google-Bibliothek importieren - Schichten-Regel."""
    import werkstatt_sync.planer as planer

    src = open(planer.__file__).read()
    assert "google" not in src.lower(), (
        "planer.py darf nicht von google-* Paketen abhaengen "
        "(siehe Architektur-Prinzipien in AGENTS.md)"
    )


def test_excel_parser_haengt_nicht_von_kalender_ab():
    import werkstatt_sync.excel_parser as parser

    src = open(parser.__file__).read()
    assert "google" not in src.lower()


def test_config_haengt_nicht_von_googleapi_ab():
    """config darf nur von Stdlib abhaengen."""
    import werkstatt_sync.config as cfg

    src = open(cfg.__file__).read()
    assert "google" not in src.lower()
    assert "tkinter" not in src.lower()
    assert "pandas" not in src.lower()


def test_orchestrator_kennt_alle_schichten():
    """Sanity-Check: orchestrator nutzt Excel + Planer + Kalender."""
    import werkstatt_sync.orchestrator as o

    src = open(o.__file__).read()
    assert "excel_parser" in src
    assert "planer" in src
    assert "kalender_sync" in src
