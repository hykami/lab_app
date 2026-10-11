"""
TypePillSwitcher — переключатель типа карточки в стиле Linear/Raycast.
Sliding pill анимация при переключении между вкладками.
"""
from __future__ import annotations
from typing import Callable, Optional

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty,
    QParallelAnimationGroup,
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QPushButton, QWidget,
)

from ui.theme import FONT_UI


class _Pill(QWidget):
    """Полупрозрачный слой-таблетка, скользящий за активным табом."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "_Pill {"
            "  background: #2e2a42;"
            "  border: 0.5px solid rgba(108,92,231,0.39);"
            "  border-radius: 6px;"
            "}"
        )
        self.hide()


class _PillTab(QPushButton):
    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
        )
        self._refresh()
        self.toggled.connect(lambda _: self._refresh())

    def _refresh(self):
        active = self.isChecked()
        color  = "#a29bfe" if active else "#606075"
        weight = "500" if active else "400"
        self.setStyleSheet(
            "QPushButton {"
            f"  background: transparent; border: none; padding: 0 11px;"
            f"  color: {color}; font-family: '{FONT_UI}', sans-serif;"
            f"  font-size: 11px; font-weight: {weight};"
            "}"
            "QPushButton:hover:!checked { color: #8a8a9a; }"
        )


class TypePillSwitcher(QWidget):
    """
    Контейнер с табами и анимированной таблеткой.
    Использование:
        sw = TypePillSwitcher(["Перегонка", "Входной контроль", ...])
        sw.currentChanged.connect(on_change)
    """

    def __init__(self, items: list[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items = items
        self._current_index = 0
        self._on_change: Callable[[int, str], None] | None = None

        self.setFixedHeight(32)
        self.setStyleSheet(
            "TypePillSwitcher {"
            "  background: #1a1a1e; border: 0.5px solid #2a2a30;"
            "  border-radius: 8px;"
            "}"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Pill — отдельный виджет под кнопками
        self._pill = _Pill(self)

        # Кнопки
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(1)

        self._buttons: list[_PillTab] = []
        for i, label in enumerate(items):
            btn = _PillTab(label)
            btn.clicked.connect(lambda _=False, idx=i: self._select(idx))
            lay.addWidget(btn)
            self._buttons.append(btn)

        if self._buttons:
            self._buttons[0].setChecked(True)

        # Анимация pill: pos + size одновременно
        self._pos_anim = QPropertyAnimation(self._pill, b"geometry")
        self._pos_anim.setDuration(220)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutQuart)

        # Init pill position after first show
        self._pill_initialized = False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._pill_initialized:
            self._pill.show()
            self._pill.lower()  # под кнопками
            self._move_pill_to(self._current_index, animate=False)
            self._pill_initialized = True

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._pill_initialized:
            self._move_pill_to(self._current_index, animate=False)

    def _move_pill_to(self, index: int, animate: bool = True):
        if index < 0 or index >= len(self._buttons):
            return
        btn = self._buttons[index]
        target = QRect(btn.x(), btn.y(), btn.width(), btn.height())

        if not animate:
            self._pill.setGeometry(target)
            return

        self._pos_anim.stop()
        self._pos_anim.setStartValue(self._pill.geometry())
        self._pos_anim.setEndValue(target)
        self._pos_anim.start()

    def _select(self, index: int):
        if index == self._current_index:
            return
        for i, b in enumerate(self._buttons):
            b.setChecked(i == index)
        self._current_index = index
        self._move_pill_to(index, animate=True)
        if self._on_change:
            self._on_change(index, self._items[index])

    # ── Public API ──────────────────────────────────────────────────────────────

    def connect_changed(self, cb: Callable[[int, str], None]):
        self._on_change = cb

    @property
    def current_text(self) -> str:
        return self._items[self._current_index]

    @property
    def current_index(self) -> int:
        return self._current_index

    def set_current_text(self, text: str, emit: bool = False):
        if text not in self._items:
            return
        idx = self._items.index(text)
        if idx == self._current_index and not emit:
            return
        for i, b in enumerate(self._buttons):
            b.setChecked(i == idx)
        self._current_index = idx
        self._move_pill_to(idx, animate=True)
        if emit and self._on_change:
            self._on_change(idx, self._items[idx])
