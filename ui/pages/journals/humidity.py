"""
Калькулятор влажности зерна.
"""

from __future__ import annotations

import random
from typing import Optional

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint
from ui.animations import animate_label_value, fade_in
from PyQt6.QtGui import QPainter, QColor, QPainterPath
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.theme import (
    BG_CARD, BORDER, TEXT_MAIN,
    TEXT_BRIGHT, TEXT_MUTED, ACCENT_ICON, FONT_MONO, FONT_UI,
)
from ui.style_helpers import combo_style
from ui.components.styled_combo import StyledComboBox
from logic.calculators import calc_humidity, HumidityResult
from logic.db_service import get_all_boxes, get_boxes_by_type
from ui.components.probe_selector import ProbeSelector
from ui.validators import attach_numeric_validators


# ── Виджет выбора бюксы ───────────────────────────────────────────────────────



# ── iOS-style toggle switch ────────────────────────────────────────────────────

class _IOSToggle(QWidget):
    """Переключатель в стиле macOS/iOS с плавной анимацией."""

    def __init__(self, label: str = "", on_changed=None,
                 parent=None) -> None:
        super().__init__(parent)
        self._checked = False
        self._on_changed = on_changed
        self._label_text = label

        self._track_w = 40
        self._track_h = 22
        self._thumb_d = 16
        self._margin  = 3

        # Анимируем позицию X большого пальца (0.0 → 1.0)
        self._anim_val = 0.0
        self._anim = QPropertyAnimation(self, b"_pos")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        # Минимальный размер виджета = переключатель + отступ + текст
        fm_w = 90 if label else 0
        self.setFixedSize(self._track_w + (8 + fm_w if label else 0),
                          max(self._track_h, 20))

    # ── Qt property для анимации ───────────────────────────────────────────

    def _get_pos(self) -> float:
        return self._anim_val

    def _set_pos(self, v: float) -> None:
        self._anim_val = v
        self.update()

    _pos = pyqtProperty(float, _get_pos, _set_pos)

    # ── Отрисовка ─────────────────────────────────────────────────────────

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Дорожка
        track_x = 0
        track_y = (self.height() - self._track_h) // 2
        track_rect = (track_x, track_y, self._track_w, self._track_h)

        path = QPainterPath()
        path.addRoundedRect(*[float(v) for v in track_rect],
                            self._track_h / 2, self._track_h / 2)

        # Цвет дорожки: серый → зелёный
        t = self._anim_val
        off_r, off_g, off_b = 45, 45, 52
        on_r,  on_g,  on_b  = 52, 211, 153   # #34d399
        r = int(off_r + (on_r  - off_r) * t)
        g = int(off_g + (on_g  - off_g) * t)
        b = int(off_b + (on_b  - off_b) * t)
        p.fillPath(path, QColor(r, g, b))

        # Тонкая рамка дорожки
        from PyQt6.QtGui import QPen
        pen = QPen(QColor(255, 255, 255, 18))
        pen.setWidthF(0.8)
        p.setPen(pen)
        p.drawPath(path)

        # Ползунок (thumb)
        travel = self._track_w - self._thumb_d - self._margin * 2
        thumb_x = track_x + self._margin + travel * self._anim_val
        thumb_y = track_y + self._margin
        thumb_path = QPainterPath()
        thumb_path.addEllipse(thumb_x, float(thumb_y),
                              float(self._thumb_d), float(self._thumb_d))
        # Тень
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(thumb_path, QColor(0, 0, 0, 40))
        # Белый круг
        thumb_path2 = QPainterPath()
        thumb_path2.addEllipse(thumb_x, float(thumb_y),
                               float(self._thumb_d), float(self._thumb_d))
        p.fillPath(thumb_path2, QColor(255, 255, 255, 248))

        # Текст подписи
        if self._label_text:
            p.setPen(QColor(160, 160, 176))
            from PyQt6.QtGui import QFont
            font = QFont("Segoe UI", 12)
            p.setFont(font)
            text_x = self._track_w + 8
            p.drawText(text_x, 0, self.width() - text_x, self.height(),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self._label_text)
        p.end()

    # ── Взаимодействие ────────────────────────────────────────────────────

    def mousePressEvent(self, _e):
        self.setChecked(not self._checked)

    def setChecked(self, checked: bool) -> None:
        self._checked = checked
        self._anim.stop()
        self._anim.setStartValue(self._anim_val)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()
        if self._on_changed:
            self._on_changed(checked)

    def isChecked(self) -> bool:
        return self._checked


class BoxSelector(QWidget):
    """Метка + выпадающий список бюкс."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; font-weight: 500; background: transparent;"
        )
        lay.addWidget(lbl)

        self._combo = StyledComboBox(font_size=12)
        self._combo.setFixedHeight(36)
        self._combo.setStyleSheet(combo_style(font_size=12))
        lay.addWidget(self._combo)

    def populate(self, boxes: list) -> None:
        self._combo.clear()
        self._combo.addItem("Случайная", userData=None)
        for box in boxes:
            self._combo.addItem(f"№ {box.number}  ({box.weight:.2f} г)", userData=box)

    @property
    def selected_box(self):
        """Возвращает выбранную бюксу или None (случайная)."""
        return self._combo.currentData()

# ── Карточка результата бюксы ─────────────────────────────────────────────────

class BoxResultCard(QFrame):
    """
    Показывает m, m1, m2 и W для одной бюксы.
    """

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 0.5px solid {BORDER};
                border-radius: 10px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)

        # Заголовок
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)

        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(
            f"color: #333; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()

        self._box_badge = QLabel("—")
        self._box_badge.setStyleSheet(
            f"color: {ACCENT_ICON}; background: rgba(108,92,231,0.1);"
            f"border: 0.5px solid rgba(108,92,231,0.25); border-radius: 4px;"
            f"font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 2px 8px;"
        )
        hdr.addWidget(self._box_badge)
        lay.addLayout(hdr)

        # Сетка значений
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        self._fields: dict[str, QLabel] = {}
        rows = [
            ("m",  "Масса бюксы, г"),
            ("m1", "До сушки, г"),
            ("m2", "После сушки, г"),
            ("w",  "Влажность, %"),
        ]
        for i, (key, label) in enumerate(rows):
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent; border: none;"
            )
            grid.addWidget(name_lbl, i, 0)

            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            is_result = key in ("m2", "w")
            val_lbl.setStyleSheet(
                f"color: {'#4ade80' if is_result else TEXT_MUTED};"
                f"font-family: '{FONT_UI}', sans-serif;"
                f"font-size: {'15px' if is_result else '13px'};"
                f"font-weight: {'300' if is_result else '400'};"
                "background: transparent; border: none;"
            )
            grid.addWidget(val_lbl, i, 1)
            self._fields[key] = val_lbl

        lay.addLayout(grid)

    def update_result(self, box_number: str, m: float, m1: float, m2: float, w: float) -> None:
        self._box_badge.setText(f"№ {box_number}")
        animate_label_value(self._fields["m"],  f"{m:.2f}")
        animate_label_value(self._fields["m1"], f"{m1:.2f}")
        animate_label_value(self._fields["m2"], f"{m2:.2f}", duration=280)
        animate_label_value(self._fields["w"],  f"{w:.1f} %", duration=300)

    def clear(self) -> None:
        self._box_badge.setText("—")
        for lbl in self._fields.values():
            lbl.setText("—")


# ── Страница Влажность ────────────────────────────────────────────────────────

class HumidityPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Влажность",
            subtitle="",
            section="Журналы",
            actions=[("Очистить", False), ("Рассчитать", True)],
        )
        self._action_buttons["Рассчитать"].clicked.connect(self._on_calculate)
        self._action_buttons["Очистить"].clicked.connect(self._on_clear)
        self._build_ui()
        # Валидация подключается после _build_ui (нужны и поле и кнопка)
        attach_numeric_validators(
            [(self._w_input, False)],
            calc_btn=self._action_buttons["Рассчитать"],
        )

    def _build_ui(self) -> None:
        # Убираем stretch
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # ── Выбор пробы ───────────────────────────────────────────────────────
        self._probe_selector = ProbeSelector(
            on_select=self._on_probe_selected,
            required_fields=["humidity"],
        )
        self._content_layout.addWidget(self._probe_selector)

        # ── Ввод влажности ────────────────────────────────────────────────────
        self._mesh_mode = False

        w_block = QWidget()
        w_block.setStyleSheet("background: transparent;")
        w_lay = QVBoxLayout(w_block)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.setSpacing(5)

        w_lbl = QLabel("Влажность, %")
        w_lbl.setStyleSheet(
            f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; font-weight: 500; background: transparent;"
        )
        w_lay.addWidget(w_lbl)

        inp_row = QHBoxLayout()
        inp_row.setSpacing(10)
        inp_row.setContentsMargins(0, 0, 0, 0)

        self._w_input = QLineEdit()
        self._w_input.setPlaceholderText("например 12.7")
        self._w_input.setFixedHeight(36)
        self._w_input.setFixedWidth(160)
        self._w_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_CARD};
                border: 0.5px solid {BORDER};
                border-radius: 7px;
                color: {TEXT_MAIN};
                font-family: '{FONT_MONO}', monospace;
                font-size: 14px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{
                border-color: rgba(108,92,231,0.5);
                color: {TEXT_BRIGHT};
            }}
        """)
        self._w_input.returnPressed.connect(self._on_calculate)
        inp_row.addWidget(self._w_input)

        # Переключатель «При подработке» — iOS-style toggle
        toggle_wrap = QWidget()
        toggle_wrap.setStyleSheet("background: transparent;")
        tw_lay = QHBoxLayout(toggle_wrap)
        tw_lay.setContentsMargins(0, 0, 0, 0)
        tw_lay.setSpacing(8)
        self._mesh_toggle = _IOSToggle(
            label="При подработке",
            on_changed=self._on_mesh_toggled,
        )
        self._mesh_toggle.setFixedWidth(180)
        tw_lay.addWidget(self._mesh_toggle)
        tw_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        inp_row.addWidget(toggle_wrap)

        inp_row.addStretch()
        w_lay.addLayout(inp_row)

        self._content_layout.addWidget(w_block)

        # ── Выбор бюкс ────────────────────────────────────────────────────────
        boxes_row = QHBoxLayout()
        boxes_row.setSpacing(16)
        boxes_row.setContentsMargins(0, 0, 0, 0)

        self._box1_sel = BoxSelector("Бюкса 1")
        self._box2_sel = BoxSelector("Бюкса 2")
        boxes_row.addWidget(self._box1_sel)
        boxes_row.addWidget(self._box2_sel)
        boxes_row.addStretch()

        boxes_widget = QWidget()
        boxes_widget.setStyleSheet("background: transparent;")
        boxes_widget.setLayout(boxes_row)
        self._content_layout.addWidget(boxes_widget)

        self._reload_boxes()

        # ── Карточки результатов ──────────────────────────────────────────────
        results_row = QHBoxLayout()
        results_row.setSpacing(12)
        results_row.setContentsMargins(0, 0, 0, 0)

        self._card1 = BoxResultCard("Бюкса 1")
        self._card2 = BoxResultCard("Бюкса 2")
        results_row.addWidget(self._card1)
        results_row.addWidget(self._card2)

        results_widget = QWidget()
        results_widget.setStyleSheet("background: transparent;")
        results_widget.setLayout(results_row)
        self._content_layout.addWidget(results_widget)

        # ── Подсказка ─────────────────────────────────────────────────────────
        self._content_layout.addStretch()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, '_probe_selector'):
            self._probe_selector.reload()
        if hasattr(self, '_box1_sel'):
            self._reload_boxes()

    def _on_mesh_toggled(self, checked: bool) -> None:
        self._mesh_mode = checked
        self._reload_boxes()

    def _reload_boxes(self) -> None:
        if self._mesh_mode:
            boxes = get_boxes_by_type("mesh")
        else:
            boxes = get_all_boxes()
        self._box1_sel.populate(boxes)
        self._box2_sel.populate(boxes)
        self._all_boxes = boxes

    def _on_probe_selected(self, card) -> None:
        """Заполняет поле влажности из выбранной карточки."""
        if card.humidity is not None:
            self._w_input.setText(str(card.humidity))

    def _on_calculate(self) -> None:
        # Читаем влажность
        try:
            w = float(self._w_input.text().replace(",", "."))
        except ValueError:
            self._w_input.setStyleSheet(
                self._w_input.styleSheet().replace(BORDER, "rgba(248,113,113,0.5)")
            )
            return

        if not self._all_boxes:
            return

        # Определяем бюксы
        b1 = self._box1_sel.selected_box
        b2 = self._box2_sel.selected_box

        # Случайный выбор если не выбрана
        pool = list(self._all_boxes)
        if b1 is None and b2 is None:
            chosen = random.sample(pool, min(2, len(pool)))
            b1 = chosen[0]
            b2 = chosen[1] if len(chosen) > 1 else chosen[0]
        elif b1 is None:
            remaining = [b for b in pool if b.id != b2.id]
            b1 = random.choice(remaining) if remaining else b2
        elif b2 is None:
            remaining = [b for b in pool if b.id != b1.id]
            b2 = random.choice(remaining) if remaining else b1

        # Расчёт
        result: HumidityResult = calc_humidity(
            w_input=w,
            box1_number=b1.number, box1_mass=b1.weight,
            box2_number=b2.number, box2_mass=b2.weight,
        )

        # Обновляем карточки
        self._card1.update_result(
            result.box1.box_number,
            result.box1.m, result.box1.m1,
            result.box1.m2, result.box1.w,
        )
        self._card2.update_result(
            result.box2.box_number,
            result.box2.m, result.box2.m1,
            result.box2.m2, result.box2.w,
        )

    def _on_clear(self) -> None:
        self._w_input.clear()
        self._card1.clear()
        self._card2.clear()
        self._reload_boxes()
