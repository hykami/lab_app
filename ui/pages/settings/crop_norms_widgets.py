"""
Виджеты для страницы Нормы культур:
RangeField, _DotLineDot, AddCultureDialog, OutlinedCard, ImpurityGroupHeader, CultureEditor.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from ui.style_helpers import (
    scroll_style,
)
from ui.theme import (
    BG, BG_CARD, BORDER,
    TEXT_MAIN, TEXT_BRIGHT, TEXT_MUTED,
    ACCENT_V, FONT_MONO, FONT_UI,
)
from logic.db_service import (
    Culture, save_culture, save_impurity_norm, delete_culture,
)

logger = logging.getLogger(__name__)


# ── RangeField ────────────────────────────────────────────────────────────────

class _DotLineDot(QLabel):
    """Стрелка-разделитель диапазона мин → макс."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("→", parent)
        self.setFixedSize(14, 30)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "color: #5a5a72; background: transparent; border: none;"            " font-size: 11px;"
        )


class RangeField(QWidget):
    """Два поля ввода (мин/макс) с разделителем точка–линия–точка.

    integer_only=True — значения форматируются как целые числа.
    Используется для показателей, которые не могут быть дробными
    (например, Стекловидность, ЧП).
    """

    # Ширина одного поля ввода — рассчитана так, чтобы 4-значное число
    # умещалось целиком (например, диапазоны типа «150 → 450» для ЧП
    # или «1000 → 1200» при необходимости).
    _INPUT_WIDTH: int = 58
    _SEP_WIDTH:   int = 14
    _SPACING:     int = 4

    @classmethod
    def total_width(cls) -> int:
        """Полная ширина виджета — для синхронизации с метками."""
        return cls._INPUT_WIDTH * 2 + cls._SEP_WIDTH + cls._SPACING

    def __init__(self, min_val: float = 0.0, max_val: float = 0.0,
                 integer_only: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._integer_only = integer_only
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._min = self._make_input(min_val)
        self._max = self._make_input(max_val)
        lay.addWidget(self._min)
        lay.addWidget(_DotLineDot())
        lay.addWidget(self._max)
        # Фиксируем ширину виджета чтобы метка над ним совпадала
        self.setFixedWidth(self.total_width())

    def _format(self, value: float) -> str:
        """Форматирует значение для отображения: целое или с двумя знаками."""
        if self._integer_only:
            return f"{int(round(value))}"
        return f"{value:.2f}"

    def _make_input(self, value: float) -> QLineEdit:
        inp = QLineEdit(self._format(value))
        inp.setFixedHeight(30)
        inp.setFixedWidth(self._INPUT_WIDTH)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background: #111114; border: 0.5px solid {BORDER};
                border-radius: 5px; color: {TEXT_MAIN};
                font-family: '{FONT_MONO}', monospace; font-size: 12px; padding: 0 4px;
            }}
            QLineEdit:focus {{ border-color: rgba(108,92,231,0.5); color: {TEXT_BRIGHT}; }}
        """)
        return inp

    def _parse(self, text: str) -> float:
        """Парсит значение из поля: для целочисленного режима — округляет до int."""
        try:
            val = float(text.replace(",", "."))
        except ValueError:
            return 0.0
        if self._integer_only:
            return float(int(round(val)))
        return val

    @property
    def min_value(self) -> float:
        return self._parse(self._min.text())

    @property
    def max_value(self) -> float:
        return self._parse(self._max.text())


# ── AddCultureDialog ──────────────────────────────────────────────────────────

class AddCultureDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить культуру")
        self.setFixedSize(340, 160)
        self.setStyleSheet(f"background: {BG_CARD};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        form = QFormLayout(); form.setSpacing(10)
        self._name = self._inp("Название культуры")
        self._weight = self._inp(""); self._weight.setText("50")
        lbl_style = f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; background: transparent;"
        form.addRow(self._lbl("Название", lbl_style), self._name)
        form.addRow(self._lbl("Навеска, г", lbl_style), self._weight)
        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 6px;
                color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif;
                font-size: 12px; padding: 5px 16px; min-width: 70px;
            }}
            QPushButton:default {{
                background: rgba(108,92,231,0.15); border-color: rgba(108,92,231,0.4); color: {ACCENT_V};
            }}
        """)
        lay.addWidget(btns)

    def _inp(self, placeholder: str) -> QLineEdit:
        inp = QLineEdit(); inp.setPlaceholderText(placeholder); inp.setFixedHeight(34)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background: #111114; border: 0.5px solid {BORDER}; border-radius: 7px;
                color: {TEXT_MAIN}; font-family: '{FONT_UI}', sans-serif; font-size: 13px; padding: 0 11px;
            }}
            QLineEdit:focus {{ border-color: rgba(108,92,231,0.5); }}
        """)
        return inp

    def _lbl(self, text: str, style: str) -> QLabel:
        l = QLabel(text); l.setStyleSheet(style); return l

    @property
    def culture_name(self) -> str: return self._name.text().strip()

    @property
    def sample_weight(self) -> float:
        try: return float(self._weight.text().replace(",", "."))
        except ValueError: return 50.0


# ── OutlinedCard ──────────────────────────────────────────────────────────────

class _BorderOverlay(QWidget):
    def __init__(self, radius: float, border: QColor, parent: QWidget) -> None:
        super().__init__(parent)
        self._radius = radius; self._border = border
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent; border: none;")

    def resizeEvent(self, event) -> None:
        self.resize(self.parent().size()); super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(self._border); pen.setWidthF(0.5)
        p.setPen(pen)
        path = QPainterPath()
        path.addRoundedRect(0.25, 0.25, self.width() - 0.5, self.height() - 0.5, self._radius, self._radius)
        p.drawPath(path); p.end()


class OutlinedCard(QFrame):
    def __init__(self, radius: float = 10.0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: none; border-radius: {radius}px; }}")
        self._overlay = _BorderOverlay(radius, QColor(BORDER), self)
        self._overlay.resize(self.size())

    def resizeEvent(self, event) -> None:
        self._overlay.resize(self.size()); super().resizeEvent(event)


# ── ImpurityGroupHeader ───────────────────────────────────────────────────────

class ImpurityGroupHeader(QWidget):
    def __init__(self, title: str, color: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 8, 0, 4); lay.setSpacing(8)
        line1 = QFrame(); line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet(f"background: {color}; max-height: 1px; border: none; opacity: 0.3;")
        dot = QWidget(); dot.setFixedSize(5, 5)
        dot.setStyleSheet(f"background: {color}; border-radius: 2px;")
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color: {color}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; letter-spacing: 0.04em; background: transparent;")
        line2 = QFrame(); line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet(line1.styleSheet())
        lay.addWidget(line1, 1); lay.addWidget(dot); lay.addWidget(lbl); lay.addWidget(line2, 3)


# ── CultureEditor ─────────────────────────────────────────────────────────────

class CultureEditor(QScrollArea):
    """Правая панель — редактор норм выбранной культуры."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet(scroll_style())
        self._inner = QWidget(); self._inner.setStyleSheet(f"background: {BG};")
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(22, 18, 22, 22)
        self._lay.setSpacing(14)
        self.setWidget(self._inner)
        self._culture: Optional[Culture] = None
        self._imp_fields: dict[int, RangeField] = {}
        self._sp_range: Optional[RangeField] = None
        self._zp_range: Optional[RangeField] = None
        self._weight_inp: Optional[QLineEdit] = None

        ph = QLabel("Выберите культуру из списка")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet(f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif; font-size: 13px; background: transparent;")
        self._lay.addWidget(ph); self._lay.addStretch()

    def load_culture(self, culture: Culture) -> None:
        self._culture = culture
        self._imp_fields.clear()
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().setParent(None)

        # ── Заголовок культуры ────────────────────────────────────────────────
        hdr_card = OutlinedCard()
        hdr_lay = QVBoxLayout(hdr_card)
        hdr_lay.setContentsMargins(18, 14, 18, 16)
        hdr_lay.setSpacing(12)

        name_lbl = QLabel(culture.name)
        name_lbl.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 16px; font-weight: 600; background: transparent;"
        )
        hdr_lay.addWidget(name_lbl)

        # ── Навеска + СП/ЗП в строку ──────────────────────────────────────────
        basics_row = QHBoxLayout(); basics_row.setSpacing(20); basics_row.setContentsMargins(0,0,0,0)

        # Навеска
        w_col = QVBoxLayout(); w_col.setSpacing(5)
        w_col.addWidget(self._mini_label("Навеска, г"))
        self._weight_inp = QLineEdit(str(int(culture.sample_weight)))
        self._weight_inp.setFixedHeight(34); self._weight_inp.setFixedWidth(80)
        self._weight_inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_inp.setStyleSheet(f"""
            QLineEdit {{
                background: #111114; border: 0.5px solid {BORDER}; border-radius: 7px;
                color: {TEXT_MAIN}; font-family: '{FONT_MONO}', monospace; font-size: 14px; padding: 0 8px;
            }}
            QLineEdit:focus {{ border-color: rgba(108,92,231,0.5); }}
        """)
        w_col.addWidget(self._weight_inp)
        basics_row.addLayout(w_col)

        # СП
        sp_col = QVBoxLayout(); sp_col.setSpacing(5); sp_col.setContentsMargins(0,0,0,0)
        sp_lbl = self._mini_label("СП мин–макс, %")
        sp_lbl.setFixedWidth(RangeField.total_width())
        sp_col.addWidget(sp_lbl)
        self._sp_range = RangeField(culture.sp_min, culture.sp_max)
        sp_col.addWidget(self._sp_range)
        basics_row.addLayout(sp_col)

        # ЗП
        zp_col = QVBoxLayout(); zp_col.setSpacing(5); zp_col.setContentsMargins(0,0,0,0)
        zp_lbl = self._mini_label("ЗП мин–макс, %")
        zp_lbl.setFixedWidth(RangeField.total_width())
        zp_col.addWidget(zp_lbl)
        self._zp_range = RangeField(culture.zp_min, culture.zp_max)
        zp_col.addWidget(self._zp_range)
        basics_row.addLayout(zp_col)

        basics_row.addStretch()
        hdr_lay.addLayout(basics_row)

        # ── Нормы показателей (зависят от культуры) ──────────────────────────
        from logic.card_params import (
            WHEAT_CULTURES, WHEAT_EXTRA, PROTEIN_CULTURES, CARD_TYPE_WASTE,
        )

        # Определяем какие показатели есть у этой культуры.
        # Кортеж: (key_prefix, label, integer_only).
        # integer_only=True — показатель не может быть дробным (целое число).
        param_norms = []
        param_norms.append(("humidity",     "Влажность, %",              False))
        if culture.name != CARD_TYPE_WASTE:
            if culture.name not in {"Кукуруза"}:
                param_norms.append(("natura",   "Натура, г/л",               True))
            if culture.name in WHEAT_CULTURES:
                param_norms.append(("gluten",   "Клейковина (экспресс), %",  False))
            if culture.name in WHEAT_CULTURES or culture.name in PROTEIN_CULTURES:
                param_norms.append(("protein",  "М.д. белка, %",             False))
            if culture.name in WHEAT_EXTRA:
                param_norms.append(("vitreousness", "Стекловидность, %",     True))
                param_norms.append(("idc",          "ИДК",                   True))
                param_norms.append(("fall_number",  "ЧП, с",                 True))

        if param_norms:
            self._param_fields: dict[str, RangeField] = {}
            params_card = OutlinedCard()
            pl = QVBoxLayout(params_card)
            pl.setContentsMargins(14, 12, 14, 14)
            pl.setSpacing(8)

            # Заголовок
            ph = QWidget(); ph.setStyleSheet("background: transparent;")
            phl = QHBoxLayout(ph); phl.setContentsMargins(0, 0, 0, 4); phl.setSpacing(8)
            line1 = QFrame(); line1.setFrameShape(QFrame.Shape.HLine)
            line1.setStyleSheet("background: #4ade80; max-height: 1px; border: none;")
            dot2 = QWidget(); dot2.setFixedSize(5, 5)
            dot2.setStyleSheet("background: #4ade80; border-radius: 2px;")
            lbl2 = QLabel("ПОКАЗАТЕЛИ")
            lbl2.setStyleSheet(f"color: #4ade80; font-family: '{FONT_UI}', sans-serif; font-size: 12px; letter-spacing: 0.04em; background: transparent;")
            line2 = QFrame(); line2.setFrameShape(QFrame.Shape.HLine)
            line2.setStyleSheet(line1.styleSheet())
            phl.addWidget(line1, 1); phl.addWidget(dot2); phl.addWidget(lbl2); phl.addWidget(line2, 3)
            pl.addWidget(ph)

            # Поля в два столбца: лейбл фиксирован, поле справа, колонки симметричны
            col_l = QVBoxLayout(); col_l.setSpacing(8)
            col_r = QVBoxLayout(); col_r.setSpacing(4)
            for idx, (key_prefix, label, integer_only) in enumerate(param_norms):
                row = QHBoxLayout(); row.setSpacing(8); row.setContentsMargins(0, 0, 0, 0)
                n = QLabel(label)
                n.setWordWrap(False)
                n.setFixedWidth(148)
                n.setStyleSheet(f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif; font-size: 11px; background: transparent;")
                lo = getattr(culture, f"{key_prefix}_min", 0.0)
                hi = getattr(culture, f"{key_prefix}_max", 100.0)
                rf = RangeField(lo, hi, integer_only=integer_only)
                self._param_fields[key_prefix] = rf
                row.addWidget(n)
                row.addWidget(rf)
                row.addStretch()
                rw = QWidget(); rw.setStyleSheet("background: transparent;"); rw.setLayout(row)
                (col_l if idx % 2 == 0 else col_r).addWidget(rw)

            # Вертикальный сепаратор с отступами от верхней и нижней границ
            sep_wrap = QWidget()
            sep_wrap.setStyleSheet("background: transparent;")
            sep_wrap.setFixedWidth(1)
            sep_inner = QVBoxLayout(sep_wrap)
            sep_inner.setContentsMargins(0, 4, 0, 4)
            sep_inner.setSpacing(0)
            sep_line = QWidget()
            sep_line.setStyleSheet(f"background: {BORDER}; border: none;")
            sep_inner.addWidget(sep_line)

            grid = QHBoxLayout(); grid.setSpacing(16); grid.setContentsMargins(0, 0, 0, 0)
            grid.addLayout(col_l, 1)
            grid.addWidget(sep_wrap)
            grid.addLayout(col_r, 1)
            pl.addLayout(grid)
            self._lay.addWidget(params_card)
        else:
            self._param_fields = {}

        self._lay.addWidget(hdr_card)

        # ── Примеси ───────────────────────────────────────────────────────────
        if culture.impurities:
            imp_card = OutlinedCard()
            imp_lay = QVBoxLayout(imp_card)
            imp_lay.setContentsMargins(14, 12, 14, 14)
            imp_lay.setSpacing(6)

            sp_imps = [i for i in culture.impurities if i.group_name == "СП"]
            zp_imps = [i for i in culture.impurities if i.group_name == "ЗП"]

            if sp_imps:
                imp_lay.addWidget(ImpurityGroupHeader("СОРНАЯ ПРИМЕСЬ", "#f97316"))
                imp_lay.addLayout(self._imp_grid(sp_imps))
            if zp_imps:
                imp_lay.addWidget(ImpurityGroupHeader("ЗЕРНОВАЯ ПРИМЕСЬ", "#6c5ce7"))
                imp_lay.addLayout(self._imp_grid(zp_imps))

            self._lay.addWidget(imp_card)

        # ── Кнопка удалить культуру ───────────────────────────────────────────
        del_btn = QPushButton("Удалить культуру")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFixedHeight(34)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 0.5px solid rgba(248,113,113,0.2);
                border-radius: 7px; color: rgba(248,113,113,0.5);
                font-family: '{FONT_UI}', sans-serif; font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(248,113,113,0.06);
                border-color: rgba(248,113,113,0.4);
                color: #f97316;
            }}
        """)
        del_btn.clicked.connect(self._on_delete)
        self._lay.addWidget(del_btn)
        self._lay.addStretch()

    def _imp_grid(self, imps) -> QHBoxLayout:
        """Два столбца примесей рядом."""
        grid = QHBoxLayout(); grid.setSpacing(10); grid.setContentsMargins(0, 0, 0, 0)
        col1 = QVBoxLayout(); col1.setSpacing(8)
        col2 = QVBoxLayout(); col2.setSpacing(8)
        for idx, imp in enumerate(imps):
            row = QHBoxLayout(); row.setSpacing(8); row.setContentsMargins(0, 0, 0, 0)
            n = QLabel(imp.name)
            n.setFixedWidth(95)
            n.setStyleSheet(f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; background: transparent;")
            rf = RangeField(imp.min_val, imp.max_val)
            self._imp_fields[imp.id] = rf
            row.addWidget(n); row.addWidget(rf); row.addStretch()
            rw = QWidget(); rw.setStyleSheet("background: transparent;"); rw.setLayout(row)
            (col1 if idx % 2 == 0 else col2).addWidget(rw)
        grid.addLayout(col1); grid.addLayout(col2); grid.addStretch()
        return grid

    def _mini_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: #707085; font-family: '{FONT_UI}', sans-serif; font-size: 12px; font-weight: 500; background: transparent;")
        return lbl

    def _on_delete(self) -> None:
        if not self._culture:
            return
        reply = QMessageBox.question(
            self, "Удалить культуру",
            f"Удалить «{self._culture.name}»?\nВсе нормы примесей также будут удалены.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        delete_culture(self._culture.id)
        self._culture = None
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().setParent(None)
        ph = QLabel("Культура удалена. Выберите другую.")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet(f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif; font-size: 13px; background: transparent;")
        self._lay.addWidget(ph); self._lay.addStretch()
        # Вызываем callback родителя если задан
        cb = getattr(self, '_on_delete_callback', None)
        if callable(cb):
            cb()

    def collect_and_save(self) -> bool:
        if not self._culture:
            return False
        try:
            if self._weight_inp:
                try: self._culture.sample_weight = float(self._weight_inp.text().replace(",", "."))
                except ValueError: pass
            if self._sp_range:
                self._culture.sp_min = self._sp_range.min_value
                self._culture.sp_max = self._sp_range.max_value
            if self._zp_range:
                self._culture.zp_min = self._zp_range.min_value
                self._culture.zp_max = self._zp_range.max_value
            # Сохраняем нормы показателей
            for key_prefix, rf in getattr(self, '_param_fields', {}).items():
                setattr(self._culture, f"{key_prefix}_min", rf.min_value)
                setattr(self._culture, f"{key_prefix}_max", rf.max_value)
            save_culture(self._culture)
            for imp_id, field in self._imp_fields.items():
                norm = next((i for i in self._culture.impurities if i.id == imp_id), None)
                if norm:
                    norm.min_val = field.min_value
                    norm.max_val = field.max_value
                    save_impurity_norm(norm)
            return True
        except Exception:
            logger.exception("Ошибка сохранения норм культуры")
            return False
