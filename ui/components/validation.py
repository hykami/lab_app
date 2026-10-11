"""
Общая логика живой валидации полей ввода.
Используется на странице Создать (ParamsBlock) и при редактировании карточки (CardDetailPanel).

Правила подсветки:
  - Пустое поле              → базовый стиль (без изменений)
  - Валидное значение        → базовый стиль (без изменений, не выделяем зелёным)
  - Невалидное / нечисловое  → красная рамка, фон без изменений
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import QLineEdit

from ui.theme import BORDER, FONT_MONO, TEXT_BRIGHT


# ── Стили ─────────────────────────────────────────────────────────────────────

def _base_style(bg: str, font_size: int, radius: int) -> str:
    return (
        f"QLineEdit {{"
        f" background: {bg}; border: 0.5px solid {BORDER};"
        f" border-radius: {radius}px; color: {TEXT_BRIGHT};"
        f" font-family: '{FONT_MONO}', monospace; font-size: {font_size}px; padding: 0 8px; }}"
        " QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
    )


def _error_style(bg: str, font_size: int, radius: int) -> str:
    return (
        f"QLineEdit {{"
        f" background: {bg}; border: 0.5px solid rgba(248,113,113,0.7);"
        f" border-radius: {radius}px; color: {TEXT_BRIGHT};"
        f" font-family: '{FONT_MONO}', monospace; font-size: {font_size}px; padding: 0 8px; }}"
        " QLineEdit:focus { border-color: rgba(248,113,113,0.9); }"
    )


def _imp_base_style() -> str:
    return (
        f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
        f" border-radius: 5px; color: #c0c0c8;"
        f" font-family: '{FONT_MONO}', monospace; font-size: 11px; padding: 0 5px; }}"
        " QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
    )


def _imp_error_style() -> str:
    return (
        "QLineEdit { background: #111114; border: 0.5px solid rgba(248,113,113,0.6);"
        f" border-radius: 5px; color: #c0c0c8;"
        f" font-family: '{FONT_MONO}', monospace; font-size: 11px; padding: 0 5px; }}"
        " QLineEdit:focus { border-color: rgba(248,113,113,0.8); }"
    )


def _total_base_style(txt_col: str) -> str:
    return (
        f"QLineEdit {{ background: #111114; border: 0.5px solid {BORDER};"
        f" border-radius: 5px; color: #c0c0c8;"
        f" font-family: '{FONT_MONO}', monospace; font-size: 11px; padding: 0 5px; }}"
        " QLineEdit:focus { border-color: rgba(108,92,231,0.5); }"
    )


def _total_error_style(txt_col: str) -> str:
    return (
        "QLineEdit { background: #111114; border: 0.5px solid rgba(248,113,113,0.6);"
        f" border-radius: 5px; color: #c0c0c8;"
        f" font-family: '{FONT_MONO}', monospace; font-size: 11px; padding: 0 5px; }}"
        " QLineEdit:focus { border-color: rgba(248,113,113,0.8); }"
    )


# ── Публичные функции ─────────────────────────────────────────────────────────

def apply_param_validation(
    key: str,
    inp: QLineEdit,
    culture_obj: object,
    bg: str = "#111114",
    font_size: int = 13,
    radius: int = 6,
) -> None:
    """
    Живая валидация поля показателя (Влажность, Натура, Клейковина и т.д.).
    Вызывать из textEdited.
    """
    from logic.card_params import get_range

    text = inp.text().strip().replace(",", ".")
    if not text:
        inp.setStyleSheet(_base_style(bg, font_size, radius))
        return

    try:
        val = float(text)
    except ValueError:
        inp.setStyleSheet(_error_style(bg, font_size, radius))
        return

    lo, hi = get_range(key, culture_obj)
    if lo <= val <= hi:
        inp.setStyleSheet(_base_style(bg, font_size, radius))
    else:
        inp.setStyleSheet(_error_style(bg, font_size, radius))


def apply_imp_pct_validation(
    inp: QLineEdit,
    norm_min: float = 0.0,
    norm_max: float = 100.0,
) -> None:
    """
    Живая валидация поля % отдельной примеси.
    Проверяет кратность 0.02 и диапазон нормы примеси из БД.
    Вызывать из textEdited.
    """
    text = inp.text().strip().replace(",", ".")
    if not text:
        inp.setStyleSheet(_imp_base_style())
        return
    try:
        val = float(text)
    except ValueError:
        inp.setStyleSheet(_imp_error_style())
        return

    # Кратность 0.02 (как на странице Создать)
    if abs(round(val / 0.02) * 0.02 - val) > 1e-9:
        inp.setStyleSheet(_imp_error_style())
        return

    # Диапазон нормы примеси
    if norm_min > 0 and val < norm_min:
        inp.setStyleSheet(_imp_error_style())
        return
    if norm_max > 0 and val > norm_max:
        inp.setStyleSheet(_imp_error_style())
        return

    inp.setStyleSheet(_imp_base_style())


def apply_imp_total_validation(
    inp: QLineEdit,
    group: str,
    culture_obj: object,
) -> None:
    """
    Живая валидация итогового поля СП или ЗП.
    Вызывать из textEdited.
    """
    from logic.card_params import get_range

    txt_col = "#f87171" if group == "СП" else "#6c5ce7"
    key = "sp" if group == "СП" else "zp"
    lo, hi = get_range(key, culture_obj)

    text = inp.text().strip().replace(",", ".")
    if not text:
        inp.setStyleSheet(_total_base_style(txt_col))
        return
    try:
        val = float(text)
        ok = lo <= val <= hi
    except ValueError:
        ok = False

    inp.setStyleSheet(_total_base_style(txt_col) if ok else _total_error_style(txt_col))


def make_param_validator(key: str, inp: QLineEdit, culture_obj: object,
                         bg: str = "#111114", font_size: int = 13,
                         radius: int = 6):
    """Возвращает функцию-слот для подключения к textEdited."""
    def _validate(text: str) -> None:
        apply_param_validation(key, inp, culture_obj, bg, font_size, radius)
    return _validate


def make_imp_pct_validator(inp: QLineEdit,
                            norm_min: float = 0.0,
                            norm_max: float = 100.0):
    """Возвращает функцию-слот для подключения к textEdited."""
    def _validate(text: str) -> None:
        apply_imp_pct_validation(inp, norm_min, norm_max)
    return _validate


def make_imp_total_validator(inp: QLineEdit, group: str, culture_obj: object):
    """Возвращает функцию-слот для подключения к textEdited."""
    def _validate(text: str) -> None:
        apply_imp_total_validation(inp, group, culture_obj)
    return _validate
