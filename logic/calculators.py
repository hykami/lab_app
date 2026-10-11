"""
Логика калькуляторов (Журналы).
Все вычисления здесь — UI-файлы только вызывают эти функции.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# ── Влажность ─────────────────────────────────────────────────────────────────

NAVISKA_G = 5.0  # масса навески, г


@dataclass
class BoxResult:
    """Результат расчёта для одной бюксы."""
    box_number: str       # номер бюксы
    m:  float             # масса пустой бюксы
    m1: float             # масса бюксы + навеска до сушки
    m2: float             # масса бюксы + навеска после сушки (расчётная)
    w:  float             # влажность для этой бюксы


@dataclass
class HumidityResult:
    """Итоговый результат расчёта влажности."""
    w_input:  float           # введённая пользователем влажность
    is_odd:   bool            # нечётная (дробная в 0.1)?
    box1:     BoxResult
    box2:     BoxResult
    w_avg:    float           # среднее — равно w_input (для наглядности)


def _is_odd_humidity(w: float) -> bool:
    """
    Нечётная влажность — у которой первый знак после запятой нечётный.
    Например: 12.7 → True (7 нечётное), 12.6 → False (6 чётное).
    """
    first_decimal = round(w * 10) % 10
    return first_decimal % 2 != 0


def _check_finite_nonneg(name: str, val: float) -> None:
    """Проверяет что значение конечно и неотрицательно. Иначе ValueError."""
    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"{name}: некорректное значение ({val})")
    if val < 0:
        raise ValueError(f"{name}: не может быть отрицательным: {val}")


def calc_humidity(w_input: float, box1_number: str, box1_mass: float,
                  box2_number: str, box2_mass: float) -> HumidityResult:
    """
    Рассчитывает m2 для двух бюкс.

    Формула:  W = (m1 - m2) * 100 / (m1 - m)
    Обратная: m2 = m1 - W * (m1 - m) / 100

    Параметры:
        w_input      — влажность введённая пользователем
        box1_number  — номер первой бюксы
        box1_mass    — масса пустой первой бюксы (из БД)
        box2_number  — номер второй бюксы
        box2_mass    — масса пустой второй бюксы (из БД)

    Raises:
        ValueError: если w_input или массы некорректны (NaN, inf, отрицательные).
    """
    _check_finite_nonneg("w_input", w_input)
    _check_finite_nonneg("box1_mass", box1_mass)
    _check_finite_nonneg("box2_mass", box2_mass)

    is_odd = _is_odd_humidity(w_input)
    if is_odd:
        # Нечётная: одна бюкса -0.1, вторая +0.1
        w1 = round(w_input - 0.1, 4)
        w2 = round(w_input + 0.1, 4)
    else:
        # Чётная: обе бюксы с одним значением
        w1 = w2 = w_input

    def _calc_box(number: str, m: float, w: float) -> BoxResult:
        m1 = round(m + NAVISKA_G, 4)
        m2 = round(m1 - w * (m1 - m) / 100, 4)
        return BoxResult(box_number=number, m=m, m1=m1, m2=m2, w=w)

    return HumidityResult(
        w_input=w_input,
        is_odd=is_odd,
        box1=_calc_box(box1_number, box1_mass, w1),
        box2=_calc_box(box2_number, box2_mass, w2),
        w_avg=w_input,
    )


# Расчёты числа падения и клейковины находятся в отдельных модулях:
# logic/fall_number_calc.py — calc_fall_number()
# logic/gluten_calc.py      — calc_gluten()
