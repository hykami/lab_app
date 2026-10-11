"""
Настройки → Очистить карточки.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.theme import (
    BG_CARD, BORDER, TEXT_MUTED,
    ACCENT_G, ACCENT_ICON, FONT_UI,
    FONT_UI,
)
from logic.db_service import delete_all_cards, get_all_cards


class ClearCardsPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Очистить карточки",
            subtitle="",
            section="Настройки",
            actions=[],
        )
        self._build_ui()

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 0.5px solid {BORDER};
                border-radius: 10px;
            }}
        """)
        card.setMaximumWidth(560)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 20)
        cl.setSpacing(12)

        # ── Статистика ────────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        stats_row.setContentsMargins(0, 0, 0, 0)

        self._stat_count = self._stat_cell("КАРТОЧЕК", "0", colored=True)
        self._stat_cultures = self._stat_cell("КУЛЬТУР", "0")
        self._stat_last = self._stat_cell("ПОСЛЕДНЯЯ", "—")

        stats_row.addWidget(self._stat_count)
        stats_row.addWidget(self._stat_cultures)
        stats_row.addWidget(self._stat_last)

        stats_w = QWidget(); stats_w.setStyleSheet("background: transparent;")
        stats_w.setLayout(stats_row)
        cl.addWidget(stats_w)

        # ── Подтверждение ─────────────────────────────────────────────────────
        confirm = QWidget()
        confirm.setStyleSheet(
            "background: rgba(248,113,113,0.04);"
            "border: 0.5px solid rgba(248,113,113,0.15);"
            "border-radius: 8px;"
        )
        conf_lay = QHBoxLayout(confirm)
        conf_lay.setContentsMargins(14, 10, 10, 10)
        conf_lay.setSpacing(12)

        self._confirm_lbl = QLabel("Нет карточек для удаления.")
        self._confirm_lbl.setWordWrap(True)
        self._confirm_lbl.setStyleSheet(
            "color: rgba(248,113,113,0.5); font-family: '"
            f"{FONT_UI}', sans-serif; font-size: 12px;"
            "background: transparent; border: none; line-height: 1.5;"
        )
        conf_lay.addWidget(self._confirm_lbl, 1)

        self._btn = QPushButton("Удалить все")
        self._btn.setFixedHeight(34)
        self._btn.setFixedWidth(120)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(248,113,113,0.1);
                border: 0.5px solid rgba(248,113,113,0.4);
                border-radius: 7px;
                color: #f87171;
                font-family: '{FONT_UI}', sans-serif;
                font-size: 12px;
                letter-spacing: 0.04em;
            }}
            QPushButton:hover {{ background: rgba(248,113,113,0.18); }}
            QPushButton:disabled {{ opacity: 0.3; }}
        """)
        self._btn.clicked.connect(self._on_clear)
        conf_lay.addWidget(self._btn)

        cl.addWidget(confirm)

        self._content_layout.addWidget(card)
        self._content_layout.addStretch()

        self._refresh()

    def _stat_cell(self, label: str, value: str, colored: bool = False) -> QFrame:
        cell = QFrame()
        cell.setStyleSheet(
            "QFrame { background: #111114; border: 0.5px solid #1e1e22; border-radius: 8px; }"
        )
        lay = QVBoxLayout(cell)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(3)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        lay.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(
            f"color: {ACCENT_ICON if colored else TEXT_MUTED};"
            f"font-family: '{FONT_UI}', sans-serif;"
            "font-size: 22px; font-weight: 300; background: transparent; border: none;"
        )
        lay.addWidget(val)

        # Храним ссылку на QLabel значения для обновления
        cell._value_lbl = val
        return cell

    def _refresh(self) -> None:
        cards = get_all_cards()
        count = len(cards)

        # Статистика
        self._stat_count._value_lbl.setText(str(count))

        cultures = len({c.culture_name for c in cards})
        self._stat_cultures._value_lbl.setText(str(cultures))

        if cards:
            last = sorted(cards, key=lambda c: c.created_at or "")[-1]
            date_str = (last.created_at or "")[:10]
            self._stat_last._value_lbl.setText(date_str or "—")
        else:
            self._stat_last._value_lbl.setText("—")

        # Кнопка и текст
        if count == 0:
            self._confirm_lbl.setText("Нет карточек для удаления.")
            self._btn.setEnabled(False)
        else:
            noun = "карточку" if count == 1 else ("карточки" if 2 <= count <= 4 else "карточек")
            self._confirm_lbl.setText(
                f"Удалить все {count} {noun}? Действие необратимо — восстановление невозможно."
            )
            self._btn.setEnabled(True)

    def _on_clear(self) -> None:
        deleted = delete_all_cards()
        self._refresh()

        self._btn.setEnabled(False)
        self._btn.setText(f"✓ {deleted} удалено")
        self._btn.setStyleSheet(self._btn.styleSheet()
            .replace("rgba(248,113,113,0.1)", "rgba(74,222,128,0.08)")
            .replace("rgba(248,113,113,0.4)", "rgba(74,222,128,0.3)")
            .replace("rgba(248,113,113,0.18)", "rgba(74,222,128,0.12)")
            .replace("#f87171", ACCENT_G)
        )
        QTimer.singleShot(3000, lambda: (
            self._btn.setText("Удалить все"),
            self._btn.setStyleSheet(self._btn.styleSheet()
                .replace("rgba(74,222,128,0.08)", "rgba(248,113,113,0.1)")
                .replace("rgba(74,222,128,0.3)", "rgba(248,113,113,0.4)")
                .replace("rgba(74,222,128,0.12)", "rgba(248,113,113,0.18)")
                .replace(ACCENT_G, "#f87171")
            ),
        ))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh()
