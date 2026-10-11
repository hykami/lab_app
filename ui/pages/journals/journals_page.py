"""
Журналы — объединённая страница с pill-переключателем.
Вкладки: Влажность | Число падения | Клейковина
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from ui.pages.base_page import BasePage
from ui.animations import fade_in
from ui.components.type_pill_switcher import TypePillSwitcher
from ui.pages.journals.humidity    import HumidityPage
from ui.pages.journals.fall_number import FallNumberPage
from ui.pages.journals.gluten      import GlutenPage


_TABS = ["Влажность", "Число падения", "Клейковина"]


class JournalsPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Журналы",
            subtitle="",
            section="Журналы",
            actions=[("Очистить", False), ("Рассчитать", True)],
        )

        # Pill-переключатель в хедере
        self._pill = TypePillSwitcher(_TABS)
        self._pill.connect_changed(self._on_tab_changed)
        self.set_header_widget(self._pill)

        # Создаём три внутренние страницы
        self._inner_pages: dict[str, BasePage] = {
            "Влажность":     HumidityPage(),
            "Число падения": FallNumberPage(),
            "Клейковина":    GlutenPage(),
        }

        # Прячем их заголовки — оставляем только scroll-контент
        for page in self._inner_pages.values():
            inner_layout = page.layout()
            if inner_layout and inner_layout.count() >= 1:
                hdr = inner_layout.itemAt(0).widget()
                if hdr:
                    hdr.hide()

        # Стек вставляем в root layout (обходя content scroll)
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        for page in self._inner_pages.values():
            self._stack.addWidget(page)

        # Вставляем стек напрямую в корневой layout (индекс 1, вместо scroll)
        root_layout = self.layout()
        # Удаляем scroll area BasePage (индекс 1)
        scroll_item = root_layout.itemAt(1)
        if scroll_item and scroll_item.widget():
            scroll_item.widget().hide()
            root_layout.removeWidget(scroll_item.widget())
        root_layout.addWidget(self._stack, 1)

        # Подключаем кнопки
        self._action_buttons["Рассчитать"].clicked.connect(self._on_calculate)
        self._action_buttons["Очистить"].clicked.connect(self._on_clear)

        self._current_tab = _TABS[0]
        self._stack.setCurrentWidget(self._inner_pages[self._current_tab])

    def _on_tab_changed(self, _idx: int, text: str) -> None:
        self._current_tab = text
        page = self._inner_pages[text]
        self._stack.setCurrentWidget(page)
        fade_in(page, duration=180)
        if hasattr(page, "_probe_selector"):
            page._probe_selector.reload()
        if hasattr(page, "_reload_boxes"):
            page._reload_boxes()

    def _on_calculate(self) -> None:
        page = self._inner_pages[self._current_tab]
        if hasattr(page, "_on_calculate"):
            page._on_calculate()

    def _on_clear(self) -> None:
        page = self._inner_pages[self._current_tab]
        if hasattr(page, "_on_clear"):
            page._on_clear()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        page = self._inner_pages[self._current_tab]
        if hasattr(page, "_probe_selector"):
            page._probe_selector.reload()
        if hasattr(page, "_reload_boxes"):
            page._reload_boxes()
