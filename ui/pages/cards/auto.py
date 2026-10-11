"""
Автоматически — страница.
Функционал будет добавлен при разработке соответствующего раздела.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from ui.pages.base_page import BasePage
from ui.theme import FONT_UI


class CardsAutoPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            title="Автоматически",
            subtitle="Автоматическая генерация карточки",
            section="Карточки",
            actions=[("Сбросить", False), ("Создать", True)],
        )
        # Функционал в разработке — отключаем нерабочие кнопки
        for btn in self._action_buttons.values():
            btn.setEnabled(False)

        placeholder = QLabel("Раздел в разработке")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 14px; background: transparent; padding: 40px;"
        )
        self._content_layout.addWidget(placeholder)
        self._content_layout.addStretch()
