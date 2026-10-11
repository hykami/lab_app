"""
Настройки → Силоса.
Таблица всех силосов с возможностью редактирования содержимого.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.style_helpers import scroll_style
from ui.theme import (
    BG_CARD, BORDER, TEXT_MAIN,
    TEXT_BRIGHT, ACCENT_ICON,
    FONT_MONO, FONT_UI,
)
from logic.db_service import Silo, get_all_silos, save_silo


# ── Строка силоса ─────────────────────────────────────────────────────────────

class _SiloRow(QWidget):
    def __init__(self, silo: Silo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.silo = silo
        self.setStyleSheet("background: transparent;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(8)

        # Номер — фиксированный, не редактируется
        num = QLabel(silo.number)
        num.setFixedWidth(30)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(
            f"color: {ACCENT_ICON}; background: rgba(108,92,231,0.1);"
            f"border: 0.5px solid rgba(108,92,231,0.2); border-radius: 5px;"
            f"font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 3px 0;"
        )
        lay.addWidget(num)

        # Поля редактирования
        self._crop_name  = self._inp(silo.crop_name,    110)
        self._crop_class = self._inp(silo.crop_class,    55)
        self._year       = self._inp(silo.harvest_year,  55)
        self._origin     = self._inp(silo.origin,        45)

        for w in (self._crop_name, self._crop_class, self._year, self._origin):
            lay.addWidget(w)

        lay.addStretch()

    def _inp(self, value: str, width: int) -> QLineEdit:
        inp = QLineEdit(value if value != "-" else "")
        inp.setPlaceholderText("—")
        inp.setFixedHeight(30)
        inp.setFixedWidth(width)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background: #111114; border: 0.5px solid {BORDER};
                border-radius: 5px; color: {TEXT_MAIN};
                font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 8px;
            }}
            QLineEdit:focus {{ border-color: rgba(108,92,231,0.5); color: {TEXT_BRIGHT}; }}
        """)
        return inp

    def collect(self) -> Silo:
        """Возвращает Silo с текущими значениями полей."""
        self.silo.crop_name    = self._crop_name.text().strip()  or "-"
        self.silo.crop_class   = self._crop_class.text().strip() or "-"
        self.silo.harvest_year = self._year.text().strip()       or "-"
        self.silo.origin       = self._origin.text().strip()     or "-"
        return self.silo


# ── Страница ──────────────────────────────────────────────────────────────────

class SilosPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Силоса",
            subtitle="",
            section="Настройки",
            actions=[("Сохранить", True)],
        )
        self._rows: list[_SiloRow] = []
        self._action_buttons["Сохранить"].clicked.connect(self._on_save)
        self._build_ui()

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        silos = get_all_silos()
        mid = (len(silos) + 1) // 2
        left_silos  = silos[:mid]
        right_silos = silos[mid:]

        # Ширина строки: margins(10+10) + №(30) + 4×spacing(8)
        # + Культура(110) + Класс(55) + Урожай(55) + Происх.(45) = 355px
        LEFT_COL_W = 355

        # Внешняя карточка-контейнер
        card = QFrame()
        card.setFixedWidth(LEFT_COL_W * 2 + 1 + 2)  # +2 под border карточки
        card.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
        )
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # Заголовок — две симметричные секции через разделитель
        hdr = QWidget()
        hdr.setObjectName("silosHdr")
        hdr.setStyleSheet(
            "QWidget#silosHdr {"
            f"background: rgba(108,92,231,0.05);"
            f"border-radius: 10px 10px 0 0; border-bottom: 0.5px solid {BORDER};"
            "}"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        def _hdr_labels() -> QWidget:
            sec = QWidget()
            sec.setStyleSheet("background: transparent;")
            sl = QHBoxLayout(sec)
            sl.setContentsMargins(10, 8, 10, 8)
            sl.setSpacing(8)
            for text, w in [("№", 30), ("Культура", 110), ("Класс", 55), ("Урожай", 55), ("Происх.", 45)]:
                lbl = QLabel(text)
                lbl.setFixedWidth(w)
                if text == "№":
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet(
                    f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                    "font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;"
                )
                sl.addWidget(lbl)
            sl.addStretch()
            return sec

        left_hdr = _hdr_labels()
        left_hdr.setFixedWidth(LEFT_COL_W)
        left_hdr.setStyleSheet("background: transparent; border: none;")
        right_hdr = _hdr_labels()
        right_hdr.setFixedWidth(LEFT_COL_W)

        hl.addWidget(left_hdr)
        hl.addWidget(right_hdr)
        hl.addStretch()
        card_lay.addWidget(hdr)

        # Тело — один скролл, внутри две колонки с разделителем
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(scroll_style())

        # Точная ширина: левая + разделитель + правая
        BODY_W = LEFT_COL_W * 2 + 1

        body = QWidget()
        body.setFixedWidth(BODY_W)
        body.setStyleSheet(f"background: {BG_CARD};")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 4, 0, 4)
        bl.setSpacing(0)

        self._rows.clear()

        for col_idx, col_silos in enumerate((left_silos, right_silos)):
            col_w = QWidget()
            col_w.setFixedWidth(LEFT_COL_W)
            if col_idx == 0:
                col_w.setStyleSheet(f"background: transparent; border-right: 0.5px solid {BORDER};")
            else:
                col_w.setStyleSheet("background: transparent;")
            col_lay = QVBoxLayout(col_w)
            col_lay.setContentsMargins(0, 0, 0, 0)
            col_lay.setSpacing(0)

            for i, silo in enumerate(col_silos):
                row = _SiloRow(silo)
                if i < len(col_silos) - 1:
                    row.setStyleSheet(
                        "background: transparent; border-bottom: 0.5px solid #1a1a1e;"
                    )
                col_lay.addWidget(row)
                self._rows.append(row)

            col_lay.addStretch()
            bl.addWidget(col_w)

        scroll.setWidget(body)
        card_lay.addWidget(scroll)

        # Центрирование карточки в content_layout
        center_row = QWidget()
        center_row.setStyleSheet("background: transparent;")
        cr_lay = QHBoxLayout(center_row)
        cr_lay.setContentsMargins(0, 0, 0, 0)
        cr_lay.setSpacing(0)
        cr_lay.addStretch()
        cr_lay.addWidget(card)
        cr_lay.addStretch()
        self._content_layout.addWidget(center_row)

    def _on_save(self) -> None:
        for row in self._rows:
            save_silo(row.collect())
        self._action_buttons["Сохранить"].flash_success()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Перезагружаем данные из БД без полного пересоздания виджетов
        silos = get_all_silos()
        silo_map = {s.id: s for s in silos}
        for row in self._rows:
            updated = silo_map.get(row.silo.id)
            if updated:
                row._crop_name.setText(updated.crop_name if updated.crop_name != "-" else "")
                row._crop_class.setText(updated.crop_class if updated.crop_class != "-" else "")
                row._year.setText(updated.harvest_year if updated.harvest_year != "-" else "")
                row._origin.setText(updated.origin if updated.origin != "-" else "")
