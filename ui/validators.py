"""
Динамическая валидация числовых полей ввода.
"""

from __future__ import annotations
import re
from typing import Optional

from PyQt6.QtWidgets import QLineEdit, QPushButton

from ui.theme import BORDER

_POSITIVE_NUMBER_RE = re.compile(r"^\d*[.,]?\d*$")

_ERROR_BORDER = "rgba(248,113,113,0.8)"

_TOOLTIP_ERROR     = "Допустимы только положительные числа (разделитель — точка или запятая)"
_TOOLTIP_INT_ERROR = "Допустимы только целые положительные числа"


def _is_valid(text: str, integer_only: bool = False) -> bool:
    """True если text допустим (или пуст)."""
    if not text:
        return True
    if integer_only:
        return text.isdigit()
    return bool(_POSITIVE_NUMBER_RE.match(text))


def _make_error_style(base_style: str) -> str:
    """
    Строит стиль ошибки из базового.
    Заменяет цвет рамки на красный и переопределяет :focus,
    чтобы красный цвет был виден даже когда поле в фокусе.
    """
    result = base_style.replace(
        f"border: 0.5px solid {BORDER}",
        f"border: 0.5px solid {_ERROR_BORDER}",
    )
    # Переопределяем border-color в :focus — иначе фиолетовый перекрывает красный
    result = result.replace(
        "border-color: rgba(108,92,231,0.5);",
        f"border-color: {_ERROR_BORDER};",
    )
    return result


def attach_numeric_validators(
    fields: list[tuple[QLineEdit, bool]],
    calc_btn: Optional[QPushButton] = None,
) -> None:
    """
    Подключает живую числовую валидацию к полям.

    fields   — список (QLineEdit, integer_only)
    calc_btn — кнопка, блокируется если хотя бы одно поле невалидно
    """
    # Сохраняем базовые стили ДО подключения (чтобы не захватить уже изменённый)
    base_styles: dict[QLineEdit, str] = {
        inp: inp.styleSheet() for inp, _ in fields
    }
    error_styles: dict[QLineEdit, str] = {
        inp: _make_error_style(base_styles[inp]) for inp, _ in fields
    }

    def _check_all() -> None:
        if calc_btn is None:
            return
        all_valid = all(
            _is_valid(inp.text(), integer_only=int_only)
            for inp, int_only in fields
        )
        calc_btn.setEnabled(all_valid)

    def _make_handler(field: QLineEdit, int_only: bool):
        base = base_styles[field]
        err  = error_styles[field]

        def _on_changed(text: str) -> None:
            valid = _is_valid(text, integer_only=int_only)
            field.setStyleSheet(base if valid else err)
            field.setToolTip(
                "" if valid else (_TOOLTIP_INT_ERROR if int_only else _TOOLTIP_ERROR)
            )
            _check_all()

        return _on_changed

    for inp, integer_only in fields:
        inp.textChanged.connect(_make_handler(inp, integer_only))
