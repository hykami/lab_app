"""
ImpurityInputBlock v2.0 — блок примесей в стиле нового макета.
Сетка 4×N карточек с лейблом, полем % и граммами под ним.
"""
from __future__ import annotations
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QSizePolicy, QVBoxLayout, QWidget,
)

from ui.theme import BORDER, FONT_MONO, FONT_UI, TEXT_BRIGHT
from logic.card_calc import ImpurityEntry

COLS = 4

# ── Цвета групп ──────────────────────────────────────────────────────────────
_GROUP_COLORS = {
    "СП": {"accent": "#f39c12", "bg": "rgba(243,156,18,0.10)", "border": "rgba(243,156,18,0.40)"},
    "ЗП": {"accent": "#a29bfe", "bg": "rgba(162,155,254,0.10)", "border": "rgba(162,155,254,0.35)"},
}
_DEFAULT_COLOR = {"accent": "#6c5ce7", "bg": "rgba(108,92,231,0.10)", "border": "rgba(108,92,231,0.35)"}


def _inp_style(state: str = "normal", size: int = 12) -> str:
    if state == "error":
        b, bf, bg = "rgba(248,113,113,0.7)", "rgba(248,113,113,0.9)", "rgba(248,113,113,0.06)"
    elif state == "ok":
        b, bf, bg = "rgba(74,222,128,0.5)", "rgba(74,222,128,0.7)", "rgba(74,222,128,0.05)"
    elif state == "warn":
        b, bf, bg = "rgba(243,156,18,0.45)", "rgba(243,156,18,0.7)", "rgba(243,156,18,0.08)"
    else:
        b, bf, bg = BORDER, "rgba(108,92,231,0.5)", "#111114"
    return f"""
        QLineEdit {{
            background: {bg}; border: 0.5px solid {b};
            border-radius: 5px; color: {TEXT_BRIGHT};
            font-family: '{FONT_MONO}', monospace; font-size: {size}px;
        }}
        QLineEdit:focus {{ border-color: {bf}; }}
    """


def _zero_inp_style() -> str:
    return f"""
        QLineEdit {{
            background: #0f0f11; border: 0.5px solid #1c1c1e;
            border-radius: 5px; color: #2e2e3c;
            font-family: '{FONT_MONO}', monospace; font-size: 12px;
        }}
        QLineEdit:focus {{ border-color: rgba(108,92,231,0.35); color: #606070; }}
    """


# ── Одна ячейка примеси ───────────────────────────────────────────────────────

class _ImpCell(QWidget):
    """Ячейка: лейбл + input% + граммы."""

    def __init__(self, name: str, naveski: float,
                 norm_min: float, norm_max: float,
                 warn_color: str,
                 on_changed: Callable,
                 parent=None):
        super().__init__(parent)
        self._name       = name
        self._naveski    = naveski
        self._norm_min   = norm_min
        self._norm_max   = norm_max
        self._warn_color = warn_color
        self._on_changed = on_changed
        self._auto_val   = 0.0
        self._manual     = False

        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(3)

        self._lbl = QLabel(name.upper())
        self._lbl.setStyleSheet(
            f"color: #606075; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; font-weight: 500;"
            "background: transparent; border: none;"
        )
        lay.addWidget(self._lbl)

        inp_row = QWidget()
        inp_row.setStyleSheet("background: transparent;")
        ir = QHBoxLayout(inp_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.setSpacing(3)

        self._inp = QLineEdit()
        self._inp.setFixedSize(50, 26)
        self.setFixedWidth(103)
        self._inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inp.setStyleSheet(_inp_style())
        self._inp.textEdited.connect(self._on_edited)
        self._inp.editingFinished.connect(self._on_finished)
        ir.addWidget(self._inp)

        self._pct_lbl = QLabel("%")
        self._pct_lbl.setStyleSheet(
            "color: #606075; font-size: 11px;"
            "background: transparent; border: none;"
        )
        ir.addWidget(self._pct_lbl)
        lay.addWidget(inp_row)

        self._grams = QLabel("—")
        self._grams.setStyleSheet(
            f"color: #606075; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._grams)

    # ── validation ────────────────────────────────────────────────────────────

    def _validate(self, text: str) -> str:
        if not text.strip():
            return "empty"
        try:
            val = float(text.replace(",", "."))
        except ValueError:
            return "error"
        if abs(round(val / 0.02) * 0.02 - val) > 1e-9:
            return "error"
        if self._norm_max > 0 and val > self._norm_max:
            return "warn"
        return "ok"

    def _on_edited(self, text: str) -> None:
        self._manual = bool(text.strip())
        if not self._manual:
            self._inp.setStyleSheet(_inp_style())
            self._refresh_grams()
            self._on_changed()
            return
        state = self._validate(text)
        if state == "empty":
            self._inp.setStyleSheet(_inp_style())
        elif state == "warn":
            self._inp.setStyleSheet(_inp_style("warn"))
        elif state == "error":
            self._inp.setStyleSheet(_inp_style("error"))
        else:
            self._inp.setStyleSheet(_inp_style("ok"))
        self._on_changed()

    def _on_finished(self) -> None:
        if self._manual and self._validate(self._inp.text()) == "ok":
            self._refresh_grams()

    def _refresh_grams(self) -> None:
        val = self.effective_value
        if val > 0 and self._naveski > 0:
            g = round(val * self._naveski / 100, 2)
            self._grams.setText(f"{g:.2f} г")
            self._grams.setStyleSheet(
                f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
        else:
            self._grams.setText("0.00 г")
            self._grams.setStyleSheet(
                "color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_manual(self) -> bool:
        return self._manual

    @property
    def manual_value(self) -> Optional[float]:
        if not self._manual:
            return None
        try:
            return float(self._inp.text().replace(",", "."))
        except ValueError:
            return None

    @property
    def effective_value(self) -> float:
        mv = self.manual_value
        return mv if mv is not None else self._auto_val

    def set_auto(self, val: float) -> None:
        self._auto_val = val
        if not self._manual:
            if val > 0:
                self._inp.setPlaceholderText(f"{val:.2f}")
                self._inp.setStyleSheet(_inp_style())
            else:
                self._inp.setPlaceholderText("0.00")
                self._inp.setStyleSheet(_zero_inp_style())
            self._refresh_grams()

    def set_naveski(self, naveski: float) -> None:
        self._naveski = naveski
        self._refresh_grams()

    def set_error(self, on: bool) -> None:
        self._inp.setStyleSheet(_inp_style("error" if on else "normal"))

    def reset(self) -> None:
        self._manual = False
        self._inp.clear()
        self._inp.setPlaceholderText(f"{self._auto_val:.2f}" if self._auto_val > 0 else "0.00")
        self._inp.setStyleSheet(_inp_style() if self._auto_val > 0 else _zero_inp_style())
        self._refresh_grams()


# ── Блок примесей ─────────────────────────────────────────────────────────────

class ImpurityInputBlock(QFrame):

    def __init__(self, group: str, naveski: float = 50.0,
                 on_changed: Callable | None = None,
                 parent=None):
        super().__init__(parent)
        self._group      = group
        self._naveski    = naveski
        self._on_changed = on_changed or (lambda: None)
        self._rows: list[_ImpCell] = []
        self._total_min  = 0.0
        self._total_max  = 99.0

        clr = _GROUP_COLORS.get(group, _DEFAULT_COLOR)
        self._accent = clr["accent"]
        self._bg     = clr["bg"]
        self._border_clr = clr["border"]

        self.setStyleSheet(
            "QFrame { background: #161618; border: 0.5px solid #252528;"
            " border-radius: 10px; }"
        )

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        self._build_header()
        # Ширина = COLS ячеек × 90px + (COLS-1) разделителей × 1px
        self._cell_w = 103
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        # Контейнер строк примесей
        self._grid_w = QWidget()
        self._grid_w.setStyleSheet("background: transparent;")
        self._grid_vbox = QVBoxLayout(self._grid_w)
        self._grid_vbox.setContentsMargins(0, 0, 0, 0)
        self._grid_vbox.setSpacing(0)
        self._outer.addWidget(self._grid_w)

    def _build_header(self) -> None:
        hdr = QWidget()
        hdr.setStyleSheet(
            "background: transparent; border-bottom: 0.5px solid #1e1e22;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 8, 14, 8)
        hl.setSpacing(8)

        bar = QWidget()
        bar.setFixedSize(3, 14)
        bar.setStyleSheet(
            f"background: {self._accent}; border-radius: 2px; border: none;"
        )
        hl.addWidget(bar)

        title = QLabel("Сорная примесь" if self._group == "СП" else "Зерновая примесь")
        title.setStyleSheet(
            f"color: #e8e8f0; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; font-weight: 500; background: transparent; border: none;"
        )
        hl.addWidget(title)
        hl.addStretch()

        # Бар нормы (скрыт по требованию макета)
        self._bar_track = QWidget()
        self._bar_track.setFixedSize(0, 4)
        self._bar_track.setStyleSheet(
            "background: #1e1e22; border-radius: 2px; border: none;"
        )
        self._bar_fill = QWidget(self._bar_track)
        self._bar_fill.setFixedHeight(4)
        self._bar_fill.setStyleSheet(
            f"background: {self._accent}; border-radius: 2px; border: none; opacity: 0.65;"
        )
        self._bar_fill.resize(0, 4)
        self._bar_track.hide()
        hl.addWidget(self._bar_track)

        self._total_inp = QLineEdit()
        self._total_inp.setPlaceholderText("1.60" if self._group == "СП" else "3.20")
        self._total_inp.setFixedSize(60, 26)
        self._total_inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._total_inp.setStyleSheet(
            f"QLineEdit {{ background: {self._bg}; border: 0.5px solid {self._border_clr};"
            f" border-radius: 5px; color: {self._accent};"
            f" font-family: '{FONT_MONO}', monospace; font-size: 12px; }}"
            f"QLineEdit:focus {{ border-color: {self._accent}; }}"
        )
        self._total_inp.textEdited.connect(self._on_total_edited)
        self._total_inp.textEdited.connect(self._update_bar)
        hl.addWidget(self._total_inp)

        # ── Элементы входного контроля (стрелка + накинутое значение) ─────────
        self._ic_arrow = QLabel("→")
        self._ic_arrow.setStyleSheet(
            "color: #6a6a80; font-size: 14px; font-weight: 700;"
            " background: transparent; border: none; padding: 0 2px;"
        )
        self._ic_arrow.setVisible(False)
        hl.addWidget(self._ic_arrow)

        bumped_color = "#f87171" if self._group == "СП" else "#fbbf24"
        bumped_border = "rgba(248,113,113,0.25)" if self._group == "СП" else "rgba(251,191,36,0.22)"
        self._ic_bumped = QLabel("—")
        self._ic_bumped.setFixedSize(60, 26)
        self._ic_bumped.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ic_bumped.setStyleSheet(
            f"background: #0e0e12; border: 0.5px solid {bumped_border};"
            f" border-radius: 5px; color: {bumped_color}; opacity: 0.6;"
            f" font-family: '{FONT_MONO}', monospace; font-size: 12px;"
        )
        self._ic_bumped.setVisible(False)
        hl.addWidget(self._ic_bumped)

        norm_lbl = QLabel("/ — %")
        norm_lbl.setStyleSheet(
            "color: #606075; font-size: 12px; background: transparent; border: none;"
        )
        self._norm_lbl = norm_lbl
        norm_lbl.hide()
        hl.addWidget(norm_lbl)

        self._outer.addWidget(hdr)

    def _update_bar(self, *_) -> None:
        try:
            val = float(self._total_inp.text().replace(",", "."))
        except ValueError:
            val = 0.0
        norm = self._total_max if self._total_max < 99 else 5.0
        pct  = min(val / norm, 1.0) if norm > 0 else 0
        px   = int(pct * 80)
        self._bar_fill.resize(px, 4)

    # ── Строки сетки ──────────────────────────────────────────────────────────

    def setup_impurities(self, names: list[str], naveski: float,
                         norms: dict | None = None,
                         names_row2: list[str] | None = None) -> None:
        """
        names       — основной ряд примесей (ряд 1).
        names_row2  — дополнительный ряд примесей (ряд 2).
        """
        # Очистить старые строки
        for cell in self._rows:
            cell.setParent(None)
        self._rows.clear()
        while self._grid_vbox.count():
            item = self._grid_vbox.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        self._naveski = naveski
        norms = norms or {}

        def _add_row(row_names: list[str], is_first: bool) -> None:
            """Добавляет горизонтальный ряд ячеек."""
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(0)
            border_top = "none" if is_first else "0.5px solid #1a1a1e"
            for c_idx, name in enumerate(row_names):
                n_min, n_max = norms.get(name, (0.0, 0.0))
                cell = _ImpCell(name, naveski, n_min, n_max,
                                self._accent, self._on_row_changed)
                self._rows.append(cell)
                is_last = (c_idx == len(row_names) - 1)
                border_right = "none" if is_last else "0.5px solid #1e1e22"
                cell.setStyleSheet(
                    f"background: transparent;"
                    f"border-right: {border_right};"
                    f"border-top: {border_top};"
                )
                row_h.addWidget(cell)
            row_h.addStretch()  # прижимаем ячейки влево
            self._grid_vbox.addWidget(row_w)

        # ── Ряд 1: основные примеси ───────────────────────────────────────
        actual_cols = min(len(names), COLS) if names else COLS
        # Ширина управляется родительским layout (50/50 для горизонтального макета)
        self.setMinimumWidth(340)

        if names:
            for chunk_idx, i in enumerate(range(0, len(names), COLS)):
                _add_row(names[i:i + COLS], is_first=(chunk_idx == 0))

        # ── Разделитель между рядами ──────────────────────────────────────
        if names_row2:
            sep_wrap = QWidget()
            sep_wrap.setStyleSheet("background: transparent;")
            sep_lay = QHBoxLayout(sep_wrap)
            sep_lay.setContentsMargins(14, 0, 14, 0)
            sep_lay.setSpacing(0)
            sep_line = QWidget()
            sep_line.setFixedHeight(1)
            sep_line.setStyleSheet("background: #252528; border: none;")
            sep_lay.addWidget(sep_line)
            self._grid_vbox.addWidget(sep_wrap)

            # ── Ряд 2: дополнительные примеси ────────────────────────────
            for chunk_idx, i in enumerate(range(0, len(names_row2), COLS)):
                _add_row(names_row2[i:i + COLS], is_first=(chunk_idx == 0))

    def _on_row_changed(self) -> None:
        self._on_changed()

    # ── Публичный API ─────────────────────────────────────────────────────────

    def set_total_norms(self, total_min: float, total_max: float) -> None:
        self._total_min = total_min
        self._total_max = total_max
        norm_str = f"/ {total_max:.1f} %"
        self._norm_lbl.setText(norm_str)
        self._update_bar()

    def set_naveski(self, naveski: float) -> None:
        self._naveski = naveski
        for cell in self._rows:
            cell.set_naveski(naveski)

    def connect_total(self, callback) -> None:
        self._total_inp.textEdited.connect(callback)

    @property
    def total_value(self) -> str:
        return self._total_inp.text().strip()

    def update_auto_values(self, total: float) -> None:
        if not self._rows:
            return
        manual_sum = sum(r.effective_value for r in self._rows if r.is_manual)
        auto_rows  = [r for r in self._rows if not r.is_manual]
        remainder  = max(0.0, round(total - manual_sum, 10))
        if not auto_rows:
            return
        unit        = 0.02
        total_units = round(remainder / unit)
        weights     = [max(0.01, r._auto_val) for r in auto_rows]
        w_sum       = sum(weights)
        normed      = [w / w_sum for w in weights]
        raw         = [max(0, round(w * total_units)) for w in normed]
        diff  = total_units - sum(raw)
        order = sorted(range(len(auto_rows)), key=lambda i: -normed[i])
        i = 0
        while diff > 0:
            raw[order[i % len(order)]] += 1; diff -= 1; i += 1
        while diff < 0:
            idx = order[i % len(order)]
            if raw[idx] > 0:
                raw[idx] -= 1; diff += 1
            i += 1
        for row, units in zip(auto_rows, raw):
            row.set_auto(round(units * unit, 2))

    def collect_entries(self, naveski: float) -> list[ImpurityEntry]:
        return [
            ImpurityEntry(
                name=r.name,
                percent=r.effective_value,
                grams=round(r.effective_value * naveski / 100, 2),
            )
            for r in self._rows
        ]

    def validate(self, total: float) -> list[str]:
        errors = []
        unit = 0.02
        for r in self._rows:
            if not r.is_manual:
                continue
            val = r.manual_value
            if val is None:
                errors.append(f"{self._group}: '{r.name}' — некорректное значение")
                continue
            if abs(round(val / unit) * unit - val) > 1e-9:
                errors.append(f"{self._group}: '{r.name}' = {val} — не кратно 0.02")
            if r._norm_max > 0 and val > r._norm_max:
                errors.append(f"{self._group}: '{r.name}' = {val} > макс. {r._norm_max}")
        manual_sum = sum(r.effective_value for r in self._rows if r.is_manual)
        if manual_sum > total + 1e-9:
            errors.append(f"{self._group}: сумма {manual_sum:.2f} > итого {total}")
        return errors

    def validate_total(self) -> str | None:
        text = self._total_inp.text().strip()
        if not text:
            return None
        try:
            val = float(text.replace(",", "."))
        except ValueError:
            return f"{self._group}%: некорректное значение «{text}»"
        if val < 0 or (self._total_max < 99 and val > self._total_max):
            return f"{self._group}% = {text} вне диапазона [{self._total_min:.1f}, {self._total_max:.1f}]"
        return None

    def _on_total_edited(self, text: str) -> None:
        if not text.strip():
            self._total_inp.setStyleSheet(
                f"QLineEdit {{ background: {self._bg}; border: 0.5px solid {self._border_clr};"
                f" border-radius: 5px; color: {self._accent};"
                f" font-family: '{FONT_MONO}', monospace; font-size: 12px; }}"
                f"QLineEdit:focus {{ border-color: {self._accent}; }}"
            )

    def set_bumped_total(self, base: float, bumped: float) -> None:
        """Показывает накинутое значение рядом с базовым (для входного контроля)."""
        self._ic_bumped.setText(f"{bumped:.2f}")
        self._ic_arrow.setVisible(True)
        self._ic_bumped.setVisible(True)

    def clear_bumped_total(self) -> None:
        """Скрывает накинутое значение."""
        self._ic_arrow.setVisible(False)
        self._ic_bumped.setVisible(False)

    def update_total_from_items(self) -> float:
        """Пересчитывает и записывает total как сумму всех effective_value примесей."""
        total = round(sum(r.effective_value for r in self._rows), 2)
        self._total_inp.setText(str(total) if total > 0 else "")
        self._update_bar()
        return total

    def reset_manual(self) -> None:
        for row in self._rows:
            row.reset()

    def clear(self) -> None:
        self._total_inp.clear()
        self.reset_manual()
        self._bar_fill.resize(0, 4)
