"""
Калькулятор числа падения.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from ui.animations import animate_label_value, fade_in
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)

from ui.style_helpers import input_style
from ui.pages.base_page import BasePage
from ui.theme import (
    BG_CARD, BORDER, TEXT_MUTED,
    ACCENT_G, ACCENT_R, FONT_MONO,
    FONT_UI,
)
from logic.fall_number_calc import calc_fall_number, FallNumberResult
from ui.components.probe_selector import ProbeSelector
from ui.validators import attach_numeric_validators


# ── Поле ввода с меткой ───────────────────────────────────────────────────────

class _InputField(QWidget):
    def __init__(self, label: str, placeholder: str = "",
                 parent: Optional[QWidget] = None) -> None:
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

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setFixedHeight(36)
        self.input.setStyleSheet(input_style())
        lay.addWidget(self.input)

    @property
    def value(self) -> str:
        return self.input.text().strip()

    def clear(self) -> None:
        self.input.clear()


# ── Карточка результатов ──────────────────────────────────────────────────────

class ResultsCard(QFrame):
    """Карточка с результатами расчёта — две колонки."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 0.5px solid {BORDER};
                border-radius: 10px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Заголовок ─────────────────────────────────────────────────────────
        hdr_w = QWidget()
        hdr_w.setStyleSheet(
            f"background: transparent; border-bottom: 0.5px solid {BORDER}; border-radius: 0;"
        )
        hdr_l = QHBoxLayout(hdr_w)
        hdr_l.setContentsMargins(14, 9, 14, 9)
        hdr_l.setSpacing(6)

        dot = QWidget(); dot.setFixedSize(5, 5)
        dot.setStyleSheet("background: #6c5ce7; border-radius: 2px; border: none;")
        hdr_l.addWidget(dot)

        hdr_lbl = QLabel("РЕЗУЛЬТАТЫ")
        hdr_lbl.setStyleSheet(
            f"color: #6c5ce7; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        hdr_l.addWidget(hdr_lbl)
        hdr_l.addStretch()
        lay.addWidget(hdr_w)

        # ── Тело: две колонки ─────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Левая колонка — параметры
        left_w = QWidget(); left_w.setStyleSheet("background: transparent; border: none;")
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(18, 14, 18, 16)
        left_l.setSpacing(10)

        left_title = QLabel("ПАРАМЕТРЫ")
        left_title.setStyleSheet(
            f"color: #2a2a4e; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        left_l.addWidget(left_title)

        self._rows: dict[str, QLabel] = {}
        for key, label in [("naveski", "Масса навески"), ("div", "Расхождение")]:
            row = QWidget(); row.setStyleSheet("background: transparent; border: none;")
            rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
            k = QLabel(label)
            k.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            v = QLabel("—")
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v.setStyleSheet(
                f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 13px; background: transparent; border: none;"
            )
            rl.addWidget(k); rl.addStretch(); rl.addWidget(v)
            left_l.addWidget(row)
            self._rows[key] = v

        left_l.addStretch()
        body.addWidget(left_w, 1)

        # Разделитель
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"background: {BORDER}; border: none; max-width: 1px;")
        body.addWidget(div)

        # Правая колонка — значения ЧП
        right_w = QWidget(); right_w.setStyleSheet("background: transparent; border: none;")
        right_l = QVBoxLayout(right_w)
        right_l.setContentsMargins(18, 14, 18, 16)
        right_l.setSpacing(10)

        right_title = QLabel("ЗНАЧЕНИЯ ЧП")
        right_title.setStyleSheet(
            f"color: #2a2a4e; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        right_l.addWidget(right_title)

        for key, label in [("fp1", "ЧП₁"), ("fp2", "ЧП₂")]:
            row = QWidget(); row.setStyleSheet("background: transparent; border: none;")
            rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
            k = QLabel(label)
            k.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            v = QLabel("—")
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v.setStyleSheet(
                f"color: {ACCENT_G}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 22px; font-weight: 300; background: transparent; border: none;"
            )
            rl.addWidget(k); rl.addStretch(); rl.addWidget(v)
            right_l.addWidget(row)
            self._rows[key] = v

        right_l.addStretch()
        body.addWidget(right_w, 1)

        body_w = QWidget(); body_w.setStyleSheet("background: transparent; border: none;")
        body_w.setLayout(body)
        lay.addWidget(body_w)

    def update(self, result: FallNumberResult) -> None:
        naveski_text = (
            f"{result.naveski:.2f} г"
            if result.naveski is not None
            else "вне диапазона таблицы"
        )
        naveski_color = TEXT_MUTED if result.naveski is not None else ACCENT_R

        animate_label_value(self._rows["naveski"], naveski_text)
        self._rows["naveski"].setStyleSheet(
            self._rows["naveski"].styleSheet().replace(TEXT_MUTED, naveski_color)
        )
        animate_label_value(self._rows["div"], str(result.divergence))
        animate_label_value(self._rows["fp1"], str(int(round(result.fp1))), duration=280)
        animate_label_value(self._rows["fp2"], str(int(round(result.fp2))), duration=300)

    def clear(self) -> None:
        for lbl in self._rows.values():
            lbl.setText("—")


# ── Страница Число падения ────────────────────────────────────────────────────

class FallNumberPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Число падения",
            subtitle="",
            section="Журналы",
            actions=[("Очистить", False), ("Рассчитать", True)],
        )
        self._action_buttons["Рассчитать"].clicked.connect(self._on_calculate)
        self._action_buttons["Очистить"].clicked.connect(self._on_clear)
        self._build_ui()
        # Влажность — дробное, ЧП — только целое
        attach_numeric_validators(
            [
                (self._humidity_inp.input, False),
                (self._fp_inp.input,       True),
            ],
            calc_btn=self._action_buttons["Рассчитать"],
        )

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # ── Выбор пробы ───────────────────────────────────────────────────────
        self._probe_selector = ProbeSelector(
            on_select=self._on_probe_selected,
            required_fields=["fall_number"],
        )
        self._content_layout.addWidget(self._probe_selector)

        # ── Поля ввода ────────────────────────────────────────────────────────
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(16)
        inputs_row.setContentsMargins(0, 0, 0, 0)

        self._humidity_inp = _InputField("Влажность, %", "например 12.5")
        self._fp_inp = _InputField("Число падения, с", "например 280")

        self._humidity_inp.input.returnPressed.connect(self._on_calculate)
        self._fp_inp.input.returnPressed.connect(self._on_calculate)

        inputs_row.addWidget(self._humidity_inp)
        inputs_row.addWidget(self._fp_inp)
        inputs_row.addStretch()

        inputs_widget = QWidget()
        inputs_widget.setStyleSheet("background: transparent;")
        inputs_widget.setLayout(inputs_row)
        self._content_layout.addWidget(inputs_widget)

        # ── Карточка результатов ──────────────────────────────────────────────
        self._results_card = ResultsCard()
        self._content_layout.addWidget(self._results_card)

        # ── Подсказка ─────────────────────────────────────────────────────────
        self._content_layout.addStretch()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, '_probe_selector'):
            self._probe_selector.reload()

    def _on_probe_selected(self, card) -> None:
        """Заполняет влажность и ЧП из карточки."""
        if card.humidity is not None:
            self._humidity_inp.input.setText(str(card.humidity))
        if card.fall_number is not None:
            self._fp_inp.input.setText(str(int(card.fall_number)))

    def _on_calculate(self) -> None:
        # Читаем влажность
        try:
            humidity = float(self._humidity_inp.value.replace(",", "."))
        except ValueError:
            self._humidity_inp.input.setStyleSheet(
                self._humidity_inp.input.styleSheet().replace(
                    BORDER, "rgba(248,113,113,0.5)"
                )
            )
            return

        # Читаем ЧП
        try:
            fall_number = float(self._fp_inp.value.replace(",", "."))
        except ValueError:
            self._fp_inp.input.setStyleSheet(
                self._fp_inp.input.styleSheet().replace(
                    BORDER, "rgba(248,113,113,0.5)"
                )
            )
            return

        result = calc_fall_number(humidity, fall_number)
        self._results_card.update(result)

    def _on_clear(self) -> None:
        self._humidity_inp.clear()
        self._fp_inp.clear()
        self._results_card.clear()
