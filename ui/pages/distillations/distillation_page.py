"""
Перегонки — Master/Detail layout.
Слева: список карточек с поиском и чекбоксами.
Справа: сводка + поля ввода + экспорт с прогресс-баром.
"""

from __future__ import annotations
import os
from typing import Optional, Callable

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.components.type_pill_switcher import TypePillSwitcher
from ui.animations import stagger_fade_in, fade_in_progress, fade_out_progress
from ui.style_helpers import scroll_style, label_field_style, combo_style, input_style
from ui.components.styled_combo import StyledComboBox
from ui.components.rounded_clip import RoundedClipFrame
from ui.theme import (
    BG, BG_CARD, BORDER,
    TEXT_MAIN, TEXT_MUTED, TEXT_BRIGHT, ACCENT_G,
    ACCENT_ICON, FONT_MONO, FONT_UI,
)
from logic.db_service import Card, get_all_cards, get_all_silos
from logic.excel_writer import ExportRow, export_to_mkmts, export_to_app
from config import config


_TABS = [
    {"label": "Мукомолка",   "sheet": "МКМЦ",             "places": frozenset({"Мукомолка"}),           "fn": export_to_mkmts},
    {"label": "КРС / Свинки","sheet": "Производства АПП", "places": frozenset({"КРС","Свинки","Рыбы"}), "fn": export_to_app},
]

_PLACE_COLORS = {
    "Мукомолка": ("rgba(251,191,36,0.07)",  "#fbbf24", "rgba(251,191,36,0.18)"),
    "КРС":       ("rgba(96,165,250,0.07)",  "#60a5fa", "rgba(96,165,250,0.18)"),
    "Свинки":    ("rgba(168,139,255,0.08)", "#a89cff", "rgba(108,92,231,0.22)"),
    "Рыбы":      ("rgba(74,222,128,0.06)",  "#4ade80", "rgba(74,222,128,0.18)"),
}


def _sec_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
        " font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
    )
    return lbl


def _divider() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {BORDER}; border: none;")
    return w


class _ExportThread(QThread):
    progress   = pyqtSignal(int, int)
    finished   = pyqtSignal(int)
    error      = pyqtSignal(str)
    lock_error = pyqtSignal(str)

    def __init__(self, fn: Callable, path: str, rows: list) -> None:
        super().__init__()
        self._fn = fn; self._path = path; self._rows = rows

    def run(self) -> None:
        from logic.file_lock import FileLockError
        try:
            count = self._fn(
                self._path, self._rows,
                progress_cb=lambda s, t: self.progress.emit(s, t),
            )
            self.finished.emit(count)
        except FileLockError as e:
            self.lock_error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))


class _CardItem(QWidget):
    def __init__(self, card: Card, on_change: Callable, silo_label: str = "", parent=None) -> None:
        super().__init__(parent)
        self.card = card
        self.setStyleSheet("background: transparent;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(8)

        self._cb = QCheckBox()
        self._cb.setStyleSheet("""
            QCheckBox { background: transparent; border: none; }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border-radius: 4px; border: 0.5px solid #5a5a72; background: #111114;
            }
            QCheckBox::indicator:checked {
                background: rgba(108,92,231,0.85); border-color: rgba(108,92,231,0.9);
            }
        """)
        self._cb.stateChanged.connect(on_change)
        lay.addWidget(self._cb)

        num = QLabel(f"#{card.probe_number}")
        num.setFixedWidth(72)
        num.setStyleSheet(
            f"color: {ACCENT_ICON}; background: rgba(108,92,231,0.1);"
            f" border: 0.5px solid rgba(108,92,231,0.25); border-radius: 5px;"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 2px 7px;"
        )
        lay.addWidget(num)

        cult = QLabel(card.culture_name)
        cult.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 12px; background: transparent; border: none;"
        )
        lay.addWidget(cult, 1)

        # Силос
        if silo_label:
            silo_lbl = QLabel(f"Силос {silo_label}")
            silo_lbl.setStyleSheet(
                f"background: rgba(74,222,128,0.06); color: #4ade80;"
                f" border: 0.5px solid rgba(74,222,128,0.2);"
                f" border-radius: 3px; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; padding: 2px 6px;"
            )
            lay.addWidget(silo_lbl)

        place = getattr(card, "distillation_place", "") or ""
        if place:
            bg, fg, bd = _PLACE_COLORS.get(place, ("transparent", TEXT_MUTED, BORDER))
            pl = QLabel(place)
            pl.setStyleSheet(
                f"background: {bg}; color: {fg}; border: 0.5px solid {bd};"
                f" border-radius: 3px; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; padding: 2px 7px;"
            )
            lay.addWidget(pl)

        self.mousePressEvent = lambda e: self._cb.setChecked(not self._cb.isChecked())

    @property
    def is_checked(self) -> bool:
        return self._cb.isChecked()


class DistillationPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(title="Перегонки", subtitle="", section="Перегонки", actions=[])
        self._active_tab    = 0
        self._card_items:   list[_CardItem] = []
        self._all_silos     = []
        self._export_thread = None

        self._tab_switcher = TypePillSwitcher([cfg["label"] for cfg in _TABS])
        self._tab_switcher.connect_changed(lambda idx, _: self._switch_tab(idx))
        self.set_header_widget(self._tab_switcher)

        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._all_silos = get_all_silos()

        main = QHBoxLayout()
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # ── Левая часть: список карточек ───────────────────────────────────────
        left = QWidget()
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left.setStyleSheet(f"background: {BG};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        # Тулбар: поиск + Все/Сбросить
        toolbar = QWidget()
        toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        toolbar.setStyleSheet(
            f"background: {BG_CARD}; border-bottom: 0.5px solid {BORDER};"
        )
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(8, 7, 8, 7)
        tl.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск по номеру, культуре...")
        self._search.setFixedHeight(28)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
            " border-radius: 6px; color: #e0e0f0;"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 8px; }}"
            "QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
        )
        self._search.textChanged.connect(self._on_search)
        tl.addWidget(self._search, 1)

        for label, fn in [("Все", lambda: self._select_all(True)),
                          ("Сбросить", lambda: self._select_all(False))]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 0.5px solid {BORDER};"
                f" border-radius: 5px; color: #707085;"
                f" font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 0 9px; }}"
                "QPushButton:hover { color: #8080a0; border-color: #5a5a72; }"
            )
            btn.clicked.connect(fn)
            tl.addWidget(btn)

        ll.addWidget(toolbar)

        # Заголовок колонок
        col_hdr = QWidget()
        col_hdr.setStyleSheet(f"background: {BG_CARD}; border-bottom: 0.5px solid {BORDER};")
        chl = QHBoxLayout(col_hdr)
        chl.setContentsMargins(10, 5, 10, 5)
        chl.setSpacing(8)
        for txt, fixed_w in [("", 22), ("ПРОБА", 72), ("КУЛЬТУРА", 0), ("МЕСТО", 60)]:
            lb = QLabel(txt)
            lb.setStyleSheet(
                f"color: #606075; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; background: transparent; border: none;"
            )
            if fixed_w:
                lb.setFixedWidth(fixed_w)
                chl.addWidget(lb)
            else:
                chl.addWidget(lb, 1)
        ll.addWidget(col_hdr)

        # Список
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            scroll_style() +
            " QScrollArea { border: none; }"
        )
        self._list_inner = QWidget()
        self._list_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._list_inner.setStyleSheet(f"background: {BG};")
        self._list_lay = QVBoxLayout(self._list_inner)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(0)
        self._list_lay.addStretch()
        scroll.setWidget(self._list_inner)
        ll.addWidget(scroll, 1)

        # Итоговая строка снизу
        summary_bar = QWidget()
        summary_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        summary_bar.setStyleSheet(
            f"background: {BG_CARD}; border-top: 0.5px solid {BORDER};"
        )
        sbl = QHBoxLayout(summary_bar)
        sbl.setContentsMargins(0, 0, 0, 0)
        sbl.setSpacing(0)

        def _sum_cell(key: str, last=False) -> QLabel:
            cell = QWidget()
            cell.setStyleSheet(
                "background: transparent;"
                + ("" if last else f" border-right: 0.5px solid {BORDER};")
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(12, 7, 12, 7)
            cl.setSpacing(2)
            k = QLabel(key)
            k.setStyleSheet(
                f"color: #525265; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 11px; background: transparent; border: none;"
            )
            v = QLabel("—")
            v.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 13px; background: transparent; border: none;"
            )
            cl.addWidget(k)
            cl.addWidget(v)
            sbl.addWidget(cell)
            return v

        self._sum_count  = _sum_cell("ВЫБРАНО")
        self._sum_weight = _sum_cell("ВЕС, КГ")
        self._sum_sheet  = _sum_cell("ЛИСТ", last=True)
        sbl.addStretch()
        ll.addWidget(summary_bar)

        main.addWidget(left, 1)

        # Разделитель
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {BORDER};")
        main.addWidget(sep)

        # ── Правая панель ──────────────────────────────────────────────────────
        right = QWidget()
        right.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        right.setFixedWidth(256)
        right.setStyleSheet(f"background: {BG_CARD};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14, 16, 14, 14)
        rl.setSpacing(0)

        # Сводка
        rl.addWidget(_sec_label("СВОДКА"))
        rl.addSpacing(8)

        summary_card = QFrame()
        summary_card.setStyleSheet(
            f"QFrame {{ background: {BG}; border: 0.5px solid {BORDER}; border-radius: 8px; }}"
        )
        scl = QVBoxLayout(summary_card)
        scl.setContentsMargins(0, 0, 0, 0)
        scl.setSpacing(0)

        def _stat_row(label: str, last=False) -> QLabel:
            row = QWidget()
            row.setStyleSheet(
                "background: transparent;"
                + ("" if last else f" border-bottom: 0.5px solid {BORDER};")
            )
            rl2 = QHBoxLayout(row)
            rl2.setContentsMargins(12, 8, 12, 8)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 12px; background: transparent; border: none;"
            )
            val = QLabel("—")
            val.setStyleSheet(
                f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 13px; font-weight: 500; background: transparent; border: none;"
            )
            rl2.addWidget(lbl, 1)
            rl2.addWidget(val)
            scl.addWidget(row)
            return val

        self._stat_count  = _stat_row("Карточек")
        self._stat_weight = _stat_row("Вес, кг")
        self._stat_sp     = _stat_row("СП среднее")
        self._stat_zp     = _stat_row("ЗП среднее", last=True)

        rl.addWidget(summary_card)
        rl.addSpacing(16)

        # Разделитель
        rl.addWidget(_divider())
        rl.addSpacing(14)

        # Поля ввода
        rl.addWidget(_sec_label("ПАРАМЕТРЫ"))
        rl.addSpacing(10)

        def _field_w(label: str, placeholder: str, required=False) -> tuple[QWidget, QLineEdit]:
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            wl = QVBoxLayout(w)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(4)
            lrow = QWidget()
            lrow.setStyleSheet("background: transparent;")
            lr = QHBoxLayout(lrow)
            lr.setContentsMargins(0, 0, 0, 0)
            lr.setSpacing(3)
            l = QLabel(label)
            l.setStyleSheet(label_field_style())
            lr.addWidget(l)
            if required:
                s = QLabel("*")
                s.setStyleSheet("color: #f87171; font-size: 12px; background: transparent; border: none;")
                lr.addWidget(s)
            lr.addStretch()
            wl.addWidget(lrow)
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setFixedHeight(30)
            inp.setStyleSheet(input_style())
            inp.textChanged.connect(self._update_state)
            wl.addWidget(inp)
            return w, inp

        fw, self._weight_inp = _field_w("Вес, кг", "например 6700")
        rl.addWidget(fw)
        rl.addSpacing(8)
        ft, self._tank_inp = _field_w("Номер ёмкости", "например 4", required=True)
        rl.addWidget(ft)
        rl.addSpacing(8)

        # Исполнитель
        exec_w = QWidget()
        exec_w.setStyleSheet("background: transparent;")
        el = QVBoxLayout(exec_w)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(4)
        elrow = QWidget()
        elrow.setStyleSheet("background: transparent;")
        ell = QHBoxLayout(elrow)
        ell.setContentsMargins(0, 0, 0, 0)
        ell.setSpacing(3)
        elbl = QLabel("Исполнитель")
        elbl.setStyleSheet(label_field_style())
        ell.addWidget(elbl)
        estar = QLabel("*")
        estar.setStyleSheet("color: #f87171; font-size: 12px; background: transparent; border: none;")
        ell.addWidget(estar)
        ell.addStretch()
        el.addWidget(elrow)
        self._exec_combo = StyledComboBox(font_size=12)
        self._exec_combo.setFixedHeight(30)
        self._exec_combo.setEditable(True)
        self._exec_combo.lineEdit().setPlaceholderText("Фамилия И.О.")
        self._exec_combo.setStyleSheet(combo_style(font_size=12))
        self._exec_combo.lineEdit().setStyleSheet(
            f"background: transparent; border: none; color: {TEXT_MAIN};"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 4px;"
        )
        self._exec_combo.currentTextChanged.connect(self._update_state)
        el.addWidget(self._exec_combo)
        rl.addWidget(exec_w)

        rl.addStretch()

        # Разделитель перед экспортом
        rl.addWidget(_divider())
        rl.addSpacing(12)

        # Секция экспорта
        rl.addWidget(_sec_label("ЭКСПОРТ"))
        rl.addSpacing(8)

        self._target_lbl = QLabel("Выберите карточки")
        self._target_lbl.setStyleSheet(
            f"color: #525265; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 11px; background: transparent; border: none;"
        )
        rl.addWidget(self._target_lbl)
        rl.addSpacing(8)

        self._export_btn = QPushButton("Экспорт в Excel")
        self._export_btn.setFixedHeight(34)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setEnabled(False)
        self._export_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(74,222,128,0.1);
                border: 0.5px solid rgba(74,222,128,0.35);
                border-radius: 7px; color: #4ade80;
                font-family: '{FONT_UI}', sans-serif; font-size: 12px; font-weight: 500;
            }}
            QPushButton:hover {{ background: rgba(74,222,128,0.18); }}
            QPushButton:disabled {{
                background: transparent; border-color: {BORDER}; color: #4a4a58;
            }}
        """)
        self._export_btn.clicked.connect(self._on_export)
        rl.addWidget(self._export_btn)
        rl.addSpacing(6)

        # Прогресс-бар прямо под кнопкой
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {BORDER}; border: none; border-radius: 1px; }}"
            f"QProgressBar::chunk {{ background: {ACCENT_G}; border-radius: 1px; }}"
        )
        self._progress_bar.setContentsMargins(0, 0, 0, 0)
        self._progress_bar.setVisible(False)
        rl.addWidget(self._progress_bar)

        # Статус экспорта
        self._prog_lbl = QLabel("")
        self._prog_lbl.setStyleSheet(
            f"color: #4ade80; font-family: '{FONT_UI}', sans-serif;"
            " font-size: 12px; background: transparent; border: none;"
        )
        rl.addWidget(self._prog_lbl)

        main.addWidget(right)

        mw = RoundedClipFrame(radius=10)
        mw.set_layout(main)
        self._content_layout.addWidget(mw, 1)
        self._load_cards()

    # ── Переключение таба ──────────────────────────────────────────────────────

    def _switch_tab(self, idx: int) -> None:
        self._active_tab = idx
        self._load_cards()

    # ── Загрузка карточек ─────────────────────────────────────────────────────

    def _load_cards(self) -> None:
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._card_items.clear()

        places = _TABS[self._active_tab]["places"]
        cards = [
            c for c in get_all_cards()
            if getattr(c, "card_type", "") == "Перегонка"
            and getattr(c, "distillation_place", "") in places
        ]

        if not cards:
            ph = QLabel("Нет карточек для этой вкладки")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 13px; background: transparent; border: none; padding: 20px;"
            )
            self._list_lay.addWidget(ph)
        else:
            for i, card in enumerate(cards):
                silo_map = {s.id: s for s in self._all_silos}
                silo = silo_map.get(getattr(card, "silo_id", None))
                silo_label = silo.number if silo else ""
                item = _CardItem(card, self._update_state, silo_label=silo_label)
                # Тонкая разделительная линия между строками
                item.setStyleSheet(
                    "background: transparent;"
                    + (f" border-bottom: 0.5px solid {BORDER};" if i < len(cards) - 1 else "")
                )
                self._list_lay.addWidget(item)
                self._card_items.append(item)

        self._list_lay.addStretch()
        self._update_state()
        if self._card_items:
            stagger_fade_in(self._card_items, duration=150, step_ms=30)

    # ── Поиск ─────────────────────────────────────────────────────────────────

    def _on_search(self, text: str) -> None:
        t = text.strip().lower()
        for item in self._card_items:
            visible = (
                not t
                or t in str(item.card.probe_number).lower()
                or t in item.card.culture_name.lower()
            )
            item.setVisible(visible)

    # ── Выбор всех ────────────────────────────────────────────────────────────

    def _select_all(self, checked: bool) -> None:
        for item in self._card_items:
            if item.isVisible():
                item._cb.setChecked(checked)

    # ── Обновление состояния ───────────────────────────────────────────────────

    def _update_state(self) -> None:
        sel   = [it for it in self._card_items if it.is_checked]
        n     = len(sel)
        exec_ = self._exec_combo.currentText().strip()
        tank  = self._tank_inp.text().strip()
        weight = self._weight_inp.text().strip()
        sheet  = _TABS[self._active_tab]["sheet"]

        ok = bool(n > 0 and exec_ and tank)
        self._export_btn.setEnabled(ok)

        def _active_val(val, active: bool) -> str:
            color = TEXT_BRIGHT if active else "#707085"
            return (
                f"color: {color}; font-family: '{FONT_UI}', sans-serif;"
                " font-size: 13px; font-weight: 500; background: transparent; border: none;"
            )

        # summary bar
        self._sum_count.setText(str(n))
        self._sum_count.setStyleSheet(_active_val(n, n > 0))
        self._sum_weight.setText(weight or "—")
        self._sum_weight.setStyleSheet(_active_val(weight, bool(weight)))
        self._sum_sheet.setText(sheet if n > 0 else "—")
        self._sum_sheet.setStyleSheet(_active_val(sheet, n > 0))

        # stat card
        self._stat_count.setText(str(n) if n > 0 else "—")
        self._stat_weight.setText(f"{weight} кг" if weight else "—")

        # Считаем средние СП/ЗП
        if sel:
            sp_vals = [getattr(c.card, "sp_total", None) for c in sel]
            zp_vals = [getattr(c.card, "zp_total", None) for c in sel]
            sp_vals = [v for v in sp_vals if v is not None]
            zp_vals = [v for v in zp_vals if v is not None]
            sp_avg = f"{sum(sp_vals)/len(sp_vals):.2f}%" if sp_vals else "—"
            zp_avg = f"{sum(zp_vals)/len(zp_vals):.2f}%" if zp_vals else "—"
        else:
            sp_avg = zp_avg = "—"

        self._stat_sp.setText(sp_avg)
        self._stat_zp.setText(zp_avg)

        # target label
        self._target_lbl.setText(
            f"{n} карт. → {sheet}" if n > 0 else "Выберите карточки"
        )
        self._target_lbl.setStyleSheet(
            f"color: {'#8080a0' if n > 0 else '#525265'};"
            f" font-family: '{FONT_UI}', sans-serif; font-size: 11px; background: transparent; border: none;"
        )

    # ── Экспорт ───────────────────────────────────────────────────────────────

    def _on_export(self) -> None:
        excel_path = config.excel_path
        if not excel_path:
            QMessageBox.warning(self, "Ошибка",
                "Путь к Excel-файлу не указан.\nЗадайте его в Настройки → Основные.")
            return
        if not os.path.exists(excel_path):
            QMessageBox.warning(self, "Ошибка",
                f"Файл не найден:\n{excel_path}\n\nПроверьте путь в Настройки → Основные.")
            return

        selected = [it.card for it in self._card_items if it.is_checked]
        if not selected:
            return

        executor = self._exec_combo.currentText().strip()
        tank     = self._tank_inp.text().strip()

        silo_map = {s.id: s for s in self._all_silos}
        rows = [
            ExportRow(
                card=c,
                silo=silo_map.get(c.silo_id) if getattr(c, "silo_id", None) else None,
                weight_kg=self._weight_inp.text().strip(),
                executor=executor,
                tank_number=tank,
                workshop=getattr(c, "distillation_place", "") or "",
            )
            for c in selected
        ]

        self._export_btn.setEnabled(False)
        self._export_btn.setText("Экспортируется...")
        self._prog_lbl.setText("")
        self._progress_bar.setValue(0)
        fade_in_progress(self._progress_bar, duration=200)

        fn = _TABS[self._active_tab]["fn"]
        self._export_thread = _ExportThread(fn, excel_path, rows)

        def _on_progress(step, total):
            self._progress_bar.setValue(int(step / total * 100) if total > 0 else 0)

        def _on_done(count):
            self._progress_bar.setValue(100)
            QTimer.singleShot(400, lambda: fade_out_progress(self._progress_bar, duration=300))
            self._export_btn.setText("Экспорт в Excel")
            self._prog_lbl.setText(f"✓ Записано {count} строк")
            QTimer.singleShot(3000, lambda: self._prog_lbl.setText(""))
            self._select_all(False)
            self._update_state()

        def _on_lock_error(msg):
            fade_out_progress(self._progress_bar, duration=200)
            self._export_btn.setText("Экспорт в Excel")
            self._update_state()
            QMessageBox.warning(self, "Файл недоступен", msg)

        def _on_error(msg):
            fade_out_progress(self._progress_bar, duration=200)
            self._export_btn.setText("Экспорт в Excel")
            self._update_state()
            import glob
            directory = os.path.dirname(os.path.abspath(excel_path))
            name = os.path.splitext(os.path.basename(excel_path))[0]
            backups = sorted(glob.glob(os.path.join(directory, f"{name}.backup_*.xlsx")))
            full_msg = f"Не удалось записать в Excel:\n{msg}"
            if backups:
                full_msg += f"\n\nРезервная копия:\n{os.path.basename(backups[-1])}"
            QMessageBox.critical(self, "Ошибка записи", full_msg)

        self._export_thread.progress.connect(_on_progress)
        self._export_thread.finished.connect(_on_done)
        self._export_thread.lock_error.connect(_on_lock_error)
        self._export_thread.error.connect(_on_error)
        self._export_thread.start()

    # ── Reload executors ───────────────────────────────────────────────────────

    def _reload_executors(self) -> None:
        from logic.db_service import get_all_workers
        current = self._exec_combo.currentText()
        self._exec_combo.blockSignals(True)
        self._exec_combo.clear()
        self._exec_combo.addItem("")
        for w in get_all_workers():
            self._exec_combo.addItem(w.name)
        idx = self._exec_combo.findText(current)
        if idx >= 0:
            self._exec_combo.setCurrentIndex(idx)
        else:
            self._exec_combo.setEditText(current)
        self._exec_combo.blockSignals(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reload_executors()
        self._all_silos = get_all_silos()
        self._load_cards()
