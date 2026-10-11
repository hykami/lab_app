"""
Фабричные функции для повторяющихся QSS-стилей.
Используйте их вместо inline-строк setStyleSheet.
"""

from __future__ import annotations
from PyQt6.QtCore import Qt
from ui.theme import (
    BG, BG_CARD, BORDER,
    TEXT_MAIN, TEXT_BRIGHT, ACCENT_G,
    FONT_MONO, FONT_UI,
)


def apply_combo_popup_style(combo, font_size: int = 13) -> None:
    """
    Применяет скруглённый стиль к popup-окну QComboBox.
    Вызывать сразу после создания combo.
    Qt не позволяет скруглить системную рамку popup через CSS —
    поэтому убираем рамку у view и задаём border-radius через stylesheet.
    """
    view = combo.view()
    view.window().setWindowFlags(
        Qt.WindowType.Popup |
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.NoDropShadowWindowHint
    )
    view.setStyleSheet(f"""
        QListView {{
            background: #18181c;
            border: 0.5px solid {BORDER};
            border-radius: 8px;
            selection-background-color: rgba(108,92,231,0.15);
            color: {TEXT_MAIN};
            font-family: '{FONT_UI}', sans-serif;
            font-size: {font_size}px;
            padding: 4px;
            outline: none;
        }}
        QListView::item {{
            border-radius: 5px;
            padding: 3px 8px;
            min-height: 24px;
        }}
        QListView::item:selected {{
            background: rgba(108,92,231,0.18);
            color: #c8bfff;
        }}
        QListView::item:hover:!selected {{
            background: rgba(108,92,231,0.08);
        }}
    """)


# ── Карточки / фреймы ─────────────────────────────────────────────────────────

def card_style(radius: int = 10, hover: bool = False) -> str:
    base = (
        f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; "
        f"border-radius: {radius}px; }}"
    )
    if hover:
        base += " QFrame:hover { border-color: #5a5a72; }"
    return base


# ── Поля ввода ────────────────────────────────────────────────────────────────

def input_style(
    height: int = 36,
    font_size: int = 14,
    radius: int = 7,
    bg: str = BG_CARD,
    focus_color: str = "rgba(108,92,231,0.5)",
) -> str:
    return f"""
        QLineEdit {{
            background: {bg};
            border: 0.5px solid {BORDER};
            border-radius: {radius}px;
            color: {TEXT_MAIN};
            font-family: '{FONT_MONO}', monospace;
            font-size: {font_size}px;
            padding: 0 12px;
        }}
        QLineEdit:focus {{
            border-color: {focus_color};
            color: {TEXT_BRIGHT};
        }}
    """


def compact_input_style(font_size: int = 13, radius: int = 6) -> str:
    """Тёмный input (#111114) — используется внутри карточек."""
    return f"""
        QLineEdit {{
            background: #111114;
            border: 0.5px solid {BORDER};
            border-radius: {radius}px;
            color: {TEXT_MAIN};
            font-family: '{FONT_MONO}', monospace;
            font-size: {font_size}px;
            padding: 0 10px;
        }}
        QLineEdit:focus {{ border-color: rgba(108,92,231,0.5); }}
    """


def result_input_style() -> str:
    """Зелёный input — для отображения результатов расчёта."""
    return f"""
        QLineEdit {{
            background: rgba(74,222,128,0.08);
            border: 0.5px solid rgba(74,222,128,0.3);
            border-radius: 6px;
            color: {ACCENT_G};
            font-family: '{FONT_MONO}', monospace;
            font-size: 14px;
            font-weight: 300;
            padding: 0 10px;
        }}
        QLineEdit:focus {{ border-color: rgba(74,222,128,0.6); }}
    """


# ── Выпадающие списки ─────────────────────────────────────────────────────────

def combo_style(font_size: int = 13, min_width: int = 0) -> str:
    mw = f"min-width: {min_width}px;" if min_width else ""
    return f"""
        QComboBox {{
            background: {BG_CARD};
            border: 0.5px solid {BORDER};
            border-radius: 7px;
            color: {TEXT_MAIN};
            font-family: '{FONT_UI}', sans-serif;
            font-size: {font_size}px;
            padding: 0 32px 0 10px;
            {mw}
        }}
        QComboBox:focus {{ border-color: rgba(108,92,231,0.5); }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: right center;
            width: 28px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            width: 0; height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #666;
            border-bottom: none;
        }}
        QComboBox::down-arrow:on {{
            border-top: none;
            border-bottom: 5px solid #888;
        }}
        QComboBox QAbstractItemView {{
            background: #18181c;
            border: 0.5px solid {BORDER};
            border-radius: 8px;
            selection-background-color: rgba(108,92,231,0.15);
            color: {TEXT_MAIN};
            font-family: '{FONT_UI}', sans-serif;
            font-size: {font_size}px;
            padding: 4px;
            outline: none;
        }}
    """


# ── Скролл-области ────────────────────────────────────────────────────────────

def scroll_style(border_right: bool = False, border_left: bool = False) -> str:
    border = ""
    if border_right:
        border = f"border-right: 0.5px solid {BORDER};"
    elif border_left:
        border = f"border-left: 0.5px solid {BORDER};"
    return f"""
        QScrollArea {{ background: {BG}; border: none; {border} }}
        QScrollBar:vertical {{ background: {BG}; width: 6px; }}
        QScrollBar::handle:vertical {{
            background: #4a4a58; border-radius: 3px; min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{ height: 0; }}
    """


# ── Метки ─────────────────────────────────────────────────────────────────────

def label_muted_style(font_size: int = 13) -> str:
    return (
        f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif; "
        f"font-size: {font_size}px; background: transparent; border: none;"
    )


def label_field_style(font_size: int = 10) -> str:
    """Метка над полем ввода."""
    return (
        f"color: #707085; font-family: '{FONT_UI}', sans-serif; "
        f"font-size: {font_size}px; font-weight: 500; background: transparent; border: none;"
    )
