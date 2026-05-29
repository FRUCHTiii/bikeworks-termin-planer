"""Entry-Point fuer PyInstaller. Startet die GUI."""

import sys
from pathlib import Path

# Damit es auch ohne installiertes Paket laeuft
sys.path.insert(0, str(Path(__file__).parent / "src"))

from werkstatt_sync.gui import main

if __name__ == "__main__":
    main()
