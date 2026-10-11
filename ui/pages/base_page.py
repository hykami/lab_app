"""
Базовый класс страницы.

Структура страницы:
  ┌─ breadcrumb  ───────────────────────────────────┐
  ├─ page header (заголовок + кнопки действий) ─────┤
  └─ scroll area (контент) ─────────────────────────┘

Виджеты:
  ActionButton   — кнопка действия (первичная / вторичная)
  BasePage       — базовый класс всех страниц приложения
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from ui.theme import (
    BG, BG_CARD, BORDER, TEXT_BRIGHT,
    ACCENT_V, ACCENT_G, FONT_UI,
)


# ═════════════════════════════════════════════════════════════════
# ActionButton — кнопка действия
# ═════════════════════════════════════════════════════════════════

class ActionButton(QPushButton):
    def __init__(
        self,
        label: str,
        primary: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(label, parent)
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if primary:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(108,92,231,0.15);
                    border: 0.5px solid rgba(108,92,231,0.4);
                    border-radius: 7px;
                    color: {ACCENT_V};
                    font-family: '{FONT_UI}', sans-serif;
                    font-size: 12px;
                    letter-spacing: 2px;
                    padding: 0 16px;
                }}
                QPushButton:hover {{ background: rgba(108,92,231,0.22); }}
                QPushButton:pressed {{ background: rgba(108,92,231,0.30); }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {BG_CARD};
                    border: 0.5px solid {BORDER};
                    border-radius: 7px;
                    color: #555;
                    font-family: '{FONT_UI}', sans-serif;
                    font-size: 12px;
                    letter-spacing: 2px;
                    padding: 0 16px;
                }}
                QPushButton:hover {{ color: #888; border-color: #3a3a3e; }}
                QPushButton:pressed {{ background: #1c1c20; }}
            """)

    def flash_success(self, text: str = "✓ Сохранено", duration_ms: int = 1800) -> None:
        """Показывает зелёный тост успеха и восстанавливает исходный стиль."""
        self._flash(text, success=True, duration_ms=duration_ms)

    def flash_error(self, text: str = "✗ Ошибка", duration_ms: int = 1800) -> None:
        """Показывает красный тост ошибки и восстанавливает исходный стиль."""
        self._flash(text, success=False, duration_ms=duration_ms)

    def _flash(self, text: str, success: bool, duration_ms: int) -> None:
        from ui.theme import ACCENT_R
        orig_text  = self.text()
        orig_style = self.styleSheet()
        color      = ACCENT_G if success else ACCENT_R
        bg_active  = "rgba(74,222,128,0.12)"  if success else "rgba(248,113,113,0.12)"
        bg_border  = "rgba(74,222,128,0.4)"   if success else "rgba(248,113,113,0.4)"
        self.setText(text)
        self.setEnabled(False)
        self.setStyleSheet(orig_style
                           .replace(ACCENT_V, color)
                           .replace("rgba(108,92,231,0.15)", bg_active)
                           .replace("rgba(108,92,231,0.4)",  bg_border))
        QTimer.singleShot(duration_ms, lambda: (
            self.setText(orig_text),
            self.setStyleSheet(orig_style),
            self.setEnabled(True),
        ))


def flash_btn(btn: QPushButton, text: str, success: bool = True,
              duration_ms: int = 1800,
              restore_text: str | None = None) -> None:
    """
    Универсальный тост для любого QPushButton — не только ActionButton.
    Меняет текст и цвет рамки, затем восстанавливает исходное состояние.
    """
    from ui.theme import ACCENT_R
    orig_text  = btn.text()
    orig_style = btn.styleSheet()
    color      = ACCENT_G if success else ACCENT_R
    bg_c       = "rgba(74,222,128,0.12)"  if success else "rgba(248,113,113,0.12)"
    bd_c       = "rgba(74,222,128,0.4)"   if success else "rgba(248,113,113,0.4)"

    # Подменяем цвета любого стиля кнопки
    flash_style = orig_style
    for old_bg in ("rgba(74,222,128,0.12)", "rgba(108,92,231,0.15)", "transparent"):
        flash_style = flash_style.replace(old_bg, bg_c, 1)
    for old_bd in ("rgba(74,222,128,0.35)", "rgba(108,92,231,0.4)", BORDER):
        flash_style = flash_style.replace(old_bd, bd_c, 1)
    for old_col in ("#4ade80", "#a78bfa", "#707085", ACCENT_G):
        flash_style = flash_style.replace(old_col, color, 1)

    btn.setText(text)
    btn.setEnabled(False)
    btn.setStyleSheet(flash_style)
    QTimer.singleShot(duration_ms, lambda: (
        btn.setText(restore_text or orig_text),
        btn.setStyleSheet(orig_style),
        btn.setEnabled(True),
    ))


# ═════════════════════════════════════════════════════════════════
# 10. BasePage — базовый класс страницы
# ═════════════════════════════════════════════════════════════════

class BasePage(QWidget):
    """
    Базовый класс для всех страниц приложения.

    Параметры:
      title    — заголовок страницы
      subtitle — подзаголовок
      section  — раздел для хлебных крошек
      actions  — кнопки: [(текст, primary), ...]
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        section: str = "",
        actions: Optional[list[tuple[str, bool]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header(title, subtitle, actions or []))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG}; border: none; }}
            QScrollBar:vertical {{ background: {BG}; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{
                background: #4a4a58; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet(f"background: {BG};")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(22, 12, 22, 12)
        self._content_layout.setSpacing(8)
        self._content_layout.addStretch()

        scroll.setWidget(self._content_widget)
        root.addWidget(scroll, 1)

    def _build_breadcrumb(self, section: str, page: str) -> QWidget:
        bc = QWidget()
        bc.setFixedHeight(32)
        bc.setStyleSheet(f"background: {BG}; border-bottom: 0.5px solid #1a1a1e;")
        lay = QHBoxLayout(bc)
        lay.setContentsMargins(22, 0, 22, 0)
        lay.setSpacing(6)

        s = QLabel(section.upper())
        s.setStyleSheet(
            f"color: #333; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent;"
        )
        lay.addWidget(s)

        sep = QLabel("›")
        sep.setStyleSheet("color: #4a4a58; font-size: 11px; background: transparent;")
        lay.addWidget(sep)

        p = QLabel(page.upper())
        p.setStyleSheet(
            f"color: #555; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent;"
        )
        lay.addWidget(p)
        lay.addStretch()
        return bc

    def _build_header(
        self,
        title: str,
        subtitle: str,
        actions: list[tuple[str, bool]],
    ) -> QWidget:
        header = QWidget()
        # Граница снизу только если есть subtitle или section
        border = "border-bottom: 0.5px solid #1a1a1e;" if subtitle else ""
        header.setStyleSheet(f"background: {BG}; {border}")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(22, 14, 22, 14)
        lay.setSpacing(0)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setContentsMargins(0, 0, 0, 0)

        t = QLabel(title)
        t.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 18px; font-weight: 600; letter-spacing: -0.01em; background: transparent;"
        )
        text_col.addWidget(t)

        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(
                f"color: #484858; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent;"
            )
            text_col.addWidget(s)

        lay.addLayout(text_col)

        # Слот для произвольного виджета (например TypePillSwitcher)
        self._header_slot = QHBoxLayout()
        self._header_slot.setContentsMargins(16, 0, 0, 0)
        self._header_slot.setSpacing(0)
        lay.addLayout(self._header_slot)

        lay.addStretch(1)

        if actions:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            btn_row.setContentsMargins(0, 0, 0, 0)
            self._action_buttons: dict[str, ActionButton] = {}
            for label, primary in actions:
                btn = ActionButton(label, primary)
                btn_row.addWidget(btn)
                self._action_buttons[label] = btn
            lay.addLayout(btn_row)

        return header

    def set_header_widget(self, widget: QWidget) -> None:
        """Встраивает виджет (например TypePillSwitcher) в хедер рядом с заголовком."""
        while self._header_slot.count():
            item = self._header_slot.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._header_slot.addWidget(widget)
