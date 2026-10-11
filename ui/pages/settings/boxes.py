"""
Настройки → Бюксы.
Два типа бюкс: стандартные и сетчатые.
"""

from __future__ import annotations
import logging
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.style_helpers import scroll_style
from ui.theme import (
    BG_CARD, BORDER,
    TEXT_MAIN, TEXT_BRIGHT, TEXT_MUTED,
    ACCENT_V, FONT_MONO, FONT_UI,
)
from logic.db_service import Box, get_boxes_by_type, save_box, add_box, delete_box

logger = logging.getLogger(__name__)

COLS = 4


# ── Карточка существующей бюксы ───────────────────────────────────────────────

class BoxCard(QFrame):
    """Карточка существующей бюксы: номер фиксирован, масса редактируется."""

    def __init__(self, box: Box, on_delete: callable,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._box = box
        self._on_delete = on_delete

        self.setFixedSize(80, 80)
        self.setStyleSheet(
            f"QFrame {{ background: #111114; border: 0.5px solid {BORDER}; border-radius: 8px; }}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(4)

        # Шапка: номер + кнопка удаления
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(2)

        num_lbl = QLabel(f"# {box.number}")
        num_lbl.setStyleSheet(
            f"color: {ACCENT_V}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; background: transparent; border: none;"
        )
        top.addWidget(num_lbl, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(16, 16)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            " color: #4a4a58; font-size: 11px; border-radius: 3px; }"
            "QPushButton:hover { color: #f87171; background: rgba(248,113,113,0.1); }"
        )
        del_btn.clicked.connect(self._confirm_delete)
        top.addWidget(del_btn)
        lay.addLayout(top)

        # Поле редактирования массы
        self._weight_inp = QLineEdit(f"{box.weight:.2f}")
        self._weight_inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_inp.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none;"
            f" color: {TEXT_BRIGHT}; font-family: '{FONT_MONO}', monospace;"
            "font-size: 15px; font-weight: 300; }"
            "QLineEdit:focus { background: rgba(108,92,231,0.06);"
            " border: 0.5px solid rgba(108,92,231,0.4); border-radius: 5px; }"
        )
        self._weight_inp.editingFinished.connect(self._on_weight_changed)
        lay.addWidget(self._weight_inp)

        lbl = QLabel("масса, г")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        lay.addWidget(lbl)

    def _on_weight_changed(self) -> None:
        text = self._weight_inp.text().replace(",", ".")
        try:
            val = float(text)
        except ValueError:
            self._weight_inp.setText(f"{self._box.weight:.2f}")
            return
        if abs(val - self._box.weight) < 1e-9:
            return
        self._box.weight = round(val, 2)
        try:
            save_box(self._box)
            self._flash_saved()
        except Exception:
            logger.exception("Не удалось сохранить бюксу #%s", self._box.number)

    def _flash_saved(self) -> None:
        orig = self.styleSheet()
        self.setStyleSheet(
            "QFrame { background: rgba(74,222,128,0.08);"
            " border: 0.5px solid rgba(74,222,128,0.4); border-radius: 8px; }"
        )
        QTimer.singleShot(800, lambda: self.setStyleSheet(orig))

    def _confirm_delete(self) -> None:
        reply = QMessageBox.question(
            self, "Удалить бюксу",
            f"Удалить бюксу № {self._box.number}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_box(self._box.id)
            self._on_delete()


# ── Поле ввода с подсветкой карточки ─────────────────────────────────────────

class _FocusLineEdit(QLineEdit):
    """QLineEdit который уведомляет карточку о фокусе через колбэки."""

    def __init__(self, on_focus_in: callable, on_focus_out: callable,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._on_focus_in = on_focus_in
        self._on_focus_out = on_focus_out

    def focusInEvent(self, event) -> None:
        self._on_focus_in()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self._on_focus_out()
        super().focusOutEvent(event)


# ── Карточка добавления новой бюксы ──────────────────────────────────────────

class AddBoxCard(QFrame):
    """Пустая карточка с полями ввода номера и массы для создания новой бюксы."""

    def __init__(self, box_type: str, on_added: callable,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._box_type = box_type
        self._on_added = on_added

        self.setFixedSize(80, 80)
        self._apply_idle_style()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        inp_style = (
            f"QLineEdit {{ background: #0e0e10; border: 0.5px solid {BORDER};"
            f" border-radius: 5px; color: {TEXT_MAIN};"
            f" font-family: '{FONT_MONO}', monospace; font-size: 11px; padding: 2px 4px; }}"
            "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
        )

        self._num_inp = _FocusLineEdit(self._apply_focus_style, self._apply_idle_style)
        self._num_inp.setPlaceholderText("№")
        self._num_inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._num_inp.setStyleSheet(inp_style)
        self._num_inp.returnPressed.connect(self._try_save)
        lay.addWidget(self._num_inp)

        self._weight_inp = _FocusLineEdit(self._apply_focus_style, self._apply_idle_style)
        self._weight_inp.setPlaceholderText("масса, г")
        self._weight_inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_inp.setStyleSheet(inp_style)
        self._weight_inp.returnPressed.connect(self._try_save)
        lay.addWidget(self._weight_inp)

        save_btn = QPushButton("✓")
        save_btn.setFixedHeight(22)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(
            "QPushButton { background: rgba(74,222,128,0.12);"
            " border: 0.5px solid rgba(74,222,128,0.35); border-radius: 5px;"
            " color: #4ade80; font-size: 13px; }"
            "QPushButton:hover { background: rgba(74,222,128,0.22); }"
        )
        save_btn.clicked.connect(self._try_save)
        lay.addWidget(save_btn)

    def _apply_idle_style(self) -> None:
        self.setStyleSheet(
            f"QFrame {{ background: #111114; border: 0.5px dashed {BORDER}; border-radius: 8px; }}"
        )

    def _apply_focus_style(self) -> None:
        self.setStyleSheet(
            "QFrame { background: rgba(108,92,231,0.06);"
            " border: 0.5px dashed rgba(108,92,231,0.5); border-radius: 8px; }"
        )

    def _try_save(self) -> None:
        number = self._num_inp.text().strip()
        weight_text = self._weight_inp.text().strip().replace(",", ".")

        if not number and not weight_text:
            return

        if not number:
            QMessageBox.warning(self, "Ошибка", "Введите номер бюксы.")
            self._num_inp.setFocus()
            return

        if not weight_text:
            QMessageBox.warning(self, "Ошибка", "Введите массу бюксы.")
            self._weight_inp.setFocus()
            return

        try:
            weight = float(weight_text)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Масса должна быть числом.")
            self._weight_inp.setFocus()
            return

        try:
            add_box(number, round(weight, 2), self._box_type)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось добавить бюксу: {e}")
            return

        # Откладываем на следующий цикл событий — иначе Qt падает при вызове
        # reload() прямо во время обработки returnPressed (виджет уничтожается
        # пока стек вызова события ещё не завершён).
        QTimer.singleShot(0, self._on_added)


# ── Группа бюкс ───────────────────────────────────────────────────────────────

class _BoxGroup(QFrame):
    """Рамка с заголовком и сеткой карточек бюкс."""

    def __init__(self, title: str, box_type: str, on_change: callable,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._box_type = box_type
        self._on_change = on_change

        self.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Заголовок рамки
        hdr = QWidget()
        hdr.setObjectName("boxGroupHdr")
        hdr.setStyleSheet(
            "QWidget#boxGroupHdr { background: rgba(108,92,231,0.06);"
            f" border-radius: 10px 10px 0 0; border-bottom: 0.5px solid {BORDER}; }}"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 8, 12, 8)
        t = QLabel(title)
        t.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 13px; font-weight: 600; background: transparent; border: none;"
        )
        hl.addWidget(t)
        hl.addStretch()
        outer.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_style())
        self._inner = QWidget()
        self._inner.setStyleSheet(f"background: {BG_CARD};")
        self._grid_lay = QVBoxLayout(self._inner)
        self._grid_lay.setContentsMargins(10, 10, 10, 10)
        self._grid_lay.setSpacing(0)
        scroll.setWidget(self._inner)
        outer.addWidget(scroll)

        self.reload()

    def reload(self) -> None:
        while self._grid_lay.count():
            item = self._grid_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        boxes = get_boxes_by_type(self._box_type)

        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)

        for i, box in enumerate(boxes):
            row, col = divmod(i, COLS)
            grid.addWidget(BoxCard(box, on_delete=self._on_change), row, col)

        add_row, add_col = divmod(len(boxes), COLS)
        grid.addWidget(AddBoxCard(self._box_type, on_added=self._on_change), add_row, add_col)

        self._grid_lay.addWidget(grid_w)
        self._grid_lay.addStretch()


# ── Страница ──────────────────────────────────────────────────────────────────

class BoxesPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Бюксы",
            subtitle="",
            section="Настройки",
            actions=[],
        )
        self._build_ui()

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Компактные отступы для страницы бюкс
        self._content_layout.setContentsMargins(4, 8, 4, 8)

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        self._std_group  = _BoxGroup("Бюксы",          "standard", self._reload)
        self._mesh_group = _BoxGroup("Сетчатые бюксы", "mesh",     self._reload)

        rl.addWidget(self._std_group,  1)
        rl.addWidget(self._mesh_group, 1)

        self._content_layout.addWidget(row)

    def _reload(self) -> None:
        self._std_group.reload()
        self._mesh_group.reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reload()
