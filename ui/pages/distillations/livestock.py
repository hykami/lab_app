"""КРС / Свинки — экспорт в лист Производства АПП."""
from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import QWidget
from ui.pages.distillations.base_distillation import BaseDistillationPage
from logic.excel_writer import export_to_app


class LivestockPage(BaseDistillationPage):
    SHOW_TANK = True
    DISTILLATION_PLACES = frozenset({"КРС", "Свинки", "Рыбы"})

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="КРС / Свинки",
            section="Перегонки",
            export_fn=export_to_app,
            parent=parent,
        )
