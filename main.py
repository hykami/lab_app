"""
Lab App — точка входа
Python : 3.14.4
PyQt6  : 6.11.0
"""

from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication

from data.database import init_db
from ui.main_window import MainWindow
from utils.fonts import download_fonts, register_fonts


def _setup_logging() -> None:
    """Настройка глобального логгера: WARNING и выше в stderr с timestamp."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    _setup_logging()
    init_db()
    download_fonts()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    register_fonts()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
