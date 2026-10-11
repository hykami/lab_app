"""
Калькулятор клейковины и ИДК.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt
from ui.animations import animate_label_value, fade_in
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ui.style_helpers import input_style
from ui.pages.base_page import BasePage
from ui.theme import (
    BG_CARD, BORDER, TEXT_MUTED,
    ACCENT_G, ACCENT_ICON, FONT_MONO,
    FONT_UI,
)
from logic.gluten_calc import calc_gluten, GlutenResult, GlutenCalc, IdkCalc
from ui.components.probe_selector import ProbeSelector
from ui.validators import attach_numeric_validators


# ── Поле ввода с меткой ───────────────────────────────────────────────────────

class _Field(QWidget):
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


# ── Строка значения ───────────────────────────────────────────────────────────

def _val_row(label: str, big: bool = True) -> tuple[QWidget, QLabel]:
    """Возвращает виджет строки и QLabel значения."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 3, 0, 3)

    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
        "font-size: 12px; background: transparent; border: none;"
    )
    lay.addWidget(lbl)
    lay.addStretch()

    val = QLabel("—")
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if big:
        val.setStyleSheet(
            f"color: {ACCENT_G}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 22px; font-weight: 300; background: transparent; border: none;"
        )
    else:
        val.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 13px; background: transparent; border: none;"
        )
    lay.addWidget(val)
    return w, val


def _mini_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
        "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
    )
    return lbl


# ── Блок клейковины (оба расчёта) ─────────────────────────────────────────────

class GlutenBlock(QFrame):
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

        # Заголовок
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background: rgba(108,92,231,0.05); border-radius: 10px 10px 0 0;"
            f"border-bottom: 0.5px solid {BORDER};"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(6)
        dot = QWidget(); dot.setFixedSize(5, 5)
        dot.setStyleSheet("background: #6c5ce7; border-radius: 2px; border: none;")
        hl.addWidget(dot)
        title = QLabel("КЛЕЙКОВИНА")
        title.setStyleSheet(
            f"color: #6c5ce7; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        hl.addWidget(title)
        hl.addStretch()
        lay.addWidget(hdr)

        # Тело — три строки v3/v2/v1, два значения в каждой
        self._vals: list[list[QLabel]] = [[], []]
        for i, label in enumerate(("v3", "v2", "v1")):
            row_w = QWidget()
            is_last = (i == 2)
            row_w.setStyleSheet(
                "background: transparent; border: none;" +
                ("" if is_last else f"border-bottom: 0.5px solid {BORDER};")
            )
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(14, 10, 14, 10)
            rl.setSpacing(0)

            name = QLabel(label)
            name.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            rl.addWidget(name)
            rl.addStretch()

            for calc_idx in range(2):
                val = QLabel("—")
                val.setFixedWidth(90)
                val.setAlignment(Qt.AlignmentFlag.AlignCenter)
                val.setStyleSheet(
                    f"color: {ACCENT_G}; font-family: '{FONT_UI}', sans-serif;"
                    "font-size: 18px; font-weight: 500; background: transparent; border: none;"
                )
                rl.addWidget(val)
                self._vals[calc_idx].append(val)

            lay.addWidget(row_w)

    def update(self, c1: GlutenCalc, c2: GlutenCalc) -> None:
        for trio, calc in zip(self._vals, [c1, c2]):
            for lbl, val in zip(trio, [calc.v3, calc.v2, calc.v1]):
                animate_label_value(lbl, f"{val:.2f}", duration=240)

    def clear(self) -> None:
        for trio in self._vals:
            for lbl in trio:
                lbl.setText("—")


# ── Блок ИДК (один расчёт) ───────────────────────────────────────────────────

class IdkBlock(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
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

        # Заголовок
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background: rgba(108,92,231,0.05); border-radius: 10px 10px 0 0;"
            f"border-bottom: 0.5px solid {BORDER};"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(6)
        dot = QWidget(); dot.setFixedSize(5, 5)
        dot.setStyleSheet("background: #6c5ce7; border-radius: 2px; border: none;")
        hl.addWidget(dot)
        title = QLabel("ИДК")
        title.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        hl.addWidget(title)
        hl.addStretch()
        lay.addWidget(hdr)

        # Тело: две колонки
        body_w = QWidget(); body_w.setStyleSheet("background: transparent; border: none;")
        body_l = QHBoxLayout(body_w)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(0)

        # Левая — расхождение
        left = QWidget(); left.setStyleSheet("background: transparent; border: none;")
        ll = QVBoxLayout(left); ll.setContentsMargins(18, 12, 18, 14); ll.setSpacing(8)
        lt = QLabel("ПАРАМЕТРЫ")
        lt.setStyleSheet(f"color: #2a2a4e; font-family: '{FONT_UI}', sans-serif; font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;")
        ll.addWidget(lt)
        r3, self._div = _val_row("Расхождение", big=False)
        ll.addWidget(r3)
        ll.addStretch()
        body_l.addWidget(left, 1)

        div_line = QFrame()
        div_line.setFrameShape(QFrame.Shape.VLine)
        div_line.setStyleSheet(f"background: {BORDER}; border: none; max-width: 1px;")
        body_l.addWidget(div_line)

        # Правая — значения
        right = QWidget(); right.setStyleSheet("background: transparent; border: none;")
        rl = QVBoxLayout(right); rl.setContentsMargins(18, 12, 18, 14); rl.setSpacing(8)
        rt = QLabel("ЗНАЧЕНИЯ ИДК")
        rt.setStyleSheet(f"color: #2a2a4e; font-family: '{FONT_UI}', sans-serif; font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;")
        rl.addWidget(rt)
        r1, self._idk1 = _val_row("ИДК₁", big=True)
        r2, self._idk2 = _val_row("ИДК₂", big=True)
        rl.addWidget(r1); rl.addWidget(r2)
        rl.addStretch()
        body_l.addWidget(right, 1)

        lay.addWidget(body_w)

    def update(self, calc: IdkCalc) -> None:
        animate_label_value(self._idk1, str(calc.idk1), duration=280)
        animate_label_value(self._idk2, str(calc.idk2), duration=300)
        animate_label_value(self._div,  str(calc.divergence))

    def clear(self) -> None:
        for lbl in (self._idk1, self._idk2, self._div):
            lbl.setText("—")


# ── Страница Клейковина ───────────────────────────────────────────────────────

class GlutenPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Клейковина",
            subtitle="",
            section="Журналы",
            actions=[("Очистить", False), ("Рассчитать", True)],
        )
        self._action_buttons["Рассчитать"].clicked.connect(self._on_calculate)
        self._action_buttons["Очистить"].clicked.connect(self._on_clear)
        self._build_ui()
        # Оба поля принимают дробные числа
        attach_numeric_validators(
            [
                (self._gluten_inp.input, False),
                (self._idk_inp.input,    False),
            ],
            calc_btn=self._action_buttons["Рассчитать"],
        )

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Выбор пробы
        self._probe_selector = ProbeSelector(
            on_select=self._on_probe_selected,
            required_fields=["gluten", "idc"],
        )
        self._content_layout.addWidget(self._probe_selector)

        # Поля ввода
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(16)
        inputs_row.setContentsMargins(0, 0, 0, 0)
        self._gluten_inp = _Field("Клейковина, %", "например 28.0")
        self._idk_inp    = _Field("ИДК", "например 75.0")
        self._gluten_inp.input.returnPressed.connect(self._on_calculate)
        self._idk_inp.input.returnPressed.connect(self._on_calculate)
        inputs_row.addWidget(self._gluten_inp)
        inputs_row.addWidget(self._idk_inp)
        inputs_row.addStretch()
        iw = QWidget()
        iw.setStyleSheet("background: transparent;")
        iw.setLayout(inputs_row)
        self._content_layout.addWidget(iw)

        # Два блока рядом
        two_col = QHBoxLayout()
        two_col.setSpacing(12)
        two_col.setContentsMargins(0, 0, 0, 0)

        self._gluten_block = GlutenBlock()
        self._idk_block    = IdkBlock()


        for block in (self._gluten_block, self._idk_block):
            block.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )

        two_col.addWidget(self._gluten_block, 1)
        two_col.addWidget(self._idk_block, 1)

        tw = QWidget()
        tw.setStyleSheet("background: transparent;")
        tw.setLayout(two_col)
        self._content_layout.addWidget(tw)

        self._content_layout.addStretch()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, '_probe_selector'):
            self._probe_selector.reload()

    def _on_probe_selected(self, card) -> None:
        """Заполняет клейковину и ИДК из карточки."""
        if card.gluten is not None:
            self._gluten_inp.input.setText(str(card.gluten))
        if card.idc is not None:
            self._idk_inp.input.setText(str(card.idc))

    def _on_calculate(self) -> None:
        try:
            gluten = float(self._gluten_inp.value.replace(",", "."))
        except ValueError:
            self._gluten_inp.input.setStyleSheet(
                self._gluten_inp.input.styleSheet().replace(BORDER, "rgba(248,113,113,0.5)")
            )
            return
        try:
            idk = float(self._idk_inp.value.replace(",", "."))
        except ValueError:
            self._idk_inp.input.setStyleSheet(
                self._idk_inp.input.styleSheet().replace(BORDER, "rgba(248,113,113,0.5)")
            )
            return

        result: GlutenResult = calc_gluten(gluten, idk)
        self._gluten_block.update(result.calc1, result.calc2)
        self._idk_block.update(result.idk1)

    def _on_clear(self) -> None:
        self._gluten_inp.clear()
        self._idk_inp.clear()
        self._gluten_block.clear()
        self._idk_block.clear()
