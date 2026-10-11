"""
Общий компонент блока примесей.
Используется на странице Создать и в детальном просмотре.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.theme import BG_CARD, BORDER, TEXT_MUTED, ACCENT_G, FONT_MONO, FONT_UI


class ImpurityBlock(QFrame):
    """
    Блок примесей с заголовком и таблицей строк.

    Поддерживает два режима:
    - Обычный: total, items
    - Входной контроль: + base_total, base_items → показывает базовое и итог
    """

    def __init__(self, group: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._group = group
        is_sp      = group == "СП"
        self._hdr_bg  = "rgba(248,113,113,0.06)" if is_sp else "rgba(108,92,231,0.06)"
        self._txt_col = "#f87171" if is_sp else "#6c5ce7"
        self._title   = "СОРНАЯ ПРИМЕСЬ" if is_sp else "ЗЕРНОВАЯ ПРИМЕСЬ"

        self.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

        self._build_header()
        self._build_col_header(ic=False)
        self._build_rows()

    # ── Строители ─────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        self._hdr_w = QWidget()
        self._hdr_w.setStyleSheet(
            f"background: {self._hdr_bg}; border-radius: 10px 10px 0 0;"
            f"border-bottom: 0.5px solid {BORDER};"
        )
        hl = QHBoxLayout(self._hdr_w)
        hl.setContentsMargins(14, 9, 14, 9)

        t = QLabel(self._title)
        t.setStyleSheet(
            f"color: {self._txt_col}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
        )
        hl.addWidget(t)
        hl.addStretch()

        self._total_lbl = QLabel("—")
        self._total_lbl.setStyleSheet(
            f"color: {self._txt_col}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 13px; font-weight: 300; background: transparent; border: none;"
        )
        hl.addWidget(self._total_lbl)
        self._lay.addWidget(self._hdr_w)

    def _build_col_header(self, ic: bool) -> None:
        if hasattr(self, "_col_hdr_w") and self._col_hdr_w:
            self._col_hdr_w.setParent(None)
            self._col_hdr_w.deleteLater()
            self._col_hdr_w = None

        self._col_hdr_w = QWidget()
        self._col_hdr_w.setFixedHeight(24)
        self._col_hdr_w.setStyleSheet(f"background: #111114; border-bottom: 0.5px solid {BORDER};")
        cl = QHBoxLayout(self._col_hdr_w)
        cl.setContentsMargins(14, 0, 14, 0)
        cl.setSpacing(0)

        col_w = 90 if ic else 65
        for i, (text, w) in enumerate([("ПРИМЕСЬ", 0), ("ГР", col_w), ("%", col_w)]):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
            )
            if w:
                lbl.setFixedWidth(w)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cl.addWidget(lbl)
                if i == 1:  # после ГР — разделитель
                    sep = QLabel(); sep.setFixedWidth(12)
                    sep.setStyleSheet("background: transparent; border: none;")
                    cl.addWidget(sep)
            else:
                cl.addWidget(lbl, 1)

        self._lay.insertWidget(1, self._col_hdr_w)
        self._col_w = col_w

    def _build_rows(self) -> None:
        self._row_widgets: list[QWidget] = []
        self._rows: list[tuple[QLabel, QLabel, QLabel]] = []

        for i in range(4):
            row = QWidget()
            row.setFixedHeight(34)
            row.setStyleSheet(
                "background: transparent;" +
                ("" if i == 3 else "border-bottom: 0.5px solid #1a1a1e;")
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 0, 14, 0)
            rl.setSpacing(0)

            name = QLabel("—")
            name.setStyleSheet(
                f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 12px; background: transparent; border: none;"
            )
            grm = QLabel("—")
            grm.setFixedWidth(65)
            grm.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grm.setStyleSheet(
                f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent; border: none;"
            )
            gap = QLabel()
            gap.setFixedWidth(12)
            gap.setStyleSheet("background: transparent; border: none;")

            pct = QLabel("—")
            pct.setFixedWidth(65)
            pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pct.setStyleSheet(
                f"color: {ACCENT_G}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent; border: none;"
            )
            rl.addWidget(name, 1)
            rl.addWidget(grm)
            rl.addWidget(gap)
            rl.addWidget(pct)

            self._lay.addWidget(row)
            self._row_widgets.append(row)
            self._rows.append((name, grm, pct))

    def _set_col_width(self, w: int) -> None:
        for name_lbl, grm, pct in self._rows:
            grm.setFixedWidth(w)
            pct.setFixedWidth(w)

    # ── Публичный API ─────────────────────────────────────────────────────────

    def update(self, total: float, items,
               base_total: float = None,
               base_items=None) -> None:
        """
        items — list[ImpurityEntry] или list[dict].
        base_items — то же, при входном контроле.
        """
        ic = base_total is not None and base_items is not None

        # Перестраиваем заголовок колонок если режим изменился
        if ic != (self._col_w == 90):
            self._build_col_header(ic)
            self._set_col_width(self._col_w)

        # Заголовок
        if ic:
            self._total_lbl.setText(f"{base_total:.2f}% → {total:.2f}%")
        else:
            self._total_lbl.setText(f"{total:.2f} %")

        # Строки
        for i, (n, g, p) in enumerate(self._rows):
            row_widget = self._row_widgets[i]
            if i >= len(items):
                # Скрываем лишние строки
                row_widget.setVisible(False)
                n.setText(""); g.setText(""); p.setText("")
                continue
            row_widget.setVisible(True)
            imp = items[i]
            # Поддержка и ImpurityEntry и dict
            name_val = imp.name if hasattr(imp, "name") else imp.get("name", "—")
            grm_val  = imp.grams if hasattr(imp, "grams") else imp.get("grams", 0)
            pct_val  = imp.percent if hasattr(imp, "percent") else imp.get("percent", 0)

            n.setText(name_val)

            if ic and base_items and i < len(base_items):
                b = base_items[i]
                b_grm = b.grams if hasattr(b, "grams") else b.get("grams", 0)
                b_pct = b.percent if hasattr(b, "percent") else b.get("percent", 0)
                g.setText(f"{b_grm:.2f} | {grm_val:.2f}")
                p.setText(f"{b_pct:.2f} | {pct_val:.2f}")
            else:
                g.setText(f"{grm_val:.2f}")
                p.setText(f"{pct_val:.2f}")

    def clear(self) -> None:
        self._total_lbl.setText("—")
        for i, (n, g, p) in enumerate(self._rows):
            self._row_widgets[i].setVisible(True)
            n.setText("—"); g.setText("—"); p.setText("—")
