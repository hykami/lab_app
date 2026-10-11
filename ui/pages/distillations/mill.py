"""Мукомолка — экспорт в лист МКМЦ."""
from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import QWidget
from ui.pages.distillations.base_distillation import BaseDistillationPage
from logic.excel_writer import export_to_mkmts


class MillPage(BaseDistillationPage):
    SHOW_TANK = True
    DISTILLATION_PLACES = frozenset({"Мукомолка"})

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Мукомолка",
            section="Перегонки",
            export_fn=export_to_mkmts,
            parent=parent,
        )
