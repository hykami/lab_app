"""
Компонент выбора пробы — выпадающий список с номерами карточек.
При выборе возвращает объект Card через callback.
"""

from __future__ import annotations
from typing import Optional, Callable

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ui.components.styled_combo import StyledComboBox
from ui.style_helpers import combo_style
from ui.theme import FONT_UI
from logic.db_service import get_all_cards, Card


class ProbeSelector(QWidget):
    def __init__(
        self,
        on_select: Callable[[Card], None],
        required_fields: list[str] | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_select = on_select
        self._required_fields = required_fields or []
        self.setStyleSheet("background: transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        lbl = QLabel("Проба")
        lbl.setStyleSheet(
            f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; font-weight: 500; background: transparent;"
        )
        lay.addWidget(lbl)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._combo = StyledComboBox(font_size=13)
        self._combo.setFixedHeight(36)
        self._combo.setFixedWidth(320)
        self._combo.setStyleSheet(combo_style())
        self._combo.currentIndexChanged.connect(self._on_changed)
        row.addWidget(self._combo)
        row.addStretch()

        lay.addLayout(row)
        self.reload()

    def _card_matches(self, card: Card) -> bool:
        return all(getattr(card, f, None) is not None for f in self._required_fields)

    def reload(self) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("— не выбрана —", userData=None)
        for card in get_all_cards():
            if self._card_matches(card):
                label = f"# {card.probe_number}  {card.culture_name}"
                self._combo.addItem(label, userData=card)
        self._combo.blockSignals(False)

    def _on_changed(self, index: int) -> None:
        card = self._combo.itemData(index)
        if card is not None:
            self._on_select(card)
