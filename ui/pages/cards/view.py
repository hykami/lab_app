"""
Карточки → Просмотр.
Список карточек с чекбоксами для выбора + детальный просмотр + кнопка «Печать».
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
    QMessageBox,
)

from ui.pages.base_page import BasePage
from ui.theme import (
    BG, BG_CARD, BORDER,
    TEXT_MUTED, TEXT_BRIGHT, ACCENT_G,
    ACCENT_ICON, FONT_MONO, FONT_UI,
)
from logic.db_service import (
    Card, get_all_cards, get_all_cultures, get_all_silos,
    delete_card, delete_cards_bulk, update_card_params, get_culture_with_norms,
)
from logic.card_params import PARAM_META, validate_params, CARD_TYPE_WASTE
from ui.components.validation import (
    make_param_validator, make_imp_pct_validator, make_imp_total_validator,
)
from ui.style_helpers import scroll_style, combo_style
from ui.components.impurity_block import ImpurityBlock as _ImpurityBlock
from ui.components.rounded_clip import RoundedClipFrame


# ── Карточка в списке (с чекбоксом) ──────────────────────────────────────────

class CardListItem(QFrame):
    def __init__(self, card: Card, on_select: callable,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._card = card
        self._on_select = on_select
        self._selected = False
        self._apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        # ── Основная строка ───────────────────────────────────────────────────
        self._main_row = QWidget()
        self._main_row.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self._main_row)
        lay.setContentsMargins(8, 6, 6, 6)
        lay.setSpacing(6)

        # Номер пробы
        num = QLabel(f"#{card.probe_number}")
        num.setStyleSheet(
            f"color: {ACCENT_ICON}; background: rgba(108,92,231,0.1);"
            f"border: 0.5px solid rgba(108,92,231,0.25); border-radius: 4px;"
            f"font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 1px 6px;"
        )
        num.setFixedWidth(54)
        lay.addWidget(num)

        # Культура
        cult = QLabel(card.culture_name)
        cult.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        cult.setMinimumWidth(0)
        lay.addWidget(cult, 1)

        # Тег типа/места карточки
        card_type = (getattr(card, "card_type", "") or "")
        place_text = (getattr(card, "distillation_place", "") or "")

        _PLACE_MAP = {
            "мукомолка": ("Мук.",   "rgba(251,191,36,0.08)",  "#fbbf24", "rgba(251,191,36,0.25)"),
            "крс":       ("КРС",    "rgba(96,165,250,0.08)",  "#60a5fa", "rgba(96,165,250,0.2)"),
            "свинки":    ("Свинки", "rgba(168,139,255,0.08)", "#a89cff", "rgba(108,92,231,0.25)"),
            "рыбы":      ("Рыбы",   "rgba(74,222,128,0.06)",  "#4ade80", "rgba(74,222,128,0.2)"),
        }
        _TYPE_MAP = {
            "входной контроль":       ("ВхК",    "rgba(248,113,113,0.07)", "#f87171", "rgba(248,113,113,0.22)"),
            "отгрузка":               ("Отгр.",  "rgba(96,165,250,0.07)",  "#60a5fa", "rgba(96,165,250,0.2)"),
            "очистка":                ("Очист.", "rgba(74,222,128,0.06)",  "#4ade80", "rgba(74,222,128,0.2)"),
            "контроль при хранении":  ("КпХ",   "rgba(251,191,36,0.07)",  "#fbbf24", "rgba(251,191,36,0.22)"),
            "отходы":                 ("Отх.",   "rgba(168,139,255,0.07)", "#a89cff", "rgba(108,92,231,0.22)"),
        }

        if card_type.lower() == "перегонка" and place_text:
            tag_data = _PLACE_MAP.get(place_text.lower())
            if tag_data is None:
                tag_data = (place_text[:4] + ".", "transparent", TEXT_MUTED, BORDER)
        elif card_type.lower() in _TYPE_MAP:
            tag_data = _TYPE_MAP[card_type.lower()]
        else:
            tag_data = None

        if tag_data:
            ptag, bg, fg, bd = tag_data
            type_lbl = QLabel(ptag)
            type_lbl.setStyleSheet(
                f"background: {bg}; color: {fg}; border: 0.5px solid {bd};"
                f" border-radius: 3px; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 12px; padding: 1px 4px;"
            )
            lay.addWidget(type_lbl)

        self._outer.addWidget(self._main_row)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_select(self._card)
        super().mousePressEvent(event)

    def _apply_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                "QFrame { background: rgba(108,92,231,0.12);"
                " border: 0.5px solid rgba(108,92,231,0.5); border-radius: 8px; }"
            )
        else:
            self.setStyleSheet(
                f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 8px; }}"
                "QFrame:hover { border-color: #5a5a72; }"
            )

    def set_selected(self, selected: bool) -> None:
        """Подсветка строки (детальный просмотр)."""
        self._selected = selected
        self._apply_style()

    @property
    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def set_checked(self, checked: bool) -> None:
        self._checkbox.blockSignals(True)
        self._checkbox.setChecked(checked)
        self._checkbox.blockSignals(False)


# ── Детальный просмотр карточки ───────────────────────────────────────────────

class CardDetailPanel(QScrollArea):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(scroll_style(border_left=True))
        self._inner = QWidget()
        self._inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._inner.setStyleSheet(f"background: {BG};")
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(12, 12, 12, 12)
        self._lay.setSpacing(12)
        self._current_card: Optional[Card] = None
        self._edit_mode: bool = False
        self._on_card_saved = None   # колбэк (card) -> None — для обновления списка
        self._imp_total_labels: dict = {}
        self._show_placeholder()
        self.setWidget(self._inner)

    def _show_placeholder(self) -> None:
        ph = QLabel("Выберите карточку из списка")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet(
            f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 13px; background: transparent; border: none;"
        )
        self._lay.addWidget(ph)
        self._lay.addStretch()

    def _clear_layout(self) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def clear(self) -> None:
        self._clear_layout()
        self._show_placeholder()

    def show_card(self, card: Card) -> None:
        self._current_card = card
        self._edit_mode = False
        self._clear_layout()

        self._lay.setContentsMargins(14, 14, 14, 14)
        self._lay.setSpacing(10)

        # ── Заголовок ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)
        num_lbl = QLabel(f"#{card.probe_number}")
        num_lbl.setStyleSheet(
            f"color: {ACCENT_ICON}; background: rgba(108,92,231,0.1);"
            f"border: 0.5px solid rgba(108,92,231,0.25); border-radius: 6px;"
            f"font-family: '{FONT_UI}', sans-serif; font-size: 13px; padding: 3px 11px;"
        )
        hdr.addWidget(num_lbl)
        cult_lbl = QLabel(card.culture_name)
        cult_lbl.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 15px; font-weight: 500; background: transparent; border: none;"
        )
        hdr.addWidget(cult_lbl, 1)

        edit_btn = QPushButton("Редактировать")
        edit_btn.setFixedHeight(26)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 0.5px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_MUTED};"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 0 12px; }}"
            "QPushButton:hover { border-color: rgba(108,92,231,0.5); color: #a89cff; "
            "background: rgba(108,92,231,0.06); }"
        )
        edit_btn.clicked.connect(lambda: self._open_edit(card))
        hdr.addWidget(edit_btn)

        hdr_w = QWidget()
        hdr_w.setStyleSheet("background: transparent;")
        hdr_w.setLayout(hdr)
        self._lay.addWidget(hdr_w)

        # ── Метаданные одной строкой ─────────────────────────────────────────
        meta_parts = []
        if getattr(card, 'card_type', None):
            meta_parts.append(card.card_type)
        if getattr(card, 'silo_id', None):
            silos = get_all_silos()
            silo = next((s for s in silos if s.id == card.silo_id), None)
            if silo:
                meta_parts.append(f"Силос {silo.number}")
        if getattr(card, 'distillation_place', None):
            meta_parts.append(card.distillation_place)
        if getattr(card, 'created_at', None):
            meta_parts.append(card.created_at[:10])

        if meta_parts:
            meta_lbl = QLabel(" · ".join(meta_parts))
            meta_lbl.setStyleSheet(
                f"color: #606075; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            self._lay.addWidget(meta_lbl)

        # ── СП и ЗП рядом ────────────────────────────────────────────────────
        imp_row = QHBoxLayout()
        imp_row.setContentsMargins(0, 0, 0, 0)
        imp_row.setSpacing(8)
        is_ic = card.incoming_ctrl and card.sp_base is not None
        imp_row.addWidget(self._build_imp_card(
            "СП", "СОРНАЯ ПРИМЕСЬ", "#f87171",
            card.sp_total, card.sp_items,
            base_total=card.sp_base if is_ic else None,
            base_items=card.sp_items_base if is_ic else None,
            culture_name=card.culture_name,
        ), 1)
        imp_row.addWidget(self._build_imp_card(
            "ЗП", "ЗЕРНОВАЯ ПРИМЕСЬ", "#fbbf24",
            card.zp_total, card.zp_items,
            base_total=card.zp_base if is_ic else None,
            base_items=card.zp_items_base if is_ic else None,
            culture_name=card.culture_name,
        ), 1)
        imp_w = QWidget()
        imp_w.setStyleSheet("background: transparent;")
        imp_w.setLayout(imp_row)
        self._lay.addWidget(imp_w)

        # ── Полоса основного зерна ───────────────────────────────────────────
        cultures = get_all_cultures()
        naveski = next((c.sample_weight for c in cultures if c.name == card.culture_name), None)
        if naveski is not None:
            _WHEAT_BROKEN = {"Пшеница 3 кл.", "Пшеница 4 кл."}

            def _fixed_grams(item: dict) -> float:
                """Граммы с учётом специального правила для Битых у пшеницы 3/4 кл."""
                if item.get("name") == "Битые" and card.culture_name in _WHEAT_BROKEN:
                    return item.get("percent", 0) or 0
                return item.get("grams", 0) or 0

            # Для входного контроля берём накинутые значения (sp_items/zp_items),
            # для обычных карточек — те же sp_items/zp_items (они и есть итоговые)
            sp_sum = round(sum(_fixed_grams(i) for i in card.sp_items), 2)
            zp_sum = round(sum(_fixed_grams(i) for i in card.zp_items), 2)
            grain = round(naveski - sp_sum - zp_sum, 2)
            self._lay.addWidget(self._build_grain_bar(naveski, sp_sum, zp_sum, grain))

        # ── Показатели ───────────────────────────────────────────────────────
        params_keys = [
            ("humidity",     "Влажность, %"),
            ("natura",       "Натура, г/л"),
            ("gluten",       "Клейковина (эксп.), %"),
            ("gluten_arb",   "Клейковина (арб.), %"),
            ("protein",      "Белок, %"),
            ("vitreousness", "Стекловидн., %"),
            ("idc",          "ИДК"),
            ("fall_number",  "ЧП, с"),
        ]
        active = [(k, l) for k, l in params_keys if getattr(card, k, None) is not None]
        if active:
            self._lay.addWidget(self._build_params_grid(card, active))

        self._lay.addStretch()

    # ── Компактные блоки ─────────────────────────────────────────────────────────
    def _build_imp_card(self, group: str, title: str, color: str,
                        total: float, items: list,
                        base_total: float = None,
                        base_items: list = None,
                        culture_name: str = "") -> QFrame:
        from logic.calc_utils import calc_grams
        _WHEAT_BROKEN = {"Пшеница 3 кл.", "Пшеница 4 кл."}

        # RGB для hover-подсветки строк
        _COLOR_RGB = {
            "#f87171": "248,113,113",
            "#fbbf24": "251,191,36",
        }
        color_rgb = _COLOR_RGB.get(color, "108,92,231")

        def _fix_grams(item: dict) -> dict:
            """П.2: для Битых у пшеницы 3/4 кл. граммы = %"""
            if item.get("name") == "Битые" and culture_name in _WHEAT_BROKEN:
                return {**item, "grams": item.get("percent", 0)}
            return item

        f = QFrame()
        f.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 8px; }}")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(6)

        # ── Шапка с итоговым % ───────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(0)
        t_lbl = QLabel(f"{group} — {title.lower()}")
        t_lbl.setStyleSheet(
            f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        hdr.addWidget(t_lbl, 1)

        # П.4: для входного контроля показываем base (bumped) в шапке
        if base_total is not None and total is not None:
            total_text = f"{base_total:.2f} ({total:.2f})%"
        else:
            total_text = f"{total:.2f}%" if total is not None else "—"

        total_lbl = QLabel(total_text)
        total_lbl.setStyleSheet(
            f"color: {color}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 16px; font-weight: 300; background: transparent; border: none;"
        )
        hdr.addWidget(total_lbl)
        hw = QWidget(); hw.setStyleSheet("background: transparent;"); hw.setLayout(hdr)
        lay.addWidget(hw)

        # ── Список позиций ───────────────────────────────────────────────────
        # Если входной контроль — zip base_items + items, иначе только items
        has_ic = base_items is not None and items is not None
        pairs: list[tuple[dict, dict | None]] = []
        if has_ic:
            base_map = {i.get("name"): i for i in base_items}
            bump_map = {i.get("name"): i for i in items}
            all_names = list({i.get("name") for i in base_items} |
                             {i.get("name") for i in items})
            # сохраняем порядок base_items
            ordered = [i.get("name") for i in base_items]
            for n in all_names:
                if n not in ordered:
                    ordered.append(n)
            pairs = [(base_map.get(n, {}), bump_map.get(n)) for n in ordered]
        else:
            pairs = [(_fix_grams(i), None) for i in (items or [])]

        any_nonzero = False
        rows_to_add = []
        for base_it, bump_it in pairs:
            name = base_it.get("name", "") or (bump_it.get("name", "") if bump_it else "")
            base_it = _fix_grams(base_it)
            if bump_it:
                bump_it = _fix_grams(bump_it)

            base_g = base_it.get("grams", 0) or 0
            base_p = base_it.get("percent", 0) or 0
            bump_g = bump_it.get("grams", 0) if bump_it else None
            bump_p = bump_it.get("percent", 0) if bump_it else None

            # П.1: скрываем позиции с нулевым значением
            if base_p == 0 and (bump_p is None or bump_p == 0):
                continue

            any_nonzero = True

            # Формируем текст значения
            if has_ic and bump_it is not None:
                # П.4: 0.27 (0.47) г / 0.54 (0.94) %
                v_text = f"{base_g:.2f} ({bump_g:.2f}) г / {base_p:.2f} ({bump_p:.2f})%"
            elif base_p is not None:
                v_text = f"{base_g:.2f} г / {base_p:.2f}%"
            else:
                v_text = f"{base_g:.2f} г"

            rows_to_add.append((name, v_text))

        if rows_to_add:
            for name, v_text in rows_to_add:
                row = QHBoxLayout()
                row.setContentsMargins(4, 3, 4, 3)
                row.setSpacing(0)
                n_lbl = QLabel(name)
                n_lbl.setStyleSheet(
                    f"color: #6a6a80; font-family: '{FONT_UI}', sans-serif;"
                    "font-size: 11px; background: transparent; border: none;"
                )
                row.addWidget(n_lbl, 1)
                v_lbl = QLabel(v_text)
                v_lbl.setStyleSheet(
                    f"color: #8080a0; font-family: '{FONT_UI}', sans-serif;"
                    "font-size: 12px; background: transparent; border: none;"
                )
                row.addWidget(v_lbl)
                rw = QWidget()
                rw.setLayout(row)
                rw.setCursor(Qt.CursorShape.PointingHandCursor)
                rw.setStyleSheet("background: transparent; border-radius: 4px;")
                rw.setProperty("hovered", False)

                def _make_enter(w, c):
                    def _enter(e):
                        w.setStyleSheet(f"background: rgba({c},0.07); border-radius: 4px;")
                    return _enter

                def _make_leave(w):
                    def _leave(e):
                        w.setStyleSheet("background: transparent; border-radius: 4px;")
                    return _leave

                rw.enterEvent = _make_enter(rw, color_rgb)
                rw.leaveEvent = _make_leave(rw)
                lay.addWidget(rw)
        else:
            none_lbl = QLabel("— нет позиций —")
            none_lbl.setStyleSheet(
                f"color: #525265; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            lay.addWidget(none_lbl)
        return f

    def _build_grain_bar(self, naveski: float, sp_sum: float,
                         zp_sum: float, grain: float) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 8px; }}")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(7)

        # Заголовок
        title = QLabel("ОСНОВНОЕ ЗЕРНО")
        title.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        lay.addWidget(title)

        # Полоса
        total = max(naveski, 0.01)
        grain_pct = max(grain, 0) / total * 100
        sp_pct = sp_sum / total * 100
        zp_pct = zp_sum / total * 100

        bar = QWidget()
        bar.setFixedHeight(8)
        bar.setStyleSheet("background: transparent;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        for w_pct, col in [(grain_pct, "rgba(74,222,128,0.7)"),
                            (sp_pct, "rgba(248,113,113,0.7)"),
                            (zp_pct, "rgba(251,191,36,0.7)")]:
            seg = QWidget()
            seg.setStyleSheet(f"background: {col}; border: none;")
            seg.setFixedHeight(8)
            bl.addWidget(seg, max(int(w_pct * 100), 1))
        lay.addWidget(bar)

        # Легенда
        legend = QHBoxLayout()
        legend.setContentsMargins(0, 0, 0, 0)
        legend.setSpacing(14)
        for label, val, col in [
            ("Зерно", grain, "#4ade80"),
            ("СП", sp_sum, "#f87171"),
            ("ЗП", zp_sum, "#fbbf24"),
        ]:
            cell = QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.setSpacing(5)
            dot = QLabel("")
            dot.setFixedSize(7, 7)
            dot.setStyleSheet(f"background: {col}; border-radius: 2px;")
            cell.addWidget(dot)
            txt = QLabel(f"{label} {val:.2f} г")
            txt.setStyleSheet(
                f"color: #6a6a80; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            cell.addWidget(txt)
            cw = QWidget(); cw.setStyleSheet("background: transparent;"); cw.setLayout(cell)
            legend.addWidget(cw)
        legend.addStretch()
        lw = QWidget(); lw.setStyleSheet("background: transparent;"); lw.setLayout(legend)
        lay.addWidget(lw)
        return f

    def _build_params_grid(self, card: Card, active: list) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 8px; }}")
        outer = QVBoxLayout(f)
        outer.setContentsMargins(10, 9, 10, 9)
        outer.setSpacing(7)

        title = QLabel("ПОКАЗАТЕЛИ")
        title.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        outer.addWidget(title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        COLS = 4
        for idx, (key, label) in enumerate(active):
            val = getattr(card, key, None)
            if val is None:
                continue
            _, _, decimals = PARAM_META.get(key, ("", "", 1))
            ri, ci = divmod(idx, COLS)
            cell = QFrame()
            cell.setStyleSheet(
                f"QFrame {{ background: #111114; border: 0.5px solid {BORDER}; border-radius: 6px; }}"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(8, 6, 8, 7)
            cl.setSpacing(2)
            l_lbl = QLabel(label)
            l_lbl.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent; border: none;"
            )
            v_lbl = QLabel(f"{val:.{decimals}f}")
            v_lbl.setStyleSheet(
                f"color: #c0c0d8; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 14px; font-weight: 300; background: transparent; border: none;"
            )
            cl.addWidget(l_lbl)
            cl.addWidget(v_lbl)
            grid.addWidget(cell, ri, ci)
        gw = QWidget(); gw.setStyleSheet("background: transparent;"); gw.setLayout(grid)
        outer.addWidget(gw)
        return f


    # ── Редактирование ─────────────────────────────────────────────────────────

    def _open_edit(self, card: Card) -> None:
        """Перестраивает панель в режим редактирования."""
        self._edit_mode = True
        self._current_card = card
        self._clear_layout()

        # Заголовок
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        num_lbl = QLabel(f"# {card.probe_number}")
        num_lbl.setStyleSheet(
            f"color: {ACCENT_ICON}; background: rgba(108,92,231,0.1);"
            f"border: 0.5px solid rgba(108,92,231,0.25); border-radius: 6px;"
            f"font-family: '{FONT_UI}', sans-serif; font-size: 14px; padding: 3px 12px;"
        )
        hdr.addWidget(num_lbl)
        cult_lbl = QLabel(card.culture_name)
        cult_lbl.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 16px; font-weight: 600; background: transparent;"
        )
        hdr.addWidget(cult_lbl, 1)
        hdr_w = QWidget(); hdr_w.setStyleSheet("background: transparent;")
        hdr_w.setLayout(hdr)
        self._lay.addWidget(hdr_w)

        # ── Показатели ────────────────────────────────────────────────────────
        is_waste = (card.card_type == CARD_TYPE_WASTE)
        params_keys = [("humidity", "Влажность, %", 1)]
        if not is_waste:
            params_keys += [
                ("natura",       "Натура, г/л",               0),
                ("gluten",       "Клейковина (экспресс), %",  1),
                ("gluten_arb",   "Клейковина (арбитраж), %",  1),
                ("protein",      "М.д. белка, %",             1),
                ("vitreousness", "Стекловидность, %",         0),
                ("idc",          "ИДК",                       0),
                ("fall_number",  "ЧП, с",                     0),
            ]
        active_params = [(k, l, d) for k, l, d in params_keys if getattr(card, k, None) is not None]

        culture_obj = get_culture_with_norms(
            next((c.id for c in get_all_cultures() if c.name == card.culture_name), -1)
        )
        self._param_inputs: dict[str, QLineEdit] = {}
        if active_params:
            pframe = QFrame()
            pframe.setStyleSheet(
                f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
            )
            play = QVBoxLayout(pframe); play.setContentsMargins(0,0,0,0); play.setSpacing(0)
            phdr = QWidget()
            phdr.setStyleSheet(
                f"background: rgba(108,92,231,0.06); border-radius: 10px 10px 0 0;"
                f"border-bottom: 0.5px solid {BORDER};"
            )
            phl = QHBoxLayout(phdr); phl.setContentsMargins(14,9,14,9)
            pt = QLabel("ПОКАЗАТЕЛИ")
            pt.setStyleSheet(
                f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
            )
            phl.addWidget(pt)
            play.addWidget(phdr)
            grid_w = QWidget(); grid_w.setStyleSheet("background: transparent;")
            grid = QGridLayout(grid_w); grid.setContentsMargins(14,10,14,12); grid.setSpacing(8)
            COLS = 4
            for idx, (key, label, decimals) in enumerate(active_params):
                ri, ci = divmod(idx, COLS)
                cell = QWidget(); cell.setStyleSheet("background: transparent;")
                cl = QVBoxLayout(cell); cl.setContentsMargins(0,0,0,0); cl.setSpacing(3)
                lbl = QLabel(label)
                lbl.setStyleSheet(
                    f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                    "font-size: 12px; font-weight: 500; background: transparent; border: none;"
                )
                inp = QLineEdit()
                val = getattr(card, key, None)
                inp.setText(f"{val:.{decimals}f}" if val is not None else "")
                inp.setFixedHeight(32)
                inp.setStyleSheet(
                    f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
                    f" border-radius: 6px; color: {TEXT_BRIGHT};"
                    f" font-family: '{FONT_MONO}', monospace; font-size: 13px; padding: 0 8px; }}"
                    "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
                )
                cl.addWidget(lbl); cl.addWidget(inp)
                grid.addWidget(cell, ri, ci)
                self._param_inputs[key] = inp
                inp.textEdited.connect(
                    make_param_validator(key, inp, culture_obj,
                                         bg="#111114", font_size=13, radius=6)
                )
            play.addWidget(grid_w)
            self._lay.addWidget(pframe)

        # ── СП / ЗП ───────────────────────────────────────────────────────────
        # _imp_inputs: list of dicts per group with keys: name, pct_inp, grm_lbl
        # _imp_sp_total_inp / _imp_zp_total_inp: QLineEdit для итогового %
        self._imp_inputs: dict[str, list[dict]] = {"СП": [], "ЗП": []}
        if not is_waste:
            sample_w = next(
                (c.sample_weight for c in get_all_cultures() if c.name == card.culture_name),
                50.0
            )
            self._edit_culture_obj = culture_obj
            two = QHBoxLayout(); two.setSpacing(10); two.setContentsMargins(0,0,0,0)
            for group, items, total in [
                ("СП", card.sp_items, card.sp_total),
                ("ЗП", card.zp_items, card.zp_total),
            ]:
                two.addWidget(self._build_imp_edit_block(group, items, total, sample_w))
            tw = QWidget(); tw.setStyleSheet("background: transparent;")
            tw.setLayout(two); self._lay.addWidget(tw)

        # ── Кнопки ────────────────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0,4,0,0); btn_row.setSpacing(8)
        btn_row.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 0.5px solid {BORDER};"
            f" border-radius: 7px; color: {TEXT_MUTED};"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 16px; }}"
            "QPushButton:hover { border-color: #5a5a72; color: #c0c0c8; }"
        )
        cancel_btn.clicked.connect(lambda: self.show_card(card))
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Сохранить")
        save_btn.setFixedHeight(32)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(
            "QPushButton { background: rgba(108,92,231,0.15);"
            " border: 0.5px solid rgba(108,92,231,0.4); border-radius: 7px;"
            " color: #a89cff; font-family: '" + FONT_UI + "', sans-serif;"
            " font-size: 12px; padding: 0 16px; }"
            "QPushButton:hover { background: rgba(108,92,231,0.25); }"
        )
        save_btn.clicked.connect(self._on_save_edit)
        btn_row.addWidget(save_btn)

        btn_w = QWidget(); btn_w.setStyleSheet("background: transparent;")
        btn_w.setLayout(btn_row)
        self._lay.addWidget(btn_w)
        self._lay.addStretch()


    def _build_imp_edit_block(self, group: str, items: list,
                                total: float, sample_w: float) -> QFrame:
        """
        Строит редактируемый блок примесей.
        Пользователь вводит % примесей — граммы пересчитываются автоматически.
        Отдельное поле для итогового % (СП/ЗП) с пересчётом примесей пропорционально.
        """
        is_sp = (group == "СП")
        hdr_bg  = "rgba(248,113,113,0.06)" if is_sp else "rgba(108,92,231,0.06)"
        txt_col = "#f87171" if is_sp else "#6c5ce7"
        title   = "СОРНАЯ ПРИМЕСЬ" if is_sp else "ЗЕРНОВАЯ ПРИМЕСЬ"
        inp_attr = "_imp_sp_total_inp" if is_sp else "_imp_zp_total_inp"

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
        )
        lay = QVBoxLayout(frame); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # ── Заголовок с редактируемым итогом ─────────────────────────────────
        hdr_w = QWidget()
        hdr_w.setStyleSheet(
            f"background: {hdr_bg}; border-radius: 10px 10px 0 0; border-bottom: 0.5px solid {BORDER};"
        )
        hl = QHBoxLayout(hdr_w); hl.setContentsMargins(14,7,14,7); hl.setSpacing(6)
        t = QLabel(title)
        t.setStyleSheet(
            f"color: {txt_col}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        hl.addWidget(t); hl.addStretch()

        total_inp = QLineEdit(f"{total:.2f}")
        total_inp.setFixedSize(68, 26)
        total_inp.setStyleSheet(
            f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
            f" border-radius: 5px; color: #c0c0c8;"
            f" font-family: '{FONT_MONO}', monospace; font-size: 11px; padding: 0 5px; }}"
            "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
        )
        pct_sfx = QLabel("%")
        pct_sfx.setStyleSheet(
            f"color: {txt_col}; font-size: 11px; background: transparent; border: none;"
        )
        hl.addWidget(total_inp); hl.addWidget(pct_sfx)
        setattr(self, inp_attr, total_inp)
        lay.addWidget(hdr_w)

        # ── Заголовок колонок ─────────────────────────────────────────────────
        col_hdr = QWidget(); col_hdr.setFixedHeight(24)
        col_hdr.setStyleSheet(f"background: #111114; border-bottom: 0.5px solid {BORDER};")
        cl = QHBoxLayout(col_hdr); cl.setContentsMargins(14,0,14,0); cl.setSpacing(0)
        for txt, w in [("ПРИМЕСЬ", 0), ("%", 64), ("  ", 6), ("ГР", 52)]:
            lb = QLabel(txt)
            lb.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
            )
            if w: lb.setFixedWidth(w); lb.setAlignment(Qt.AlignmentFlag.AlignCenter); cl.addWidget(lb)
            else: cl.addWidget(lb, 1)
        lay.addWidget(col_hdr)

        # ── Строки примесей ───────────────────────────────────────────────────
        # Строим словарь норм примесей {name: (min, max)} из культуры
        imp_norms: dict[str, tuple[float, float]] = {}
        if hasattr(self, '_edit_culture_obj') and self._edit_culture_obj:
            for imp_norm in getattr(self._edit_culture_obj, 'impurities', []):
                if imp_norm.group_name == group:
                    imp_norms[imp_norm.name] = (imp_norm.min_val, imp_norm.max_val)

        row_data = self._imp_inputs[group]
        for i, imp in enumerate(items):
            name_val = imp.get("name", "—") if isinstance(imp, dict) else imp.name
            grm_val  = imp.get("grams", 0)   if isinstance(imp, dict) else imp.grams
            pct_val  = imp.get("percent", 0)  if isinstance(imp, dict) else imp.percent

            row = QWidget(); row.setFixedHeight(36)
            row.setStyleSheet(
                "background: transparent;" +
                ("" if i == len(items)-1 else "border-bottom: 0.5px solid #1a1a1e;")
            )
            rl = QHBoxLayout(row); rl.setContentsMargins(14,0,14,0); rl.setSpacing(4)

            nm = QLabel(name_val)
            nm.setStyleSheet(
                f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            rl.addWidget(nm, 1)

            pct_inp = QLineEdit(f"{pct_val:.2f}")
            pct_inp.setFixedSize(60, 26)
            pct_inp.setStyleSheet(
                f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
                " border-radius: 5px; color: #c0c0c8;"
                f" font-family: '{FONT_MONO}', monospace; font-size: 11px; padding: 0 5px; }}"
                "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
            )
            rl.addWidget(pct_inp)

            grm_lbl = QLabel(f"{grm_val:.2f}")
            grm_lbl.setFixedWidth(48)
            grm_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grm_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-family: '{FONT_MONO}', monospace;"
                "font-size: 11px; background: transparent; border: none;"
            )
            rl.addWidget(grm_lbl)

            lay.addWidget(row)
            entry = {"name": name_val, "pct_inp": pct_inp, "grm_lbl": grm_lbl}
            row_data.append(entry)

            # При изменении % примеси — пересчитываем граммы, обновляем итог и валидируем
            pct_inp.textChanged.connect(
                lambda _, g=group, sw=sample_w: self._recalc_imp_from_pct(g, sw)
            )
            _n_min, _n_max = imp_norms.get(name_val, (0.0, 100.0))
            pct_inp.textEdited.connect(make_imp_pct_validator(pct_inp, _n_min, _n_max))

        # При изменении итогового % — пересчитываем примеси пропорционально + валидируем
        total_inp.textChanged.connect(
            lambda _, g=group, sw=sample_w: self._recalc_imp_from_total(g, sw)
        )
        total_inp.textEdited.connect(
            make_imp_total_validator(total_inp, group, self._edit_culture_obj)
        )

        return frame

    def _recalc_imp_from_pct(self, group: str, sample_w: float) -> None:
        """Пересчитывает граммы и итог при изменении % отдельной примеси."""
        row_data = self._imp_inputs.get(group, [])
        total_pct = 0.0
        for entry in row_data:
            try:
                pct = float(entry["pct_inp"].text().replace(",", "."))
            except ValueError:
                pct = 0.0
            grm = round(pct / 100 * sample_w, 4) if sample_w else 0.0
            total_pct += pct
            entry["grm_lbl"].setText(f"{grm:.2f}")

        # Обновляем итоговое поле без рекурсии
        inp_attr = "_imp_sp_total_inp" if group == "СП" else "_imp_zp_total_inp"
        total_inp = getattr(self, inp_attr, None)
        if total_inp:
            total_inp.blockSignals(True)
            total_inp.setText(f"{total_pct:.2f}")
            total_inp.blockSignals(False)

    def _recalc_imp_from_total(self, group: str, sample_w: float) -> None:
        """При изменении итогового % — пересчитывает примеси пропорционально."""
        inp_attr = "_imp_sp_total_inp" if group == "СП" else "_imp_zp_total_inp"
        total_inp = getattr(self, inp_attr, None)
        if not total_inp:
            return
        try:
            new_total = float(total_inp.text().replace(",", "."))
        except ValueError:
            return

        row_data = self._imp_inputs.get(group, [])
        # Текущая сумма %
        cur_sum = 0.0
        for entry in row_data:
            try:
                cur_sum += float(entry["pct_inp"].text().replace(",", "."))
            except ValueError:
                pass

        if cur_sum == 0:
            # Делим поровну
            share = new_total / len(row_data) if row_data else 0.0
            for entry in row_data:
                entry["pct_inp"].blockSignals(True)
                entry["pct_inp"].setText(f"{share:.2f}")
                entry["pct_inp"].blockSignals(False)
                grm = round(share / 100 * sample_w, 4)
                entry["grm_lbl"].setText(f"{grm:.2f}")
        else:
            factor = new_total / cur_sum
            for entry in row_data:
                try:
                    old_pct = float(entry["pct_inp"].text().replace(",", "."))
                except ValueError:
                    old_pct = 0.0
                new_pct = round(old_pct * factor, 4)
                entry["pct_inp"].blockSignals(True)
                entry["pct_inp"].setText(f"{new_pct:.2f}")
                entry["pct_inp"].blockSignals(False)
                grm = round(new_pct / 100 * sample_w, 4)
                entry["grm_lbl"].setText(f"{grm:.2f}")

    def _on_save_edit(self) -> None:
        """Валидирует и сохраняет изменения карточки."""
        card = self._current_card

        # ── Парсим показатели ─────────────────────────────────────────────────
        def _parse(key: str) -> float | None:
            inp = self._param_inputs.get(key)
            if inp is None:
                return getattr(card, key, None)
            txt = inp.text().strip().replace(",", ".")
            if not txt:
                return None
            try:
                return float(txt)
            except ValueError:
                return None

        params_keys = [
            "humidity", "natura", "gluten", "gluten_arb", "protein",
            "vitreousness", "idc", "fall_number",
        ]
        new_vals = {k: _parse(k) for k in params_keys}

        # ── Валидация показателей (как на странице Создать) ───────────────────
        culture_obj = get_culture_with_norms(
            next((c.id for c in get_all_cultures() if c.name == card.culture_name), -1)
        )
        active_keys = [k for k in params_keys if new_vals.get(k) is not None]
        user_strs = {k: str(new_vals[k]) for k in active_keys}
        errors = validate_params(user_strs, active_keys, culture=culture_obj)

        # Подсвечиваем поля показателей
        err_style  = f"background: #111114; border: 0.5px solid rgba(248,113,113,0.7); border-radius: 6px; color: {TEXT_BRIGHT}; font-family: '{FONT_MONO}', monospace; font-size: 13px; padding: 0 8px;"
        ok_style   = f"background: #111114; border: 0.5px solid {BORDER}; border-radius: 6px; color: {TEXT_BRIGHT}; font-family: '{FONT_MONO}', monospace; font-size: 13px; padding: 0 8px;"
        focus_ok   = "QLineEdit { " + ok_style  + " } QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
        focus_err  = "QLineEdit { " + err_style + " } QLineEdit:focus { border-color: rgba(248,113,113,0.7); }"
        for key, inp in self._param_inputs.items():
            inp.setStyleSheet(focus_err if key in errors else focus_ok)

        if errors:
            return

        # ── Собираем примеси ──────────────────────────────────────────────────
        sample_w = next(
            (c.sample_weight for c in get_all_cultures() if c.name == card.culture_name),
            50.0
        )

        def _collect_imp(group: str) -> tuple[float, list]:
            rows = self._imp_inputs.get(group, [])
            items = []
            total = 0.0
            for entry in rows:
                try:
                    pct = round(float(entry["pct_inp"].text().replace(",", ".")), 4)
                except ValueError:
                    pct = 0.0
                grm = round(pct / 100 * sample_w, 4) if sample_w else 0.0
                total += pct
                items.append({"name": entry["name"], "grams": grm, "percent": pct})
            return round(total, 4), items

        if card.card_type == CARD_TYPE_WASTE:
            sp_total, sp_items = card.sp_total, card.sp_items
            zp_total, zp_items = card.zp_total, card.zp_items
        else:
            sp_total, sp_items = _collect_imp("СП")
            zp_total, zp_items = _collect_imp("ЗП")

        # ── Сохраняем ─────────────────────────────────────────────────────────
        update_card_params(
            card_id=card.id,
            humidity=new_vals["humidity"],
            natura=new_vals["natura"],
            gluten=new_vals["gluten"],
            gluten_arb=new_vals["gluten_arb"],
            protein=new_vals["protein"],
            vitreousness=new_vals["vitreousness"],
            idc=new_vals["idc"],
            fall_number=new_vals["fall_number"],
            sp_total=sp_total,
            sp_items=sp_items,
            zp_total=zp_total,
            zp_items=zp_items,
        )

        # Обновляем объект и перерисовываем просмотр
        from logic.db_service import get_card
        updated = get_card(card.id)
        if updated:
            self._current_card = updated
            self.show_card(updated)
            if self._on_card_saved:
                self._on_card_saved(updated)

    def _grain_block(self, naveski: float, sp_sum: float,
                     zp_sum: float, grain: float) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        def _part(label: str, value: str, color: str) -> QWidget:
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            wl = QVBoxLayout(w)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; font-weight: 500; background: transparent; border: none;"
            )
            val = QLabel(value)
            val.setStyleSheet(
                f"color: {color}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 18px; font-weight: 300; background: transparent; border: none;"
            )
            wl.addWidget(lbl)
            wl.addWidget(val)
            return w

        def _op(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 18px; font-weight: 300; background: transparent; padding-top: 18px;"
            )
            return lbl

        lay.addWidget(_part("Навеска, г",       f"{naveski:.2f}", TEXT_MUTED))
        lay.addWidget(_op("−"))
        lay.addWidget(_part("Сумма СП, г",       f"{sp_sum:.2f}", "#f87171"))
        lay.addWidget(_op("−"))
        lay.addWidget(_part("Сумма ЗП, г",       f"{zp_sum:.2f}", "#6c5ce7"))
        lay.addWidget(_op("="))
        lay.addWidget(_part("Основное зерно, г", f"{grain:.2f}", ACCENT_G))
        lay.addStretch()
        return frame

    def _params_block(self, card: Card, active: list) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        hdr = QWidget()
        hdr.setStyleSheet(
            f"background: rgba(108,92,231,0.06); border-radius: 10px 10px 0 0;"
            f"border-bottom: 0.5px solid {BORDER};"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 9, 14, 9)
        t = QLabel("ПОКАЗАТЕЛИ")
        t.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        hl.addWidget(t)
        lay.addWidget(hdr)
        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(14, 10, 14, 12)
        grid.setSpacing(8)
        COLS = 4
        for idx, (key, label) in enumerate(active):
            val = getattr(card, key, None)
            if val is None:
                continue
            _, _, decimals = PARAM_META.get(key, ("", "", 1))
            ri, ci = divmod(idx, COLS)
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; font-weight: 500; background: transparent; border: none;"
            )
            val_lbl = QLabel(f"{val:.{decimals}f}")
            val_lbl.setStyleSheet(
                f"color: {ACCENT_G}; font-family: '{FONT_UI}', sans-serif; font-size: 14px;"
                "font-weight: 300; background: rgba(74,222,128,0.08);"
                "border: 0.5px solid rgba(74,222,128,0.3); border-radius: 6px; padding: 4px 10px;"
            )
            cl.addWidget(lbl)
            cl.addWidget(val_lbl)
            grid.addWidget(cell, ri, ci)
        lay.addWidget(grid_w)
        return frame


# ── Страница Просмотр ─────────────────────────────────────────────────────────

class CardsViewPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Просмотр карточек",
            subtitle="",
            section="Карточки",
            actions=[("Печать", True)],
        )
        self._action_buttons["Печать"].clicked.connect(self._on_print)

        # Убираем QScrollArea BasePage — заменяем на plain виджет
        root_lay = self.layout()
        scroll_item = root_lay.takeAt(root_lay.count() - 1)
        if scroll_item and scroll_item.widget():
            scroll_item.widget().deleteLater()

        self._no_scroll_widget = QWidget()
        self._no_scroll_widget.setStyleSheet(f"background: {BG};")
        self._no_scroll_layout = QVBoxLayout(self._no_scroll_widget)
        self._no_scroll_layout.setContentsMargins(22, 18, 22, 22)
        self._no_scroll_layout.setSpacing(14)
        root_lay.addWidget(self._no_scroll_widget, 1)

        self._card_items: list[CardListItem] = []
        self._selected_item: Optional[CardListItem] = None
        self._build_ui()

    # ── Построение UI ─────────────────────────────────────────────────────────

    @staticmethod
    def _cb_style() -> str:
        return f"""
            QCheckBox {{
                color: {TEXT_MUTED};
                font-family: '{FONT_UI}', sans-serif;
                font-size: 12px;
                background: transparent;
                spacing: 7px;
            }}
            QCheckBox::indicator {{
                width: 15px; height: 15px;
                border: 0.5px solid #5a5a72;
                border-radius: 4px;
                background: #111114;
            }}
            QCheckBox::indicator:hover {{ border-color: rgba(108,92,231,0.6); }}
            QCheckBox::indicator:checked {{
                background: rgba(108,92,231,0.85);
                border-color: rgba(108,92,231,0.9);
            }}
            QCheckBox::indicator:indeterminate {{
                background: rgba(108,92,231,0.4);
                border-color: rgba(108,92,231,0.6);
            }}
        """

    def _build_ui(self) -> None:
        while self._no_scroll_layout.count():
            item = self._no_scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Состояние сортировки/фильтра
        self._sort_mode = "all"   # all | date | num | name
        self._place_filter = "all"

        main_lay = QHBoxLayout()
        main_lay.setSpacing(0)
        main_lay.setContentsMargins(0, 0, 0, 0)

        # ── Левая колонка: компактный список ─────────────────────────────────
        left = QFrame()
        left.setFixedWidth(220)
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left.setStyleSheet(
            f"QFrame {{ background: {BG}; border: none; }}"
        )
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        # ── Поиск ─────────────────────────────────────────────────────────────
        search_w = QWidget()
        search_w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        search_w.setStyleSheet(
            f"background: {BG_CARD}; border-bottom: 0.5px solid {BORDER};"
        )
        sw_lay = QHBoxLayout(search_w)
        sw_lay.setContentsMargins(8, 7, 8, 7)
        sw_lay.setSpacing(0)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск...")
        self._search.setFixedHeight(26)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
            " border-radius: 6px; color: #e0e0f0;"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 0 8px; }}"
            "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
        )
        self._search.textChanged.connect(lambda _: self._apply_filters())
        sw_lay.addWidget(self._search)
        left_lay.addWidget(search_w)

        # ── Сортировка (одна строка по центру) ───────────────────────────────
        sort_w = QWidget()
        sort_w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sort_w.setStyleSheet(f"background: {BG_CARD}; border-bottom: 0.5px solid {BORDER};")
        sort_lay = QHBoxLayout(sort_w)
        sort_lay.setContentsMargins(8, 5, 8, 6)
        sort_lay.setSpacing(4)
        self._sort_buttons: dict = {}
        sort_lay.addStretch()
        for key, label in [("all", "Все"), ("date", "Дата"), ("num", "№")]:
            btn = QPushButton(label)
            btn.setFixedHeight(20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._set_sort(k))
            self._sort_buttons[key] = btn
            sort_lay.addWidget(btn)
        sort_lay.addStretch()
        self._refresh_sort_buttons()
        left_lay.addWidget(sort_w)

        # ── Скролл со списком ─────────────────────────────────────────────────
        list_scroll = QScrollArea()
        list_scroll.setWidgetResizable(True)
        list_scroll.setStyleSheet(
            scroll_style() +
            " QScrollArea { border: none; }"
        )
        self._list_inner = QWidget()
        self._list_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._list_inner.setStyleSheet(f"background: {BG};")
        self._list_lay = QVBoxLayout(self._list_inner)
        self._list_lay.setContentsMargins(6, 6, 6, 6)
        self._list_lay.setSpacing(3)
        self._list_lay.addStretch()
        list_scroll.setWidget(self._list_inner)
        left_lay.addWidget(list_scroll, 1)

        main_lay.addWidget(left)

        # ── Правая колонка: детальный просмотр ───────────────────────────────
        self._detail = CardDetailPanel()
        self._detail._on_card_saved = self._on_card_saved
        main_lay.addWidget(self._detail, 1)

        mw = RoundedClipFrame(radius=10)
        mw.set_layout(main_lay)
        self._no_scroll_layout.addWidget(mw, 1)

        self._load_cards()

    # ── Сортировка / фильтр ────────────────────────────────────────────────────
    def _set_sort(self, mode: str) -> None:
        self._sort_mode = mode
        self._refresh_sort_buttons()
        self._apply_filters()

    def _refresh_sort_buttons(self) -> None:
        for key, btn in self._sort_buttons.items():
            active = (key == self._sort_mode)
            btn.setStyleSheet(self._chip_style(active))

    def _set_place_filter(self, mode: str) -> None:
        pass  # фильтр по месту убран

    def _refresh_place_buttons(self) -> None:
        pass

    @staticmethod
    @staticmethod
    def _chip_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{"
                f" background: rgba(108,92,231,0.1);"
                f" border: 0.5px solid rgba(108,92,231,0.4);"
                f" border-radius: 4px; color: {ACCENT_ICON};"
                f" font-family: '{FONT_UI}', sans-serif;"
                f" font-size: 12px; padding: 0 7px;"
                f"}}"
            )
        return (
            f"QPushButton {{"
            f" background: transparent;"
            f" border: 0.5px solid #2a2a32;"
            f" border-radius: 4px; color: #606075;"
            f" font-family: '{FONT_UI}', sans-serif;"
            f" font-size: 12px; padding: 0 7px;"
            f"}}"
            f" QPushButton:hover {{ color: #6a6a80; border-color: #5a5a72; }}"
        )

    def _apply_filters(self) -> None:
        self._load_cards()


    # ── Загрузка карточек ─────────────────────────────────────────────────────

    # ── Фильтры (отключены) ───────────────────────────────────────────────────

    def _on_filter_changed(self) -> None:
        self._load_cards()

    def _get_date_range(self) -> tuple[str, str]:
        return "", ""

    # ── Загрузка карточек ─────────────────────────────────────────────────────

    def _load_cards(self) -> None:
        self._card_items = []
        self._selected_item = None

        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        cards = get_all_cards()

        # Фильтр по тексту
        q = (self._search.text() if hasattr(self, "_search") else "").strip().lower()
        if q:
            def _match(c):
                return (
                    q in (c.probe_number or "").lower()
                    or q in (c.culture_name or "").lower()
                )
            cards = [c for c in cards if _match(c)]

        # Фильтр по месту убран

        # Сортировка
        sm = getattr(self, "_sort_mode", "all")
        if sm == "num":
            def _num_key(c):
                try:
                    return (0, int("".join(ch for ch in (c.probe_number or "") if ch.isdigit()) or 0))
                except Exception:
                    return (1, c.probe_number or "")
            cards.sort(key=_num_key, reverse=True)
        elif sm == "name":
            cards.sort(key=lambda c: (c.culture_name or "").lower())
        elif sm == "date":
            cards.sort(key=lambda c: c.created_at or "", reverse=True)
        # sm == "all" — порядок из БД, без сортировки

        if not cards:
            ph = QLabel("Карточек не найдено")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none; padding: 20px 8px;"
            )
            self._list_lay.addWidget(ph)
        else:
            for card in cards:
                it = CardListItem(
                    card,
                    on_select=self._on_select,
                )
                self._card_items.append(it)
                self._list_lay.addWidget(it)

        self._list_lay.addStretch()

    # ── Логика чекбоксов ──────────────────────────────────────────────────────

    def _on_check_changed(self) -> None:
        """Вызывается при изменении любого чекбокса в списке."""
    # ── Выбор / удаление ─────────────────────────────────────────────────────

    def _on_select(self, card: Card) -> None:
        if self._selected_item is not None:
            self._selected_item.set_selected(False)
        for it in self._card_items:
            if it._card.id == card.id:
                it.set_selected(True)
                self._selected_item = it
                break
        self._detail.show_card(card)

    def _on_card_saved(self, card: Card) -> None:
        self._load_cards()

    def open_probe(self, card: Card) -> None:
        """Публичный метод: открыть конкретную пробу в панели деталей."""
        self._load_cards()
        self._on_select(card)

    def _on_print(self) -> None:
        """Обработчик кнопки «Печать». Функционал будет добавлен позже."""
        checked = self.get_checked_cards()
        if not checked:
            QMessageBox.warning(
                self, "Ничего не выбрано",
                "Отметьте хотя бы одну пробу в списке перед печатью.",
            )
            return
        # TODO: реализовать печать
        # checked — список Card для печати

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_cards()
