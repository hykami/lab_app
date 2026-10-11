"""
Страница «Акты» — Master/Detail с модальными окнами.
Слева список актов, справа детали выбранного.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal

from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QComboBox,
)

from ui.pages.base_page import BasePage, flash_btn
from ui.components.type_pill_switcher import TypePillSwitcher
from ui.theme import (
    BG, BG_CARD, BORDER, TEXT_MUTED, TEXT_BRIGHT,
    ACCENT_ICON, FONT_MONO, FONT_UI,
)
from ui.style_helpers import scroll_style, combo_style
from ui.components.styled_combo import StyledComboBox
from ui.components.rounded_clip import RoundedClipFrame
from logic.db_service import (
    Act, Card, get_all_acts, get_act, create_act,
    get_act_probes, get_cards_not_in_act, add_probe_to_act,
    delete_act,
    update_act_file_path, get_setting, get_all_silos,
    get_all_shifts, update_act_shift,
)
from logic.act_writer import create_act_file, append_row_to_act
from logic.file_lock import FileLockError

logger = logging.getLogger(__name__)

_ACT_TYPES = {
    "Входной":    "daily",
    "Дневная см.": "shift1",
    "Ночная см.":  "shift2",
}

_TAG_STYLE = {
    "daily":  ("rgba(108,92,231,0.1)",  "#a89cff", "rgba(108,92,231,0.3)"),
    "shift1": ("rgba(251,191,36,0.1)",  "#fbbf24", "rgba(251,191,36,0.3)"),
    "shift2": ("rgba(96,165,250,0.1)",  "#60a5fa", "rgba(96,165,250,0.3)"),
}


def _tag_style(act_type: str) -> str:
    bg, fg, bd = _TAG_STYLE.get(act_type, _TAG_STYLE["daily"])
    return (
        f"background: {bg}; color: {fg}; border: 0.5px solid {bd};"
        f" border-radius: 4px; font-family: '{FONT_UI}', sans-serif;"
        " font-size: 12px; padding: 2px 7px;"
    )


def _btn_style(primary=False) -> str:
    if primary:
        return (
            f"QPushButton {{ background: #5b4fcf; border: none; border-radius: 7px;"
            f" color: #fff; font-family: '{FONT_UI}', sans-serif; font-size: 12px;"
            f" font-weight: 500; padding: 0 16px; }}"
            "QPushButton:hover { background: #6c5ce7; }"
            "QPushButton:pressed { background: #4a3fb5; }"
            "QPushButton:disabled { background: #4a4a58; color: #707085; }"
        )
    return (
        f"QPushButton {{ background: transparent; border: 0.5px solid {BORDER};"
        f" border-radius: 7px; color: #9090a8;"
        f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 12px; }}"
        "QPushButton:hover { background: #1e1e22; color: #a0a0b0; }"
        "QPushButton:pressed { background: #252528; }"
    )


def _danger_btn_style() -> str:
    return (
        "QPushButton { background: transparent; border: 0.5px solid rgba(248,113,113,0.35);"
        " border-radius: 7px; color: #f87171;"
        f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 12px; }}"
        "QPushButton:hover { background: rgba(248,113,113,0.1); }"
    )


# ── Модальное окно ─────────────────────────────────────────────────────────────

class _Modal(QDialog):
    """Базовый тёмный модал с заголовком и подвалом."""

    def __init__(self, title: str, parent=None, width=480):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(width)

        # Основной контейнер
        self._root = QFrame(self)
        self._root.setStyleSheet(
            f"QFrame {{ background: #161618; border: 0.5px solid {BORDER};"
            " border-radius: 12px; }}"
        )
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.addWidget(self._root)

        self._main_lay = QVBoxLayout(self._root)
        self._main_lay.setContentsMargins(0, 0, 0, 0)
        self._main_lay.setSpacing(0)

        # Заголовок
        hdr = QWidget()
        hdr.setStyleSheet(f"background: transparent; border-bottom: 0.5px solid {BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 14, 16, 14)
        t = QLabel(title)
        t.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 14px; font-weight: 500; background: transparent; border: none;"
        )
        hl.addWidget(t, 1)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #707085; font-size: 14px; }"
            "QPushButton:hover { color: #e0e0f0; }"
        )
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)
        self._main_lay.addWidget(hdr)

        # Тело (добавляется потомком)
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(16, 14, 16, 14)
        self._body_lay.setSpacing(12)
        self._main_lay.addWidget(self._body)

        # Подвал
        foot = QWidget()
        foot.setStyleSheet(f"background: transparent; border-top: 0.5px solid {BORDER};")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(8)
        fl.addStretch()
        self._cancel_btn = QPushButton("Отмена")
        self._cancel_btn.setFixedHeight(32)
        self._cancel_btn.setStyleSheet(_btn_style(False))
        self._cancel_btn.clicked.connect(self.reject)
        fl.addWidget(self._cancel_btn)
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setFixedHeight(32)
        self._ok_btn.setStyleSheet(_btn_style(True))
        fl.addWidget(self._ok_btn)
        self._main_lay.addWidget(foot)

    def _add_body_widget(self, w: QWidget):
        self._body_lay.addWidget(w)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            pr = self.parent().rect()
            pos = self.parent().mapToGlobal(pr.center())
            self.move(pos.x() - self.width() // 2, pos.y() - self.height() // 2)


class _ProbeListWidget(QWidget):
    """Список проб с чекбоксами и поиском."""

    def __init__(self, cards: list[Card], parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Поиск
        search = QLineEdit()
        search.setPlaceholderText("Поиск проб...")
        search.setFixedHeight(30)
        search.setStyleSheet(
            f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
            " border-radius: 6px; color: #e0e0f0;"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 8px; }}"
            "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
        )
        lay.addWidget(search)

        # Шапка с «Все» / «Сбросить»
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        cnt_lbl = QLabel("Выбрано: 0")
        cnt_lbl.setStyleSheet(
            f"color: #707085; font-family: '{FONT_MONO}', monospace; font-size: 12px; background: transparent;"
        )
        hdr.addWidget(cnt_lbl, 1)
        sel_all = QPushButton("Все")
        sel_all.setFixedHeight(22)
        sel_none = QPushButton("Сбросить")
        sel_none.setFixedHeight(22)
        for b in (sel_all, sel_none):
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 0.5px solid {BORDER};"
                " border-radius: 4px; color: #707085;"
                f" font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 0 8px; }}"
                "QPushButton:hover { color: #8080a0; border-color: #5a5a72; }"
            )
        hdr.addWidget(sel_all)
        hdr.addWidget(sel_none)
        lay.addLayout(hdr)

        # Список
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(180)
        scroll.setStyleSheet(scroll_style())
        inner = QWidget()
        inner.setStyleSheet(
            f"background: #111114; border: 0.5px solid {BORDER}; border-radius: 8px;"
        )
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(0)
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        self._rows: list[tuple[QWidget, QCheckBox, Card]] = []
        self._cnt_lbl = cnt_lbl

        for i, card in enumerate(cards):
            row = QWidget()
            row.setStyleSheet(
                f"background: transparent; border-bottom: 0.5px solid {BORDER};"
                if i < len(cards) - 1 else "background: transparent;"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 7, 10, 7)
            rl.setSpacing(8)
            cb = QCheckBox()
            cb.setStyleSheet("""
                QCheckBox { background: transparent; border: none; }
                QCheckBox::indicator { width:14px; height:14px;
                    border: 0.5px solid #5a5a72; border-radius: 4px; background: #111114; }
                QCheckBox::indicator:checked {
                    background: rgba(108,92,231,0.85); border-color: rgba(108,92,231,0.9); }
                QCheckBox:focus { outline: none; border: none; background: transparent; }
            """)
            cb.stateChanged.connect(self._update_count)
            rl.addWidget(cb)
            num = QLabel(f"#{card.probe_number}")
            num.setStyleSheet(
                f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; background: transparent; border: none;"
            )
            num.setFixedWidth(60)
            rl.addWidget(num)
            cult = QLabel(card.culture_name)
            cult.setStyleSheet(
                f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 12px; background: transparent; border: none;"
            )
            rl.addWidget(cult, 1)
            inner_lay.addWidget(row)
            self._rows.append((row, cb, card))

        if not cards:
            ph = QLabel("Нет доступных проб")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 12px; background: transparent; padding: 16px;"
            )
            inner_lay.addWidget(ph)

        inner_lay.addStretch()

        sel_all.clicked.connect(lambda: self._set_all(True))
        sel_none.clicked.connect(lambda: self._set_all(False))
        search.textChanged.connect(self._on_search)

    def _update_count(self):
        n = sum(1 for _, cb, _ in self._rows if cb.isChecked())
        self._cnt_lbl.setText(f"Выбрано: {n}")

    def _set_all(self, checked: bool):
        for row, cb, _ in self._rows:
            if row.isVisible():
                cb.setChecked(checked)

    def _on_search(self, text: str):
        t = text.strip().lower()
        for row, cb, card in self._rows:
            visible = (not t or t in str(card.probe_number).lower()
                       or t in card.culture_name.lower())
            row.setVisible(visible)

    def selected_cards(self) -> list[Card]:
        return [card for _, cb, card in self._rows if cb.isChecked()]


class _CreateActModal(_Modal):
    """Модал создания нового акта."""

    def __init__(self, act_type: str, parent=None):
        super().__init__("Создать акт", parent, width=460)
        self._act_type = act_type
        self._ok_btn.setText("Создать акт")

        shifts = get_all_shifts()

        def _make_combo(label: str) -> tuple[QWidget, QComboBox]:
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            wl = QVBoxLayout(w)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: #8a8a9a; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; background: transparent; border: none;"
            )
            wl.addWidget(lbl)
            combo = StyledComboBox(font_size=12)
            combo.setFixedHeight(32)
            combo.setStyleSheet(combo_style(font_size=12))
            if not shifts:
                combo.addItem("Нет смен", None)
                combo.setEnabled(False)
            else:
                for s in shifts:
                    combo.addItem(s.name if s.name else f"Смена {s.number}", s.id)
            wl.addWidget(combo)
            return w, combo

        is_daily = act_type == "daily"
        grid = QHBoxLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        label1 = "Смена 1" if is_daily else "Смена"
        w1, self._combo1 = _make_combo(label1)
        grid.addWidget(w1)

        self._combo2 = None
        if is_daily:
            w2, self._combo2 = _make_combo("Смена 2")
            if shifts and len(shifts) > 1:
                self._combo2.setCurrentIndex(1)
            grid.addWidget(w2)

        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid_w.setLayout(grid)
        self._add_body_widget(grid_w)

        self._ok_btn.clicked.connect(self.accept)

    def shift_ids(self) -> tuple[Optional[int], Optional[int]]:
        id1 = self._combo1.currentData()
        id2 = self._combo2.currentData() if self._combo2 else None
        return id1, id2


class _AddProbesModal(_Modal):
    """Модал добавления проб в существующий акт."""

    def __init__(self, act: Act, cards: list[Card], parent=None):
        super().__init__(f"Добавить пробы — Акт №{act.number_str}", parent, width=460)
        self._ok_btn.setText("Добавить")
        self._probe_list = _ProbeListWidget(cards)
        self._add_body_widget(self._probe_list)
        self._ok_btn.clicked.connect(self.accept)
        self._ok_btn.setEnabled(bool(cards))

    def selected_cards(self) -> list[Card]:
        return self._probe_list.selected_cards()


# ── Строка в списке актов ──────────────────────────────────────────────────────

class _ActListItem(QWidget):
    def __init__(self, act: Act, probe_count: int, on_select, parent=None):
        super().__init__(parent)
        self._act = act
        self._on_select = on_select
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(10, 9, 10, 9)
        self._lay.setSpacing(3)
        self._apply_style()

        # Строка 1: номер + тег + дата
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(6)
        num = QLabel(f"#{act.number_str}")
        num.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 12px; font-weight: 500; background: transparent; border: none;"
        )
        row1.addWidget(num)
        tag = QLabel(act.type_label)
        tag.setStyleSheet(_tag_style(act.act_type))
        row1.addWidget(tag)
        row1.addStretch()
        date = QLabel(act.created_at[:10])
        date.setStyleSheet(
            f"color: #606075; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 12px; background: transparent; border: none;"
        )
        row1.addWidget(date)
        self._lay.addLayout(row1)

        # Строка 2: кол-во проб
        if probe_count > 0:
            suffix = "а" if probe_count == 1 else "ы" if probe_count in (2, 3, 4) else ""
            sub = QLabel(f"{probe_count} проб{suffix}")
            sub.setStyleSheet(
                f"color: #606075; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; background: transparent; border: none;"
            )
            self._lay.addWidget(sub)
        else:
            sub = QLabel("Нет проб")
            sub.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; background: transparent; border: none;"
            )
            self._lay.addWidget(sub)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._on_select(self._act)
        super().mousePressEvent(e)

    def set_selected(self, v: bool):
        self._selected = v
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                "background: rgba(108,92,231,0.1);"
                " border: 0.5px solid rgba(108,92,231,0.3);"
                " border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                f"background: transparent; border: 0.5px solid transparent; border-radius: 8px;"
            )


# ── Виджет пробы в детальной панели ───────────────────────────────────────────

class _ProbeChip(QWidget):
    def __init__(self, card: Card, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(6)
        self.setStyleSheet(
            f"background: #111114; border: 0.5px solid {BORDER};"
            " border-radius: 6px;"
        )
        num = QLabel(f"#{card.probe_number}")
        num.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 11px; background: transparent; border: none;"
        )
        lay.addWidget(num)
        cult = QLabel(card.culture_name)
        cult.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 11px; background: transparent; border: none;"
        )
        lay.addWidget(cult)


# ── Главная страница ───────────────────────────────────────────────────────────

class ActsPage(BasePage):
    open_probe_requested = pyqtSignal(object)  # Card

    def __init__(self, parent=None):
        super().__init__(title="Акты", subtitle="", section="Акты", actions=[])
        self._selected_act: Optional[Act] = None
        self._list_items: list[_ActListItem] = []

        self._tab_switcher = TypePillSwitcher(list(_ACT_TYPES.keys()))
        self._tab_switcher.connect_changed(self._on_tab_changed)
        self.set_header_widget(self._tab_switcher)

        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        main = QHBoxLayout()
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # ── Левая колонка: список актов ────────────────────────────────────────
        left = QWidget()
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left.setFixedWidth(240)
        left.setStyleSheet(f"background: {BG};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        # Шапка со списком и кнопкой создания
        list_hdr = QWidget()
        list_hdr.setFixedHeight(54)
        list_hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        list_hdr.setStyleSheet(
            f"background: {BG_CARD}; border-bottom: 0.5px solid {BORDER};"
        )
        lhl = QHBoxLayout(list_hdr)
        lhl.setContentsMargins(16, 12, 16, 12)
        lhl.setSpacing(8)
        lbl = QLabel("Акты")
        lbl.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 13px; font-weight: 500; background: transparent; border: none;"
        )
        lhl.addWidget(lbl, 1)
        self._create_btn = QPushButton("+ Новый")
        self._create_btn.setFixedHeight(30)
        self._create_btn.setStyleSheet(_btn_style(True))
        self._create_btn.clicked.connect(self._on_create_act)
        lhl.addWidget(self._create_btn)
        ll.addWidget(list_hdr)

        # Поиск
        search_w = QWidget()
        search_w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        search_w.setStyleSheet(
            f"background: {BG}; border-bottom: 0.5px solid {BORDER}; padding: 6px 8px;"
        )
        sl = QHBoxLayout(search_w)
        sl.setContentsMargins(8, 6, 8, 6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск...")
        self._search.setFixedHeight(28)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
            " border-radius: 6px; color: #e0e0f0;"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 8px; }}"
            "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
        )
        self._search.textChanged.connect(self._on_search)
        sl.addWidget(self._search)
        ll.addWidget(search_w)

        # Скролл со списком актов
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
        self._list_lay.setSpacing(2)
        self._list_lay.addStretch()
        list_scroll.setWidget(self._list_inner)
        ll.addWidget(list_scroll, 1)
        main.addWidget(left)

        # Разделитель
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {BORDER};")
        main.addWidget(sep)

        # ── Правая панель: детали акта ─────────────────────────────────────────
        self._detail = QWidget()
        self._detail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._detail.setStyleSheet(f"background: {BG};")
        dl = QVBoxLayout(self._detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(0)

        # Шапка деталей
        self._detail_hdr = QWidget()
        self._detail_hdr.setFixedHeight(54)
        self._detail_hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._detail_hdr.setStyleSheet(
            f"background: {BG_CARD}; border-bottom: 0.5px solid {BORDER};"
        )
        dhl = QHBoxLayout(self._detail_hdr)
        dhl.setContentsMargins(16, 12, 16, 12)
        dhl.setSpacing(8)
        self._detail_title = QLabel("Выберите акт")
        self._detail_title.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 14px; font-weight: 500; background: transparent; border: none;"
        )
        dhl.addWidget(self._detail_title, 1)
        self._add_probes_btn = QPushButton("+ Добавить пробы")
        self._add_probes_btn.setFixedHeight(30)
        self._add_probes_btn.setStyleSheet(_btn_style(True))
        self._add_probes_btn.setVisible(False)
        self._add_probes_btn.clicked.connect(self._on_add_probes_modal)
        dhl.addWidget(self._add_probes_btn)
        self._delete_btn = QPushButton("Удалить")
        self._delete_btn.setFixedHeight(30)
        self._delete_btn.setStyleSheet(_danger_btn_style())
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._on_delete_act)
        dhl.addWidget(self._delete_btn)
        dl.addWidget(self._detail_hdr)

        # Контент деталей (скролл)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setStyleSheet(
            scroll_style() +
            " QScrollArea { border: none; }"
        )
        self._detail_body = QWidget()
        self._detail_body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._detail_body.setStyleSheet(f"background: {BG}; border: none;")
        self._detail_body_lay = QVBoxLayout(self._detail_body)
        self._detail_body_lay.setContentsMargins(16, 16, 16, 16)
        self._detail_body_lay.setSpacing(16)

        # Placeholder
        self._placeholder = QLabel("Выберите акт из списка слева")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 14px; background: transparent;"
        )
        self._detail_body_lay.addWidget(self._placeholder)
        self._detail_body_lay.addStretch()

        detail_scroll.setWidget(self._detail_body)
        dl.addWidget(detail_scroll, 1)
        main.addWidget(self._detail, 1)

        mw = RoundedClipFrame(radius=10)
        mw.set_layout(main)
        self._content_layout.addWidget(mw, 1)
        self._load_acts()

    # ── Список ────────────────────────────────────────────────────────────────

    def _load_acts(self):
        self._list_items.clear()
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        acts = get_all_acts()
        if not acts:
            ph = QLabel("Актов пока нет")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 12px; background: transparent; padding: 20px;"
            )
            self._list_lay.addWidget(ph)
        else:
            for act in acts:
                probes = get_act_probes(act.id)
                item = _ActListItem(act, len(probes), self._select_act)
                if self._selected_act and act.id == self._selected_act.id:
                    item.set_selected(True)
                self._list_items.append(item)
                self._list_lay.addWidget(item)

        self._list_lay.addStretch()
        self._on_search(self._search.text() if hasattr(self, '_search') else "")

    def _on_search(self, text: str):
        t = text.strip().lower()
        for item in self._list_items:
            visible = (
                not t
                or t in str(item._act.number_str).lower()
                or t in item._act.type_label.lower()
                or t in item._act.created_at[:10]
            )
            item.setVisible(visible)

    def _on_tab_changed(self, _idx: int, _text: str):
        pass  # фильтрация при необходимости

    # ── Детали акта ───────────────────────────────────────────────────────────

    def _select_act(self, act: Act):
        self._selected_act = act
        for item in self._list_items:
            item.set_selected(item._act.id == act.id)
        self._render_detail(act)

    def _on_delete_act(self) -> None:
        if not self._selected_act:
            return
        act = self._selected_act
        msg = QMessageBox(self)
        msg.setWindowTitle("Удаление акта")
        msg.setText(
            f"Удалить акт №{act.number_str} ({act.type_label}, {act.created_at[:10]})?\n\n"
            "Это действие необратимо — акт будет удалён без возможности восстановления."
        )
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("Удалить")
        msg.button(QMessageBox.StandardButton.No).setText("Отмена")
        msg.setStyleSheet("""
            QMessageBox { background: #18181c; color: #c0c0c8; }
            QLabel { color: #c0c0c8; font-size: 13px; }
            QPushButton {
                background: #18181c; border: 0.5px solid #4a4a58;
                border-radius: 7px; color: #c0c0c8;
                padding: 6px 18px; min-width: 80px;
            }
            QPushButton:hover { border-color: #5a5a72; color: #e0e0e8; }
        """)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        delete_act(act.id)
        self._selected_act = None
        # Сбрасываем правую панель
        self._detail_title.setText("Выберите акт")
        self._add_probes_btn.setVisible(False)
        self._delete_btn.setVisible(False)
        while self._detail_body_lay.count():
            item = self._detail_body_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._load_acts()

    def _render_detail(self, act: Act):
        # Заголовок
        self._detail_title.setText(f"Акт №{act.number_str}  ·  {act.type_label}  ·  {act.created_at[:10]}")
        self._add_probes_btn.setVisible(True)
        self._delete_btn.setVisible(True)

        # Очищаем тело
        while self._detail_body_lay.count():
            item = self._detail_body_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        probes = get_act_probes(act.id)

        # Пробы
        probes_hdr = QLabel("ПРОБЫ В АКТЕ")
        probes_hdr.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        self._detail_body_lay.addWidget(probes_hdr)

        if probes:
            probes_wrap = QWidget()
            probes_wrap.setStyleSheet(
                f"background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px;"
            )
            pw_lay = QVBoxLayout(probes_wrap)
            pw_lay.setContentsMargins(0, 0, 0, 0)
            pw_lay.setSpacing(0)
            for i, card in enumerate(probes):
                row = QWidget()
                row.setCursor(Qt.CursorShape.PointingHandCursor)
                row.setStyleSheet(
                    f"background: transparent;"
                    + (f" border-bottom: 0.5px solid {BORDER};" if i < len(probes) - 1 else "")
                )
                row.setToolTip("Открыть пробу в Просмотре")

                def _make_click_handler(c):
                    def _on_click(event):
                        self.open_probe_requested.emit(c)
                    return _on_click

                row.mousePressEvent = _make_click_handler(card)

                rl = QHBoxLayout(row)
                rl.setContentsMargins(14, 8, 14, 8)
                rl.setSpacing(10)
                num = QLabel(f"#{card.probe_number}")
                num.setStyleSheet(
                    f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
                    " font-size: 12px; background: transparent; border: none;"
                )
                num.setFixedWidth(70)
                rl.addWidget(num)
                cult = QLabel(card.culture_name)
                cult.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
                    " font-size: 12px; background: transparent; border: none;"
                )
                rl.addWidget(cult, 1)
                pw_lay.addWidget(row)
            self._detail_body_lay.addWidget(probes_wrap)
        else:
            ph = QLabel("Проб пока нет — добавьте через «+ Добавить пробы»")
            ph.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 12px; background: transparent; border: none;"
            )
            self._detail_body_lay.addWidget(ph)

        self._detail_body_lay.addStretch()

    # ── Создание акта ─────────────────────────────────────────────────────────

    def _on_create_act(self):
        acts_dir = get_setting("acts_dir")
        if not acts_dir:
            QMessageBox.warning(self, "Ошибка",
                "Путь к папке актов не указан.\nЗадайте его в Настройки → Основные.")
            return

        type_label = self._tab_switcher.current_text
        act_type = _ACT_TYPES[type_label]

        dlg = _CreateActModal(act_type, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        shift_id, shift_id2 = dlg.shift_ids()

        if act_type in ("shift1", "shift2") and shift_id is None:
            QMessageBox.warning(self, "Не выбрана смена",
                "Для среднесуточного акта необходимо выбрать смену.")
            return
        if act_type == "daily" and (shift_id is None or shift_id2 is None):
            QMessageBox.warning(self, "Не выбраны смены",
                "Для входного акта необходимо выбрать обе смены.")
            return
        if act_type == "daily" and shift_id == shift_id2:
            QMessageBox.warning(self, "Одинаковые смены",
                "Смены 1 и 2 не должны совпадать.")
            return

        try:
            act = create_act(act_type, "", acts_dir,
                             shift_id=shift_id, shift_id2=shift_id2)
            file_path = create_act_file(act, acts_dir)
            update_act_file_path(act.id, file_path)
        except Exception as e:
            logger.exception("Ошибка создания акта")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать акт:\n{e}")
            return

        self._load_acts()
        self._select_act(get_act(act.id))

    # ── Добавление проб ───────────────────────────────────────────────────────

    def _on_add_probes_modal(self):
        if not self._selected_act:
            return
        act = self._selected_act
        if not act.file_path or not os.path.exists(act.file_path):
            QMessageBox.warning(self, "Файл не найден",
                f"Файл акта не найден:\n{act.file_path or '(не задан)'}")
            return

        available = get_cards_not_in_act(act.id, act.act_type)
        dlg = _AddProbesModal(act, available, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dlg.selected_cards()
        if not selected:
            QMessageBox.information(self, "Ничего не выбрано",
                "Выберите хотя бы одну пробу.")
            return

        silos = {s.id: s for s in get_all_silos()}
        errors = []
        for card in selected:
            try:
                row_num = add_probe_to_act(act.id, card.id)
                silo = silos.get(card.silo_id) if getattr(card, "silo_id", None) else None
                append_row_to_act(act.file_path, card, row_num, silo, act.act_type)
            except FileLockError as e:
                QMessageBox.warning(self, "Файл недоступен", str(e))
                break
            except Exception as e:
                logger.exception("Ошибка добавления пробы #%s", card.probe_number)
                errors.append(f"#{card.probe_number}: {e}")

        if errors:
            QMessageBox.warning(self, "Частичная ошибка",
                "Некоторые пробы не удалось добавить:\n\n" + "\n".join(errors))

        self._load_acts()
        if self._selected_act:
            self._select_act(get_act(self._selected_act.id))

    # ── Events ────────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._load_acts()
        if self._selected_act:
            self._selected_act = get_act(self._selected_act.id)
            if self._selected_act:
                self._render_detail(self._selected_act)
