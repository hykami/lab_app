"""
Настройки — объединённая страница с pill-переключателем.
Вкладки: Основные | Нормы культур | Силоса | Бюксы | Персонал
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import QStackedWidget, QWidget
from PyQt6.QtGui import QShowEvent

from ui.pages.base_page import BasePage
from ui.animations import fade_in
from ui.components.type_pill_switcher import TypePillSwitcher
from ui.pages.settings.general    import GeneralSettingsPage
from ui.pages.settings.crop_norms import CropNormsPage
from ui.pages.settings.silos      import SilosPage
from ui.pages.settings.boxes      import BoxesPage
from ui.pages.settings.personnel  import PersonnelPage


_TABS = ["Основные", "Нормы культур", "Силоса", "Бюксы", "Персонал"]

_PAGE_CLASSES = {
    "Основные":      GeneralSettingsPage,
    "Нормы культур": CropNormsPage,
    "Силоса":        SilosPage,
    "Бюксы":         BoxesPage,
    "Персонал":      PersonnelPage,
}


class SettingsPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Настройки",
            subtitle="",
            section="Настройки",
            actions=[],
        )

        # Pill-переключатель в хедере
        self._pill = TypePillSwitcher(_TABS)
        self._pill.connect_changed(self._on_tab_changed)
        self.set_header_widget(self._pill)

        # Создаём все внутренние страницы
        self._inner_pages: dict[str, BasePage] = {}
        self._initialized: set[str] = set()

        # Стек вставляем напрямую в root layout (минуя scroll BasePage)
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        for tab in _TABS:
            page = _PAGE_CLASSES[tab]()
            # Скрываем хедер дочерней страницы, но сохраняем её action_buttons
            inner_layout = page.layout()
            if inner_layout and inner_layout.count() >= 1:
                hdr = inner_layout.itemAt(0).widget()
                if hdr:
                    hdr.hide()
            self._inner_pages[tab] = page
            self._stack.addWidget(page)

        # Контейнер для action-кнопок текущей вкладки в общем хедере
        from PyQt6.QtWidgets import QHBoxLayout
        self._actions_holder = QWidget()
        self._actions_holder.setStyleSheet("background: transparent;")
        self._actions_layout = QHBoxLayout(self._actions_holder)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(8)
        # Вставляем holder справа в хедер
        self._inject_actions_holder()

        # Удаляем scroll area BasePage и вставляем стек
        root_layout = self.layout()
        scroll_item = root_layout.itemAt(1)
        if scroll_item and scroll_item.widget():
            scroll_item.widget().hide()
            root_layout.removeWidget(scroll_item.widget())
        root_layout.addWidget(self._stack, 1)

        self._current_tab = _TABS[0]
        self._stack.setCurrentWidget(self._inner_pages[self._current_tab])
        self._show_inner_actions(self._current_tab)

    def _inject_actions_holder(self) -> None:
        """Вставляет контейнер для action-кнопок справа в хедер SettingsPage."""
        # Хедер SettingsPage — первый элемент root layout, у него HBoxLayout
        root = self.layout()
        if not root or root.count() == 0:
            return
        hdr = root.itemAt(0).widget()
        if not hdr:
            return
        hdr_lay = hdr.layout()
        if hdr_lay is None:
            return
        hdr_lay.addWidget(self._actions_holder)

    def _show_inner_actions(self, tab: str) -> None:
        """Показывает кнопки текущей внутренней страницы в общем хедере."""
        # Очищаем holder (не удаляя кнопки — они принадлежат дочерней странице)
        while self._actions_layout.count():
            item = self._actions_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        page = self._inner_pages.get(tab)
        if not page:
            return
        buttons = getattr(page, "_action_buttons", None)
        if not buttons:
            return
        for btn in buttons.values():
            btn.setParent(self._actions_holder)
            self._actions_layout.addWidget(btn)
            btn.show()

    def _on_tab_changed(self, idx: int, text: str) -> None:
        self._current_tab = text
        page = self._inner_pages[text]
        self._stack.setCurrentWidget(page)
        fade_in(page, duration=180)
        page.showEvent(QShowEvent())
        self._show_inner_actions(text)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        page = self._inner_pages.get(self._current_tab)
        if page:
            page.showEvent(QShowEvent())
