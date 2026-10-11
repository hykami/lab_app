"""
Карточки → Создать (вручную).
"""

from __future__ import annotations
import random
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.components.type_pill_switcher import TypePillSwitcher
from ui.animations import fade_in
from ui.style_helpers import (
    compact_input_style, result_input_style, combo_style,
)
from ui.components.styled_combo import StyledComboBox
from ui.theme import (
    BG_CARD, BORDER, TEXT_MAIN,
    TEXT_BRIGHT, TEXT_MUTED, ACCENT_G,
    ACCENT_R, ACCENT_ICON, FONT_MONO, FONT_UI,
)
from logic.card_calc import generate_card, CardResult
from logic.incoming_control import apply_incoming_control
from ui.components.impurity_input_block import ImpurityInputBlock
from logic.card_params import generate_params, CardParams, PARAM_META, validate_params, CARD_TYPE_WASTE
from ui.components.validation import make_param_validator
from logic.db_service import (
    get_all_cultures, get_culture_with_norms, save_card, get_all_cards,
    get_silos_for_culture,
)


def _items_to_dicts(items: list) -> list[dict]:
    """Преобразует список ImpurityEntry в список dict для записи в БД."""
    return [{"name": i.name, "percent": i.percent, "grams": i.grams} for i in items]


# ── Поле ввода с меткой ───────────────────────────────────────────────────────

class _Field(QWidget):
    def __init__(self, label: str, placeholder: str = "",
                 required: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        # Заголовок: для обязательных — красная звёздочка, для необязательных — ничего
        lbl_row = QWidget()
        lbl_row.setStyleSheet("background: transparent;")
        lbl_lay = QHBoxLayout(lbl_row)
        lbl_lay.setContentsMargins(0, 0, 0, 0)
        lbl_lay.setSpacing(3)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; font-weight: 500; background: transparent; border: none;"
        )
        lbl_lay.addWidget(lbl)
        if required:
            star = QLabel("*")
            star.setStyleSheet(
                "color: #f87171; font-size: 12px; font-weight: 500;"
                " background: transparent; border: none; padding-bottom: 1px;"
            )
            lbl_lay.addWidget(star)
        lbl_lay.addStretch()
        lay.addWidget(lbl_row)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setFixedHeight(36)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_CARD}; border: 0.5px solid {BORDER};
                border-radius: 7px; color: {TEXT_MAIN};
                font-family: '{FONT_MONO}', monospace; font-size: 14px; padding: 0 12px;
            }}
            QLineEdit:focus {{ border-color: rgba(108,92,231,0.5); color: {TEXT_BRIGHT}; }}
        """)
        lay.addWidget(self.input)

    @property
    def value(self) -> str:
        return self.input.text().strip()

    def set_error(self, on: bool) -> None:
        s = self.input.styleSheet()
        if on:
            s = s.replace(BORDER, "rgba(248,113,113,0.7)")
            s = s.replace("rgba(108,92,231,0.5)", "rgba(248,113,113,0.7)")
        else:
            s = s.replace("rgba(248,113,113,0.7)", BORDER)
            s = s.replace("rgba(248,113,113,0.7)", "rgba(108,92,231,0.5)")
        self.input.setStyleSheet(s)

    def clear(self) -> None:
        self.input.clear()


# ── Блок показателей ──────────────────────────────────────────────────────────

# Фиксированный порядок показателей в сетке 2×4 (строка, колонка)
# Всегда 8 слотов: активные — поля ввода, неактивные — заглушка «—»
# Индекс после которого вставляется разделитель (после 4-го слота = индекс 3)
PARAMS_GRID_SEP_AFTER = 3   # вставляем сепаратор после слота 3 (gluten_arb, строка 1)

PARAMS_GRID_ORDER = [
    "humidity",       # (0,0)
    "natura",         # (0,1)
    "gluten_express", # (1,0)
    "gluten_arb",     # (1,1)
    # ── сепаратор ──
    "protein",        # (3,0)  ← строка 3, потому что строка 2 = сепаратор
    "vitreousness",   # (3,1)
    "idc",            # (4,0)
    "fall_number",    # (4,1)
]

# ── Группы показателей для горизонтального блока (Вариант 3 — 2 колонки) ──────
HPARAMS_GROUP_PHYSICAL = ("humidity", "natura", "vitreousness", "fall_number")
HPARAMS_GROUP_PROTEIN  = ("gluten_express", "gluten_arb", "protein", "idc")
HPARAMS_PHYSICAL_LABEL = "ФИЗИЧЕСКИЕ"
HPARAMS_PROTEIN_LABEL  = "КЛЕЙКОВИНА И БЕЛОК"
HPARAMS_PHYSICAL_COLOR = "#f87171"
HPARAMS_PROTEIN_COLOR  = "#fbbf24"


class ParamsBlock(QFrame):
    """Блок показателей: фиксированная сетка 2 колонки × 4 строки.
    Активные показатели — поля ввода, неактивные — заглушка «—» (disabled).
    """
    COLS = 2
    ROWS = 4

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Верхняя половина ─────────────────────────────────────────────
        # ПОКАЗАТЕЛИ вверху, сетка прижата к сепаратору снизу.
        # stretch-before = stretch-after нижней половины → симметрия.
        top_half = QWidget()
        top_half.setStyleSheet("background: transparent;")
        top_lay = QVBoxLayout(top_half)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(0)

        title_lbl = QLabel("ПОКАЗАТЕЛИ")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setFixedHeight(22)
        title_lbl.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        top_lay.addWidget(title_lbl)

        top_lay.addStretch(1)

        self._grid_top_w = QWidget()
        self._grid_top_w.setStyleSheet("background: transparent;")
        self._grid_top = QGridLayout(self._grid_top_w)
        self._grid_top.setContentsMargins(10, 0, 10, 0)
        self._grid_top.setHorizontalSpacing(8)
        self._grid_top.setVerticalSpacing(6)
        self._grid_top.setColumnStretch(0, 1)
        self._grid_top.setColumnStretch(1, 1)
        top_lay.addWidget(self._grid_top_w)

        # Фиксированный отступ 21px от нижней сетки до сепаратора
        top_spacer = QWidget()
        top_spacer.setFixedHeight(45)
        top_spacer.setStyleSheet("background: transparent;")
        top_lay.addWidget(top_spacer)

        lay.addWidget(top_half, 1)

        # ── Сепаратор 4px с отступами от краёв ──────────────────────────
        sep_wrap = QWidget()
        sep_wrap.setStyleSheet("background: transparent;")
        sep_wrap.setFixedHeight(1)
        sep_lay_h = QHBoxLayout(sep_wrap)
        sep_lay_h.setContentsMargins(14, 0, 14, 0)
        sep_lay_h.setSpacing(0)
        sep_line = QWidget()
        sep_line.setStyleSheet(f"background: {BORDER}; border: none;")
        sep_lay_h.addWidget(sep_line)
        lay.addWidget(sep_wrap)

        # ── Нижняя половина ──────────────────────────────────────────────
        # Сетка по центру: равные stretch сверху и снизу.
        bot_half = QWidget()
        bot_half.setStyleSheet("background: transparent;")
        bot_lay = QVBoxLayout(bot_half)
        bot_lay.setContentsMargins(0, 0, 0, 0)
        bot_lay.setSpacing(0)

        bot_lay.addStretch(1)

        self._grid_bot_w = QWidget()
        self._grid_bot_w.setStyleSheet("background: transparent;")
        self._grid_bot = QGridLayout(self._grid_bot_w)
        self._grid_bot.setContentsMargins(10, 0, 10, 0)
        self._grid_bot.setHorizontalSpacing(8)
        self._grid_bot.setVerticalSpacing(6)
        self._grid_bot.setColumnStretch(0, 1)
        self._grid_bot.setColumnStretch(1, 1)
        bot_lay.addWidget(self._grid_bot_w)

        bot_lay.addStretch(1)

        lay.addWidget(bot_half, 1)

        self.setFixedWidth(291)

        # Кнопки Сбросить / Сохранить внизу блока
        btn_row_w = QWidget()
        btn_row_w.setStyleSheet("background: transparent;")
        btn_row_lay = QHBoxLayout(btn_row_w)
        btn_row_lay.setContentsMargins(10, 8, 10, 10)
        btn_row_lay.setSpacing(8)
        btn_row_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._btn_reset = QPushButton("Сбросить")
        self._btn_reset.setFixedSize(96, 32)
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 0.5px solid #4a4a58;
                border-radius: 7px;
                color: #9090a8;
                font-family: '{FONT_UI}', sans-serif;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: #1e1e22; color: #a0a0b0; }}
            QPushButton:pressed {{ background: #252528; }}
        """)
        btn_row_lay.addWidget(self._btn_reset)

        self._btn_save = QPushButton("Сохранить")
        self._btn_save.setFixedSize(96, 32)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.setStyleSheet(f"""
            QPushButton {{
                background: #5b4fcf;
                border: none;
                border-radius: 7px;
                color: #ffffff;
                font-family: '{FONT_UI}', sans-serif;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background: #6c5ce7; }}
            QPushButton:pressed {{ background: #4a3fb5; }}
        """)
        btn_row_lay.addWidget(self._btn_save)

        lay.addWidget(btn_row_w)

        self._inputs: dict[str, QLineEdit] = {}
        self._culture = None
        self._card_type = ""


    def set_culture(self, culture_name: str,
                    culture: object = None,
                    card_type: str = "") -> None:
        _, active_keys = generate_params(culture_name, {}, card_type=card_type)
        self._culture = culture
        self._card_type = card_type

        self._inputs = {}

        active_set = set(active_keys)

        # Очищаем обе сетки
        for grid in (self._grid_top, self._grid_bot):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

        for slot_idx, key in enumerate(PARAMS_GRID_ORDER):
            # Первые 4 слота → верхняя сетка; остальные → нижняя
            if slot_idx <= PARAMS_GRID_SEP_AFTER:
                grid = self._grid_top
                row  = slot_idx // self.COLS
                col  = slot_idx % self.COLS
            else:
                grid = self._grid_bot
                adj  = slot_idx - PARAMS_GRID_SEP_AFTER - 1
                row  = adj // self.COLS
                col  = adj % self.COLS

            is_active = key in active_set
            label, unit, _ = PARAM_META[key]
            full_label = f"{label}, {unit}" if unit else label

            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(1)

            lbl = QLabel(full_label)
            lbl.setStyleSheet(
                f"color: {'#707085' if is_active else '#4a4a58'};"
                f" font-family: '{FONT_UI}', sans-serif;"
                " font-size: 12px; font-weight: 500; background: transparent; border: none;"
            )
            cl.addWidget(lbl)

            inp = QLineEdit()
            inp.setFixedHeight(28)

            if is_active:
                inp.setPlaceholderText("авто")
                inp.setStyleSheet(compact_input_style(font_size=12, radius=6))
                inp.textEdited.connect(
                    make_param_validator(key, inp, self._culture,
                                         bg="#111114", font_size=12, radius=6)
                )
                self._inputs[key] = inp
            else:
                inp.setText("—")
                inp.setReadOnly(True)
                inp.setStyleSheet(f"""
                    QLineEdit {{
                        background: #111114;
                        border: 0.5px solid #1e1e22;
                        border-radius: 6px;
                        color: #4a4a58;
                        font-family: '{FONT_MONO}', monospace;
                        font-size: 12px;
                        padding: 0 10px;
                    }}
                """)

            cl.addWidget(inp)
            grid.addWidget(cell, row, col)

    def _get_range(self, key: str) -> tuple[float, float]:
        from logic.card_params import get_range
        return get_range(key, getattr(self, "_culture", None))

    def get_user_values(self) -> dict[str, str]:
        return {k: inp.text().strip() for k, inp in self._inputs.items()}

    def show_results(self, params: CardParams, active_keys: list[str]) -> None:
        for key, inp in self._inputs.items():
            _, _, decimals = PARAM_META[key]
            val = getattr(params, key, None)
            if val is None:
                continue
            inp.setText(f"{val:.{decimals}f}")
            inp.setStyleSheet(result_input_style())

    def set_errors(self, errors: dict[str, str]) -> None:
        error_style = f"""
            QLineEdit {{
                background: rgba(248,113,113,0.08);
                border: 0.5px solid rgba(248,113,113,0.6);
                border-radius: 6px;
                color: #e0e0f0;
                font-family: '{FONT_MONO}', monospace;
                font-size: 12px;
                padding: 0 8px;
            }}
        """
        for key, inp in self._inputs.items():
            if key in errors:
                inp.setStyleSheet(error_style)

    def clear(self) -> None:
        for inp in self._inputs.values():
            inp.clear()
            inp.setPlaceholderText("авто")
            inp.setStyleSheet(compact_input_style(font_size=12, radius=6))


# ── Горизонтальный блок показателей (8 ячеек в строку) ───────────────────────

class _HParamsBlock(QWidget):
    """Горизонтальный блок показателей в две колонки (Вариант 3).
    Левая колонка — физические показатели, правая — клейковина и белок.
    Каждая колонка имеет акцентную полоску слева и заголовок.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        # ── Левая колонка (физические) ──────────────────────────────────────
        self._phys_frame = QFrame()
        self._phys_frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER};"
            f" border-left: 3px solid {HPARAMS_PHYSICAL_COLOR}; border-radius: 8px; }}"
        )
        phys_lay = QVBoxLayout(self._phys_frame)
        phys_lay.setContentsMargins(10, 8, 10, 8)
        phys_lay.setSpacing(6)

        phys_hdr = QLabel(HPARAMS_PHYSICAL_LABEL)
        phys_hdr.setStyleSheet(
            f"color: {HPARAMS_PHYSICAL_COLOR}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 10px; letter-spacing: 0.06em; background: transparent; border: none;"
        )
        phys_lay.addWidget(phys_hdr)

        self._phys_grid_w = QWidget()
        self._phys_grid_w.setStyleSheet("background: transparent; border: none;")
        self._phys_grid = QGridLayout(self._phys_grid_w)
        self._phys_grid.setContentsMargins(0, 0, 0, 0)
        self._phys_grid.setHorizontalSpacing(8)
        self._phys_grid.setVerticalSpacing(4)
        phys_lay.addWidget(self._phys_grid_w)

        outer.addWidget(self._phys_frame, 1)

        # ── Правая колонка (клейковина и белок) ─────────────────────────────
        self._prot_frame = QFrame()
        self._prot_frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER};"
            f" border-left: 3px solid {HPARAMS_PROTEIN_COLOR}; border-radius: 8px; }}"
        )
        prot_lay = QVBoxLayout(self._prot_frame)
        prot_lay.setContentsMargins(10, 8, 10, 8)
        prot_lay.setSpacing(6)

        prot_hdr = QLabel(HPARAMS_PROTEIN_LABEL)
        prot_hdr.setStyleSheet(
            f"color: {HPARAMS_PROTEIN_COLOR}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 10px; letter-spacing: 0.06em; background: transparent; border: none;"
        )
        prot_lay.addWidget(prot_hdr)

        self._prot_grid_w = QWidget()
        self._prot_grid_w.setStyleSheet("background: transparent; border: none;")
        self._prot_grid = QGridLayout(self._prot_grid_w)
        self._prot_grid.setContentsMargins(0, 0, 0, 0)
        self._prot_grid.setHorizontalSpacing(8)
        self._prot_grid.setVerticalSpacing(4)
        prot_lay.addWidget(self._prot_grid_w)

        outer.addWidget(self._prot_frame, 1)

        self._inputs: dict[str, QLineEdit] = {}
        self._culture = None
        self._card_type = ""

    def _build_cell(self, key: str, is_active: bool) -> QWidget:
        label, unit, _ = PARAM_META[key]
        full_label = f"{label}, {unit}" if unit else label

        cell = QWidget()
        cell.setStyleSheet("background: transparent; border: none;")
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)

        lbl = QLabel(full_label)
        lbl.setStyleSheet(
            f"color: {'#707085' if is_active else '#4a4a58'};"
            f" font-family: '{FONT_UI}', sans-serif;"
            " font-size: 10px; background: transparent; border: none;"
        )
        cl.addWidget(lbl)

        inp = QLineEdit()
        inp.setFixedHeight(26)
        if is_active:
            inp.setPlaceholderText("авто")
            inp.setStyleSheet(compact_input_style(font_size=12, radius=5))
            inp.textEdited.connect(
                make_param_validator(key, inp, self._culture,
                                     bg="#111114", font_size=12, radius=5)
            )
            self._inputs[key] = inp
        else:
            inp.setText("—")
            inp.setReadOnly(True)
            inp.setStyleSheet(
                f"QLineEdit {{ background: #111114; border: 0.5px solid #1e1e22;"
                f" border-radius: 5px; color: #4a4a58;"
                f" font-family: '{FONT_MONO}', monospace; font-size: 12px; padding: 0 6px; }}"
            )
        cl.addWidget(inp)
        return cell

    def _clear_grid(self, grid: QGridLayout) -> None:
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def set_culture(self, culture_name: str, culture=None, card_type: str = "") -> None:
        self._culture = culture
        self._card_type = card_type
        self._inputs = {}

        self._clear_grid(self._phys_grid)
        self._clear_grid(self._prot_grid)

        _, active_keys = generate_params(culture_name, {}, card_type=card_type)
        active_set = set(active_keys)

        # Левая колонка (2 столбца × 2 строки)
        for i, key in enumerate(HPARAMS_GROUP_PHYSICAL):
            cell = self._build_cell(key, key in active_set)
            self._phys_grid.addWidget(cell, i // 2, i % 2)

        # Правая колонка (2 столбца × 2 строки)
        for i, key in enumerate(HPARAMS_GROUP_PROTEIN):
            cell = self._build_cell(key, key in active_set)
            self._prot_grid.addWidget(cell, i // 2, i % 2)

    def get_user_values(self) -> dict[str, str]:
        return {k: inp.text().strip() for k, inp in self._inputs.items()}

    def show_results(self, params: "CardParams", active_keys: list) -> None:
        for key, inp in self._inputs.items():
            _, _, decimals = PARAM_META[key]
            val = getattr(params, key, None)
            if val is None:
                continue
            inp.setText(f"{val:.{decimals}f}")
            inp.setStyleSheet(result_input_style())

    def set_errors(self, errors: dict) -> None:
        error_style = (
            "QLineEdit { background: rgba(248,113,113,0.08);"
            " border: 0.5px solid rgba(248,113,113,0.6);"
            " border-radius: 5px; color: #e0e0f0;"
            f" font-family: '{FONT_MONO}', monospace; font-size: 12px; padding: 0 6px; }}"
        )
        for key, inp in self._inputs.items():
            if key in errors:
                inp.setStyleSheet(error_style)

    def clear(self) -> None:
        for inp in self._inputs.values():
            inp.clear()
            inp.setPlaceholderText("авто")
            inp.setStyleSheet(compact_input_style(font_size=12, radius=5))




class _GrainMassWidget(QFrame):
    """
    Нижняя панель v2.0 — Вариант Б:
    Левая колонка: крупное число основного зерна + вычеты + прогресс-бар.
    Правая: показатели культуры в сетке 4×2.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: #0d0d0f; border-top: 0.5px solid #1e1e22;"
            " border-radius: 0px; }"
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Левая панель — итог зерна ─────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(160)
        left.setStyleSheet(
            "background: transparent; border-right: 0.5px solid #1e1e22;"
        )
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 10, 16, 10)
        ll.setSpacing(2)

        lbl_title = QLabel("Основное зерно")
        lbl_title.setStyleSheet(
            f"color: #606075; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; font-weight: 500; text-transform: uppercase;"
            "letter-spacing: 0.06em; background: transparent; border: none;"
        )
        ll.addWidget(lbl_title)

        val_row = QWidget()
        val_row.setStyleSheet("background: transparent; border: none;")
        vrl = QHBoxLayout(val_row)
        vrl.setContentsMargins(0, 0, 0, 0)
        vrl.setSpacing(4)
        self._grain_val = QLabel("—")
        self._grain_val.setStyleSheet(
            f"color: #00b894; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 28px; font-weight: 500; line-height: 1;"
            "background: transparent; border: none;"
        )
        vrl.addWidget(self._grain_val)
        lbl_g = QLabel("г")
        lbl_g.setStyleSheet(
            "color: #707085; font-size: 11px; background: transparent; border: none;"
        )
        vrl.addWidget(lbl_g, 0, Qt.AlignmentFlag.AlignBottom)
        vrl.addStretch()
        ll.addWidget(val_row)

        deduct_row = QWidget()
        deduct_row.setStyleSheet("background: transparent; border: none;")
        drl = QHBoxLayout(deduct_row)
        drl.setContentsMargins(0, 0, 0, 0)
        drl.setSpacing(6)
        self._sp_ded = QLabel("")
        self._sp_ded.setStyleSheet(
            f"color: #f39c12; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; background: transparent; border: none;"
        )
        drl.addWidget(self._sp_ded)
        dot_lbl = QLabel("·")
        dot_lbl.setStyleSheet("color: #4a4a58; font-size: 12px; background: transparent; border: none;")
        drl.addWidget(dot_lbl)
        self._zp_ded = QLabel("")
        self._zp_ded.setStyleSheet(
            f"color: #a29bfe; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; background: transparent; border: none;"
        )
        drl.addWidget(self._zp_ded)
        drl.addStretch()
        ll.addWidget(deduct_row)

        # Прогресс-бар сегментный
        bar_container = QWidget()
        bar_container.setFixedHeight(4)
        bar_container.setStyleSheet("background: #1a1a1e; border-radius: 2px; border: none;")
        brl = QHBoxLayout(bar_container)
        brl.setContentsMargins(0, 0, 0, 0)
        brl.setSpacing(0)
        self._seg_main = QWidget()
        self._seg_main.setFixedHeight(4)
        self._seg_main.setStyleSheet("background: #00b894; border-radius: 2px; border: none;")
        self._seg_sp = QWidget()
        self._seg_sp.setFixedHeight(4)
        self._seg_sp.setStyleSheet("background: #f39c12; border: none;")
        self._seg_zp = QWidget()
        self._seg_zp.setFixedHeight(4)
        self._seg_zp.setStyleSheet("background: #a29bfe; border: none;")
        brl.addWidget(self._seg_main)
        brl.addWidget(self._seg_sp)
        brl.addWidget(self._seg_zp)
        bar_container.setLayout(brl)
        self._bar_container = bar_container
        self._bar_total_w   = 128  # будет пересчитан в update
        ll.addSpacing(4)
        ll.addWidget(bar_container)

        outer.addWidget(left)

        # ── Правая часть — показатели ─────────────────────────────────────────
        self._params_outer = QWidget()
        self._params_outer.setStyleSheet("background: transparent;")
        outer.addWidget(self._params_outer, 1)

        # ParamsBlock будет добавлен снаружи через set_params_widget()
        self._params_layout = QHBoxLayout(self._params_outer)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        self._params_layout.setSpacing(0)

    def set_params_widget(self, w: QWidget) -> None:
        while self._params_layout.count():
            self._params_layout.takeAt(0)
        self._params_layout.addWidget(w)

    def update(self, naveski: float, sp_items: list, zp_items: list) -> None:
        sp_sum = round(sum(i.grams for i in sp_items), 2)
        zp_sum = round(sum(i.grams for i in zp_items), 2)
        grain  = round(naveski - sp_sum - zp_sum, 2)

        self._grain_val.setText(f"{grain:.2f}")
        self._sp_ded.setText(f"−{sp_sum:.2f}г")
        self._zp_ded.setText(f"−{zp_sum:.2f}г")

        # Сегментный бар
        total = naveski if naveski > 0 else 50.0
        w = self._bar_container.width() or 128
        w_main = max(0, int(grain  / total * w))
        w_sp   = max(0, int(sp_sum / total * w))
        w_zp   = max(0, w - w_main - w_sp)
        self._seg_main.setFixedWidth(w_main)
        self._seg_sp.setFixedWidth(w_sp)
        self._seg_zp.setFixedWidth(w_zp)

    def clear(self) -> None:
        self._grain_val.setText("—")
        self._sp_ded.setText("")
        self._zp_ded.setText("")
        self._seg_main.setFixedWidth(0)
        self._seg_sp.setFixedWidth(0)
        self._seg_zp.setFixedWidth(0)

# ── Страница ──────────────────────────────────────────────────────────────────

class CardsManualPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Создать",
            subtitle="",
            section="Карточки",
            actions=[("Сохранить", True)],
        )
        self._cultures = []
        self._incoming_control = False

        # Sliding pill switcher в хедере для типа карточки
        self._type_pill = TypePillSwitcher([
            "Перегонка", "Входной контроль", "Отгрузка", "Очистка", "Контроль при хранении", "Отходы",
        ])
        self._type_pill.connect_changed(self._on_pill_type_changed)
        self.set_header_widget(self._type_pill)

        self._build_ui()

        # Подключаем кнопки из хедера BasePage
        self._action_buttons["Сохранить"].clicked.connect(self._on_create_and_save)

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # ── Карточка метаданных ──────────────────────────────────────────────
        meta_card = QFrame()
        meta_card.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 8px; }}"
        )
        self._meta_lay = QHBoxLayout(meta_card)
        self._meta_lay.setSpacing(12)
        self._meta_lay.setContentsMargins(12, 10, 12, 10)
        self._meta_lay.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # № пробы
        self._probe_field = _Field("№ пробы", "...", required=True)
        self._probe_field.setFixedWidth(94)
        self._probe_field.input.returnPressed.connect(self._focus_next_field)
        self._probe_field.input.textChanged.connect(self._on_probe_text_changed)

        self._probe_check_timer = QTimer()
        self._probe_check_timer.setSingleShot(True)
        self._probe_check_timer.setInterval(400)
        self._probe_check_timer.timeout.connect(self._check_probe_duplicate)

        # Скрытый combo для совместимости логики
        self._type_combo = self._make_combo("Тип", [
            "Перегонка", "Входной контроль", "Отгрузка", "Очистка", "Контроль при хранении", "Отходы",
        ], on_change=self._on_type_changed, fixed_width=200)
        self._type_combo[0].hide()

        # Культура — растягивается
        self._cult_widget, self._cult_combo = self._make_culture_combo()
        self._cult_widget.setMinimumWidth(140)

        # Силос
        self._silo_widget, self._silo_combo = self._make_combo("Силос", [], fixed_width=170)

        # Место (только Перегонка)
        self._place_widget, self._place_combo = self._make_combo(
            "Место", ["Свинки", "КРС", "Мукомолка", "Рыбы"], fixed_width=120,
        )

        # Страна (только ВхК)
        self._origin_widget, self._origin_combo = self._make_combo(
            "Страна", ["РБ", "РФ"], fixed_width=110,
        )

        # Год урожая (только ВхК)
        self._year_field = _Field("Год урожая", "2025", required=True)
        self._year_field.setFixedWidth(90)

        # Поставщик (только ВхК)
        self._supplier_field = _Field("Поставщик", "название", required=True)
        self._supplier_field.setFixedWidth(160)

        # Грузополучатель (только Отгрузка)
        self._consignee_field = _Field("Грузополучатель", "название", required=True)
        self._consignee_field.setFixedWidth(180)

        # Группы метаданных — для динамической раскладки с разделителями
        # Группа = список виджетов, отображается если хотя бы один виден.
        # Разделители рисуются автоматически между видимыми группами.
        self._meta_groups: list[list[QWidget]] = [
            [self._probe_field],                                           # обязательная
            [self._cult_widget],                                            # обязательная (для большинства типов)
            [self._silo_widget, self._place_widget, self._origin_widget,
             self._year_field, self._supplier_field, self._consignee_field], # контекстные
        ]

        # Кеш разделителей
        self._meta_dividers: list[QWidget] = []
        # Источник истины для видимости полей мета
        self._meta_visibility: dict = {w: True for grp in self._meta_groups for w in grp}
        self._content_layout.addWidget(meta_card)
        self._relayout_meta()

        # ── Уведомление для входного контроля ────────────────────────────────
        self._ic_notice = QFrame()
        self._ic_notice.setStyleSheet(
            "QFrame { background: rgba(248,113,113,0.04);"
            " border: 0.5px solid rgba(248,113,113,0.12); border-radius: 6px; }"
        )
        notice_lay = QHBoxLayout(self._ic_notice)
        notice_lay.setContentsMargins(11, 5, 11, 5)
        notice_lay.setSpacing(8)

        dot = QLabel("")
        dot.setFixedSize(5, 5)
        dot.setStyleSheet("background: #f87171; border-radius: 2px; border: none;")
        notice_lay.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        notice_lbl = QLabel(
            "Входной контроль — к значениям СП и ЗП будет добавлено допускаемое расхождение"
        )
        notice_lbl.setStyleSheet(
            f"color: #806060; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 12px; background: transparent; border: none;"
        )
        notice_lay.addWidget(notice_lbl)
        notice_lay.addStretch()
        self._ic_notice.setVisible(False)
        self._content_layout.addWidget(self._ic_notice)

        # ── Блоки примесей горизонтально ─────────────────────────────────────
        self._sp_block = ImpurityInputBlock("СП", on_changed=self._recalc_sp)
        self._zp_block = ImpurityInputBlock("ЗП", on_changed=self._recalc_zp)
        self._sp_block.connect_total(self._on_sp_total_edited)
        self._zp_block.connect_total(self._on_zp_total_edited)

        imp_row = QHBoxLayout()
        imp_row.setSpacing(6)
        imp_row.setContentsMargins(0, 0, 0, 0)
        imp_row.addWidget(self._sp_block, 1)
        imp_row.addWidget(self._zp_block, 1)
        imp_row_w = QWidget(); imp_row_w.setStyleSheet("background: transparent;"); imp_row_w.setLayout(imp_row)
        self._content_layout.addWidget(imp_row_w)

        # ── Горизонтальный блок показателей ──────────────────────────────────
        self._hparams = _HParamsBlock()
        self._content_layout.addWidget(self._hparams)

        self._content_layout.addStretch()

        # Совместимость
        self._params_block = ParamsBlock()
        self._params_block.hide()
        self._grain_widget = _GrainMassWidget()

        self._load_cultures()

    def _relayout_meta(self) -> None:
        """Перестраивает строку метаданных по _meta_visibility."""
        meta_card = self._meta_lay.parentWidget()

        # Снимаем все элементы с layout (не удаляя виджеты — они остаются под meta_card)
        while self._meta_lay.count():
            item = self._meta_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                # Виджет всё ещё дочка meta_card, просто без позиции
                w.hide()

        # Удаляем старые разделители
        for d in self._meta_dividers:
            d.setParent(None)
            d.deleteLater()
        self._meta_dividers = []

        def _make_div() -> QWidget:
            d = QWidget(meta_card)
            d.setFixedSize(1, 36)
            d.setStyleSheet(f"background: {BORDER}; border: none;")
            return d

        # Собираем видимые группы
        visible_groups = []
        for grp in self._meta_groups:
            visible = [w for w in grp if self._meta_visibility.get(w, True)]
            if visible:
                visible_groups.append(visible)

        # Расставляем
        for i, grp in enumerate(visible_groups):
            if i > 0:
                div = _make_div()
                self._meta_dividers.append(div)
                self._meta_lay.addWidget(div, 0, Qt.AlignmentFlag.AlignBottom)
            for w in grp:
                stretch = 1 if w is self._cult_widget else 0
                self._meta_lay.addWidget(w, stretch)
                w.show()

    def _set_meta_visible(self, widget: QWidget, visible: bool) -> None:
        """Устанавливает желаемую видимость поля метаданных."""
        if not hasattr(self, "_meta_visibility"):
            self._meta_visibility = {}
        self._meta_visibility[widget] = visible

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color: #707085; font-family: '{FONT_UI}', sans-serif; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        return l

    def _make_combo(self, label: str, items: list[str],
                    on_change=None, fixed_width: int = 0,
                    required: bool = False) -> tuple[QWidget, QComboBox]:
        """Создаёт виджет с меткой и QComboBox."""
        w = QWidget(); w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(5)

        # Строка метки — с красной звёздочкой если required
        lbl_row = QWidget(); lbl_row.setStyleSheet("background: transparent;")
        lbl_lay = QHBoxLayout(lbl_row)
        lbl_lay.setContentsMargins(0, 0, 0, 0); lbl_lay.setSpacing(3)
        lbl_lay.addWidget(self._lbl(label))
        if required:
            star = QLabel("*")
            star.setStyleSheet(
                "color: #f87171; font-size: 12px; font-weight: 500;"
                " background: transparent; padding-bottom: 1px;"
            )
            lbl_lay.addWidget(star)
        lbl_lay.addStretch()
        lay.addWidget(lbl_row)

        combo = StyledComboBox(font_size=13)
        combo.setFixedHeight(36)
        width = fixed_width if fixed_width else 160
        combo.setFixedWidth(width)
        w.setFixedWidth(width)
        combo.setStyleSheet(combo_style(font_size=13))
        for item in items:
            combo.addItem(item)
        if on_change:
            combo.currentIndexChanged.connect(on_change)
        lay.addWidget(combo)
        return w, combo

    def _make_culture_combo(self) -> tuple[QWidget, QComboBox]:
        """Создаёт виджет выбора культуры с сигналом на пересчёт."""
        w, combo = self._make_combo("Культура", [], fixed_width=180)
        combo.currentIndexChanged.connect(self._on_culture_changed)
        return w, combo

    _TYPES_WITH_SILO = frozenset({"Перегонка", "Отгрузка", "Контроль при хранении"})

    def _on_pill_type_changed(self, _index: int, text: str) -> None:
        """Pill switcher изменился — синхронизируем со скрытым combo."""
        combo = self._type_combo[1]
        idx = combo.findText(text)
        if idx >= 0 and combo.currentIndex() != idx:
            combo.setCurrentIndex(idx)  # триггерит _on_type_changed автоматически
        fade_in(self._content_widget, duration=160)

    def _on_type_changed(self, _index: int) -> None:
        """Обновляет видимость полей в зависимости от типа."""
        card_type = self._type_combo[1].currentText()
        is_ic = (card_type == "Входной контроль")
        is_waste = (card_type == CARD_TYPE_WASTE)
        self._set_meta_visible(self._silo_widget, card_type in self._TYPES_WITH_SILO)
        self._set_meta_visible(self._origin_widget, is_ic)
        self._set_meta_visible(self._year_field, is_ic)
        self._set_meta_visible(self._supplier_field, is_ic)
        self._set_meta_visible(self._cult_widget, not is_waste)
        self._incoming_control = is_ic
        if hasattr(self, "_ic_notice"):
            self._ic_notice.setVisible(is_ic)
        if not is_ic:
            self._sp_block.clear_bumped_total()
            self._zp_block.clear_bumped_total()
        self._set_meta_visible(self._consignee_field, card_type == "Отгрузка")
        self._set_meta_visible(self._place_widget, card_type == "Перегонка")
        # Перестраиваем строку метаданных под новый набор видимых полей
        if hasattr(self, "_meta_lay"):
            self._relayout_meta()
        # Обновляем накинутые значения для ВхК
        if is_ic:
            self._update_ic_bumped()
        # При типе Отходы используем _waste_culture напрямую
        if is_waste:
            waste = getattr(self, '_waste_culture', None)
            if waste:
                from logic.db_service import get_culture_with_norms
                waste_full = get_culture_with_norms(waste.id)
                if waste_full:
                    self._hparams.set_culture(waste_full.name, waste_full,
                                                   card_type=card_type)
        else:
            culture = self._cult_combo.currentData() if hasattr(self, '_cult_combo') else None
            if culture:
                from logic.db_service import get_culture_with_norms
                culture_full = get_culture_with_norms(culture.id)
                if culture_full:
                    self._hparams.set_culture(culture_full.name, culture_full,
                                                   card_type=card_type)

    def _reload_silos(self) -> None:
        """Обновляет список силосов по выбранной культуре."""
        culture = self._cult_combo.currentData()
        combo = self._silo_combo
        combo.blockSignals(True)
        combo.clear()
        if culture:
            silos = get_silos_for_culture(culture.name)
            if silos:
                for s in silos:
                    label = f"Силос {s.number}"
                    if s.crop_class:
                        label += f" ({s.crop_class})"
                    combo.addItem(label, userData=s)
            else:
                combo.addItem("Нет силосов с выбранной культурой")
                combo.setEnabled(False)
                combo.blockSignals(False)
                return
        combo.setEnabled(True)
        combo.blockSignals(False)

    def _load_cultures(self) -> None:
        all_cultures = get_all_cultures()
        # Отходы — не культура для выбора, храним отдельно для подстановки
        self._waste_culture = next((c for c in all_cultures if c.name == CARD_TYPE_WASTE), None)
        self._cultures = [c for c in all_cultures if c.name != CARD_TYPE_WASTE]
        self._cult_combo.blockSignals(True); self._cult_combo.clear()
        for c in self._cultures:
            self._cult_combo.addItem(c.name, userData=c)
        self._cult_combo.blockSignals(False)
        # Инициализируем начальное состояние видимости Силоса
        self._on_type_changed(0)
        if self._cultures: self._on_culture_changed(0)

    def _on_culture_changed(self, index: int) -> None:
        from logic.card_calc import (
            SP_IMPURITIES, ZP_IMPURITIES,
            SP_IMPURITIES_CORN, ZP_IMPURITIES_CORN, CORN_CULTURES,
            SP_IMPURITIES_ROW2, ZP_IMPURITIES_ROW2,
            SP_IMPURITIES_CORN_ROW2, ZP_IMPURITIES_CORN_ROW2,
        )
        culture = self._cult_combo.itemData(index)
        if not culture:
            return

        # Обновляем список силосов под выбранную культуру
        self._reload_silos()

        # Всегда берём свежие данные из БД — чтобы учитывать изменения норм
        culture_full = get_culture_with_norms(culture.id)
        if not culture_full:
            return

        self._hparams.set_culture(culture_full.name, culture_full,
                                       card_type=self._type_combo[1].currentText())

        is_corn = culture_full.name in CORN_CULTURES
        sp_names = SP_IMPURITIES_CORN if is_corn else SP_IMPURITIES
        zp_names = ZP_IMPURITIES_CORN if is_corn else ZP_IMPURITIES
        naveski  = culture_full.sample_weight or 50.0

        # Строим словари норм примесей {name: (min, max)}
        sp_norms: dict[str, tuple[float, float]] = {}
        zp_norms: dict[str, tuple[float, float]] = {}
        if culture_full:
            for imp in culture_full.impurities:
                d = sp_norms if imp.group_name == "СП" else zp_norms
                d[imp.name] = (imp.min_val, imp.max_val)

        sp_row2 = SP_IMPURITIES_CORN_ROW2 if is_corn else SP_IMPURITIES_ROW2
        zp_row2 = ZP_IMPURITIES_CORN_ROW2 if is_corn else ZP_IMPURITIES_ROW2
        self._sp_block.setup_impurities(sp_names, naveski, norms=sp_norms, names_row2=sp_row2)
        self._zp_block.setup_impurities(zp_names, naveski, norms=zp_norms, names_row2=zp_row2)

        # Устанавливаем диапазоны total из норм культуры
        if culture_full:
            self._sp_block.set_total_norms(culture_full.sp_min, culture_full.sp_max)
            self._zp_block.set_total_norms(culture_full.zp_min, culture_full.zp_max)

        # Сбрасываем total и примеси чтобы сгенерировались новые случайные значения
        self._sp_block.clear()
        self._zp_block.clear()
        self._recalc_impurities()
        # Если включён ВхК — обновляем накинутые значения
        if getattr(self, "_incoming_control", False):
            self._update_ic_bumped()

    def _get_total(self, block, default: float) -> float:
        text = block.total_value.replace(",", ".").strip()
        if text:
            try:
                return float(text)
            except ValueError:
                return default
        # Поле пустое — генерируем случайное из диапазона культуры
        culture = self._cult_combo.currentData()
        if culture:
            culture_full = get_culture_with_norms(culture.id)
            if culture_full:
                is_sp = (block is self._sp_block)
                lo = culture_full.sp_min if is_sp else culture_full.zp_min
                hi = culture_full.sp_max if is_sp else culture_full.zp_max
                if hi > 0:
                    value = self._even_rand(lo or 0.2, hi)
                    block._total_inp.setText(str(value))
                    return value
        return default

    def _on_sp_total_edited(self) -> None:
        self._recalc_sp()
        self._update_ic_bumped()

    def _on_zp_total_edited(self) -> None:
        self._recalc_zp()
        self._update_ic_bumped()

    def _update_ic_bumped(self) -> None:
        """Пересчитывает накинутые значения СП/ЗП на лету для входного контроля."""
        if not getattr(self, "_incoming_control", False):
            return
        culture = self._cult_combo.currentData() if hasattr(self, "_cult_combo") else None
        if not culture:
            return
        from logic.db_service import get_culture_with_norms
        culture_full = get_culture_with_norms(culture.id)
        naveski = (culture_full.sample_weight if culture_full else None) or 50.0
        sp = self._get_total(self._sp_block, 0.0)
        zp = self._get_total(self._zp_block, 0.0)
        # Собираем текущие позиции
        sp_items = [type("X", (), {"name": r.name, "percent": r.effective_value, "grams": 0})()
                    for r in self._sp_block._rows]
        zp_items = [type("X", (), {"name": r.name, "percent": r.effective_value, "grams": 0})()
                    for r in self._zp_block._rows]
        ic = apply_incoming_control(
            sp_base=sp, zp_base=zp,
            sp_items_base=sp_items, zp_items_base=zp_items,
            naveski=naveski, culture_name=culture.name,
        )
        self._sp_block.set_bumped_total(ic.sp_base, ic.sp_total)
        self._zp_block.set_bumped_total(ic.zp_base, ic.zp_total)

    def _recalc_sp(self) -> None:
        """Пересчитывает блок СП. Если изменена примесь — обновляет total."""
        culture = self._cult_combo.currentData()
        if not culture or not self._sp_block._rows:
            return
        # Если есть ручные значения примесей — total = их сумма
        if any(r.is_manual for r in self._sp_block._rows):
            self._sp_block.update_total_from_items()
            self._update_ic_bumped()
            return
        sp = self._get_total(self._sp_block, 1.6)
        zp = self._get_total(self._zp_block, 3.2)
        culture_full = get_culture_with_norms(culture.id)
        naveski = (culture_full.sample_weight if culture_full else None) or 50.0
        card = generate_card(culture.name, naveski, sp, zp)
        for entry in card.sp_items:
            for row in self._sp_block._rows:
                if row.name == entry.name and not row.is_manual:
                    row.set_auto(entry.percent)
        self._sp_block.update_auto_values(sp)
        self._update_ic_bumped()

    def _recalc_zp(self) -> None:
        """Пересчитывает только блок ЗП."""
        culture = self._cult_combo.currentData()
        if not culture or not self._zp_block._rows:
            return
        # Если есть ручные значения примесей — total = их сумма
        if any(r.is_manual for r in self._zp_block._rows):
            self._zp_block.update_total_from_items()
            self._update_ic_bumped()
            return
        sp = self._get_total(self._sp_block, 1.6)
        zp = self._get_total(self._zp_block, 3.2)
        culture_full = get_culture_with_norms(culture.id)
        naveski = (culture_full.sample_weight if culture_full else None) or 50.0
        card = generate_card(culture.name, naveski, sp, zp)
        for entry in card.zp_items:
            for row in self._zp_block._rows:
                if row.name == entry.name and not row.is_manual:
                    row.set_auto(entry.percent)
        self._zp_block.update_auto_values(zp)
        self._update_ic_bumped()

    def _recalc_impurities(self) -> None:
        """Генерирует новые случайные total для СП и ЗП, затем раздаёт примеси."""
        culture = self._cult_combo.currentData()
        if not culture:
            return
        culture_full = get_culture_with_norms(culture.id)
        naveski = (culture_full.sample_weight if culture_full else None) or 50.0

        # Генерируем total один раз для каждого блока
        sp = self._get_total(self._sp_block, 1.6)
        zp = self._get_total(self._zp_block, 3.2)

        if self._sp_block._rows:
            card = generate_card(culture.name, naveski, sp, zp)
            for entry in card.sp_items:
                for row in self._sp_block._rows:
                    if row.name == entry.name and not row.is_manual:
                        row.set_auto(entry.percent)
            self._sp_block.update_auto_values(sp)

        if self._zp_block._rows:
            card = generate_card(culture.name, naveski, sp, zp)
            for entry in card.zp_items:
                for row in self._zp_block._rows:
                    if row.name == entry.name and not row.is_manual:
                        row.set_auto(entry.percent)
            self._zp_block.update_auto_values(zp)

    def _on_create_and_save(self) -> None:
        card_type_now = self._type_combo[1].currentText()
        if card_type_now == CARD_TYPE_WASTE:
            culture = getattr(self, '_waste_culture', None)
        else:
            culture = self._cult_combo.currentData()
        if not culture:
            return

        # 1. Валидация номера пробы (вкл. проверку на дубликат)
        probe = self._probe_field.value
        if not self._validate_probe(probe):
            return

        # 1b. Валидация обязательных полей (видимых для текущего типа)
        if not self._validate_required_fields():
            return

        # 2. Валидация и парсинг totals СП/ЗП
        totals = self._validate_and_get_totals(culture)
        if totals is None:
            return
        sp, zp = totals

        # 3. Валидация примесей по диапазонам норм
        impurity_errors = self._sp_block.validate(sp) + self._zp_block.validate(zp)
        if impurity_errors:
            QMessageBox.warning(self, "Ошибка примесей", "\n".join(impurity_errors))
            return

        # 4. Сбор результата + входной контроль (если включён)
        naveski = culture.sample_weight or 50.0
        card = CardResult(
            culture_name=culture.name,
            naveski=naveski,
            sp_total=sp,
            zp_total=zp,
            sp_items=self._sp_block.collect_entries(naveski),
            zp_items=self._zp_block.collect_entries(naveski),
        )
        ic_result = self._apply_ic_if_enabled(card, naveski, culture.name)

        # 5. Валидация и генерация показателей
        params, active_keys = self._validate_and_generate_params(culture)
        if params is None:
            return

        # 6. Сохранение в БД
        self._save_card_to_db(probe, culture, card, ic_result, params, active_keys)

        # 7. UI: тост успеха + автоочистка
        self._probe_check_timer.stop()
        self._show_save_success_toast()

    # ── Хелперы _on_create_and_save ───────────────────────────────────────────

    def _on_probe_text_changed(self, text: str) -> None:
        """Запускает дебаунс-таймер при каждом изменении поля пробы."""
        if not text.strip():
            self._probe_field.set_error(False)
            self._probe_field.input.setToolTip("")
            return
        self._probe_check_timer.start()

    def _check_probe_duplicate(self) -> None:
        """Проверяет есть ли уже карточка с таким номером пробы."""
        probe = self._probe_field.value
        if not probe:
            return
        existing = get_all_cards(probe_search=probe)
        is_duplicate = any(c.probe_number == probe for c in existing)
        self._probe_field.set_error(is_duplicate)
        self._probe_field.input.setToolTip(
            f"Проба «{probe}» уже существует" if is_duplicate else ""
        )

    def _validate_probe(self, probe: str) -> bool:
        """Проверяет что номер заполнен и уникален. Подсвечивает поле при ошибке."""
        if not probe:
            self._probe_field.set_error(True)
            return False
        self._probe_field.set_error(False)

        existing = get_all_cards(probe_search=probe)
        if any(c.probe_number == probe for c in existing):
            self._probe_field.set_error(True)
            self._show_button_error_toast(
                "Создать и сохранить", "✗ Уже существует",
            )
            return False
        return True
        """Проверяет, что номер заполнен и уникален. Подсвечивает поле при ошибке."""
        if not probe:
            self._probe_field.set_error(True)
            return False
        self._probe_field.set_error(False)

        existing = get_all_cards(probe_search=probe)
        if any(c.probe_number == probe for c in existing):
            self._probe_field.set_error(True)
            self._show_button_error_toast(
                "Создать и сохранить", "✗ Уже существует",
            )
            return False

    def _validate_required_fields(self) -> bool:
        """
        Проверяет обязательные текстовые поля для текущего типа карточки.
        Подсвечивает незаполненные поля, показывает одно QMessageBox со списком.
        Возвращает True если всё заполнено.
        """
        card_type = self._type_combo[1].currentText()

        # Список: (поле _Field, метка для сообщения об ошибке, условие видимости)
        candidates = [
            (self._year_field,     "Год урожая",      card_type == "Входной контроль"),
            (self._supplier_field, "Поставщик",       card_type == "Входной контроль"),
            (self._consignee_field,"Грузополучатель", card_type == "Отгрузка"),
        ]

        empty = []
        for field, label, visible in candidates:
            if not visible:
                field.set_error(False)
                continue
            if not field.value:
                field.set_error(True)
                empty.append(label)
            else:
                field.set_error(False)

        if not empty:
            return True

        if len(empty) == 1:
            msg = f"Заполните обязательное поле:\n• {empty[0]}"
        else:
            items = "\n".join(f"• {lbl}" for lbl in empty)
            msg = f"Заполните обязательные поля:\n{items}"

        self._show_button_error_toast("Создать и сохранить", "✗ Не все поля заполнены")
        QMessageBox.warning(self, "Незаполненные поля", msg)
        return False
        return True

    def _validate_and_get_totals(
        self, culture
    ) -> Optional[tuple[float, float]]:
        """
        Подсвечивает ошибочные totals, показывает QMessageBox при ошибке диапазона.
        Если поле total пустое — генерирует случайное чётное в диапазоне культуры.
        Возвращает (sp, zp) или None при ошибке.
        """
        total_errors = []
        for block, label in [(self._sp_block, "СП"), (self._zp_block, "ЗП")]:
            err = block.validate_total()
            if err:
                block._total_inp.setStyleSheet(
                    block._total_inp.styleSheet()
                    .replace(BORDER, "rgba(248,113,113,0.7)")
                )
                total_errors.append(err)
        if total_errors:
            QMessageBox.warning(self, "Ошибка диапазона",
                                "\n".join(f"• {e}" for e in total_errors))
            return None

        culture_norms = get_culture_with_norms(culture.id)

        sp = self._parse_or_random_total(
            self._sp_block,
            (culture_norms.sp_min if culture_norms else 0.2,
             culture_norms.sp_max if culture_norms else 2.0),
        )
        zp = self._parse_or_random_total(
            self._zp_block,
            (culture_norms.zp_min if culture_norms else 0.4,
             culture_norms.zp_max if culture_norms else 5.0),
        )
        if sp is None or zp is None:
            return None
        return sp, zp

    def _parse_or_random_total(
        self, block, default_range: tuple[float, float],
    ) -> Optional[float]:
        """
        Парсит значение total из поля блока. Если пусто — генерирует случайное
        чётное в default_range и записывает в поле. None если введено невалидное.
        """
        text = block.total_value.replace(",", ".")
        if not text:
            lo, hi = default_range
            value = self._even_rand(lo or 0.2, hi or 2.0)
            block._total_inp.setText(str(value))
            return value
        try:
            value = float(text)
        except ValueError:
            return None
        # Минимум — единица квантования (UNIT)
        if 0 < value < 0.02:
            value = 0.02
            block._total_inp.setText("0.02")
        return value

    @staticmethod
    def _even_rand(lo: float, hi: float) -> float:
        """Случайное число с шагом 0.2 из диапазона [lo, hi]."""
        lo_u = max(1, int(round(lo / 0.2)))
        hi_u = max(lo_u + 1, int(round(hi / 0.2)))
        return round(random.randint(lo_u, hi_u) * 0.2, 1)

    def _apply_ic_if_enabled(self, card: CardResult, naveski: float,
                              culture_name: str):
        """Применяет входной контроль если включён, обновляет grain widget."""
        if self._incoming_control:
            ic = apply_incoming_control(
                sp_base=card.sp_total, zp_base=card.zp_total,
                sp_items_base=card.sp_items, zp_items_base=card.zp_items,
                naveski=naveski, culture_name=culture_name,
            )
            self._grain_widget.update(naveski, ic.sp_items, ic.zp_items)
            self._sp_block.set_bumped_total(ic.sp_base, ic.sp_total)
            self._zp_block.set_bumped_total(ic.zp_base, ic.zp_total)
            return ic
        self._grain_widget.update(naveski, card.sp_items, card.zp_items)
        self._sp_block.clear_bumped_total()
        self._zp_block.clear_bumped_total()
        return None

    def _validate_and_generate_params(
        self, culture,
    ) -> tuple[Optional[CardParams], list[str]]:
        """
        Валидирует пользовательские значения показателей и генерирует CardParams.
        При ошибке валидации показывает QMessageBox и возвращает (None, []).
        """
        # Сначала забираем пользовательские значения — иначе clear() их затрёт
        user_vals = self._hparams.get_user_values()
        culture_obj = get_culture_with_norms(culture.id)
        card_type = self._type_combo[1].currentText()
        _, active_keys = generate_params(culture.name, {}, culture=culture_obj,
                                         card_type=card_type)

        param_errors = validate_params(user_vals, active_keys, culture=culture_obj)
        if param_errors:
            self._hparams.set_errors(param_errors)
            msg = "Значения показателей вне допустимого диапазона:\n\n"
            msg += "\n".join(f"• {e}" for e in param_errors.values())
            QMessageBox.warning(self, "Ошибка показателей", msg)
            return None, []

        # Валидация прошла — обновляем UI
        self._hparams.clear()
        params, active_keys = generate_params(
            culture.name, user_vals, culture=culture_obj, card_type=card_type,
        )
        self._hparams.show_results(params, active_keys)
        return params, active_keys

    def _save_card_to_db(self, probe: str, culture, card: CardResult,
                          ic_result, params: CardParams,
                          active_keys: list[str]) -> None:
        """Собирает данные и вызывает save_card."""
        if ic_result:
            sp_items_save = _items_to_dicts(ic_result.sp_items)
            zp_items_save = _items_to_dicts(ic_result.zp_items)
            sp_items_base = _items_to_dicts(ic_result.sp_items_base)
            zp_items_base = _items_to_dicts(ic_result.zp_items_base)
        else:
            sp_items_save = _items_to_dicts(card.sp_items)
            zp_items_save = _items_to_dicts(card.zp_items)
            sp_items_base = None
            zp_items_base = None

        params_dict = {
            k: getattr(params, k) for k in active_keys
            if getattr(params, k, None) is not None
        }

        # Тип, силос, страна происхождения, год урожая
        card_type = self._type_combo[1].currentText()
        silo = self._silo_combo.currentData() if self._silo_widget.isVisible() else None
        silo_id = silo.id if silo else None
        origin_country = (
            self._origin_combo.currentText()
            if self._origin_widget.isVisible() else None
        )
        harvest_year = (
            self._year_field.value.strip() or None
            if self._year_field.isVisible() else None
        )
        supplier = (
            self._supplier_field.value.strip() or None
            if self._supplier_field.isVisible() else None
        )
        consignee = (
            self._consignee_field.value.strip() or None
            if self._consignee_field.isVisible() else None
        )
        distillation_place = (
            self._place_combo.currentText()
            if self._place_widget.isVisible() else None
        )

        save_card(
            probe_number=probe,
            culture_name=culture.name,
            card_type=card_type,
            silo_id=silo_id,
            origin_country=origin_country,
            harvest_year=harvest_year,
            supplier=supplier,
            consignee=consignee,
            distillation_place=distillation_place,
            sp_total=ic_result.sp_total if ic_result else card.sp_total,
            zp_total=ic_result.zp_total if ic_result else card.zp_total,
            sp_items=sp_items_save,
            zp_items=zp_items_save,
            params=params_dict,
            incoming_ctrl=self._incoming_control,
            sp_base=ic_result.sp_base if ic_result else None,
            zp_base=ic_result.zp_base if ic_result else None,
            sp_divergence=ic_result.sp_divergence if ic_result else None,
            zp_divergence=ic_result.zp_divergence if ic_result else None,
            sp_items_base=sp_items_base,
            zp_items_base=zp_items_base,
        )

    def _show_button_error_toast(self, button_label: str, text: str,
                                  duration_ms: int = 2000) -> None:
        """Показывает временное состояние ошибки на кнопке."""
        # flash_error — кнопки теперь в ParamsBlock, просто игнорируем
        pass  # self._params_block._btn_save.flash_error(text, duration_ms)

    def _show_save_success_toast(self, duration_ms: int = 2000) -> None:
        """Показывает успешный тост на кнопке и очищает поля для следующей карточки."""
        pass  # flash_success — упрощённая версия без анимации

        def _clear_fields():
            self._probe_field.clear()
            self._sp_block.clear()
            self._zp_block.clear()
            self._grain_widget.clear()
            self._hparams.clear()
            # Генерируем новые случайные значения СП/ЗП и примеси
            self._recalc_impurities()

        QTimer.singleShot(duration_ms, _clear_fields)

    def has_unsaved_data(self) -> bool:
        """Возвращает True если есть незаполненные/несохранённые данные."""
        probe = self._probe_field.value if hasattr(self, '_probe_field') else ""
        sp = self._sp_block.total_value if hasattr(self, '_sp_block') else ""
        zp = self._zp_block.total_value if hasattr(self, '_zp_block') else ""
        return bool(probe or sp or zp)

    def _on_reset(self) -> None:
        self._probe_field.clear()
        self._sp_block.clear()
        self._zp_block.clear()
        self._sp_block.clear_bumped_total()
        self._zp_block.clear_bumped_total()
        self._grain_widget.clear()
        self._hparams.clear()
        self._recalc_impurities()

    def showEvent(self, event) -> None:
        """Перезагружаем культуры при каждом открытии — чтобы нормы были актуальными."""
        super().showEvent(event)
        if hasattr(self, '_cult_combo'):
            current_name = self._cult_combo.currentText()
            self._load_cultures()
            idx = self._cult_combo.findText(current_name)
            if idx >= 0:
                self._cult_combo.setCurrentIndex(idx)
        # Автофокус на поле № пробы
        if hasattr(self, '_probe_field'):
            QTimer.singleShot(50, self._probe_field.input.setFocus)

    def _focus_next_field(self) -> None:
        """Enter в поле пробы — переводит фокус на следующий видимый ввод."""
        # Список полей в порядке Tab-обхода
        candidates = [
            self._type_combo[1],
            self._cult_combo,
        ]
        for field in [
            getattr(self, '_silo_widget', None),
            getattr(self, '_origin_widget', None),
            getattr(self, '_year_field', None),
            getattr(self, '_supplier_field', None),
            getattr(self, '_consignee_field', None),
            getattr(self, '_place_widget', None),
        ]:
            if field is not None and field.isVisible():
                # Для _Field берём .input, для QWidget с комбо — дочерний QComboBox
                inner = getattr(field, 'input', None) or field.findChild(__import__('PyQt6.QtWidgets', fromlist=['QLineEdit']).QLineEdit)
                if inner:
                    candidates.append(inner)
        if candidates:
            candidates[0].setFocus()
