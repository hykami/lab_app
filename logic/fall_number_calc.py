"""
Калькулятор числа падения.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


# ── Таблица масс навески (Таблица 1) ──────────────────────────────────────────
# (влажность_мин, влажность_макс, масса_навески)

NAVESKI_TABLE = [
    (9.0,  9.1,  6.40),
    (9.2,  9.6,  6.45),
    (9.7,  10.1, 6.50),
    (10.2, 10.6, 6.55),
    (10.7, 11.3, 6.60),
    (11.4, 11.6, 6.65),
    (11.7, 12.3, 6.70),
    (12.4, 12.6, 6.75),
    (12.7, 13.3, 6.80),
    (13.4, 13.6, 6.85),
    (13.7, 14.3, 6.90),
    (14.4, 14.6, 6.95),
    (14.7, 15.3, 7.00),
    (15.4, 15.6, 7.05),
    (15.7, 16.1, 7.10),
    (16.2, 16.6, 7.15),
    (16.7, 17.1, 7.20),
    (17.2, 17.4, 7.25),
    (17.5, 18.0, 7.30),
]


def get_naveski(humidity: float) -> float | None:
    """
    Возвращает массу навески по влажности из таблицы.
    None если влажность вне диапазона таблицы или некорректна (NaN, inf, отрицательная).
    """
    try:
        h = float(humidity)
    except (TypeError, ValueError):
        return None
    if math.isnan(h) or math.isinf(h) or h < 0:
        return None

    for w_min, w_max, naveski in NAVESKI_TABLE:
        # Используем округление чтобы избежать float сравнений
        if round(w_min, 1) <= round(h, 1) <= round(w_max, 1):
            return naveski
    return None


def random_even_divergence() -> int:
    """Случайное чётное целое число от 2 до 14."""
    return random.choice(range(2, 15, 2))


@dataclass
class FallNumberResult:
    humidity:     float          # введённая влажность
    fall_number:  float          # введённое ЧП
    naveski:      float | None   # масса навески по таблице
    divergence:   float          # случайное расхождение
    fp1:          float          # ЧП - расхождение / 2
    fp2:          float          # ЧП + расхождение / 2


def calc_fall_number(humidity: float, fall_number: float) -> FallNumberResult:
    """
    Рассчитывает два значения ЧП на основе случайного расхождения.
    """
    naveski = get_naveski(humidity)
    div     = random_even_divergence()
    half    = div / 2

    return FallNumberResult(
        humidity=humidity,
        fall_number=fall_number,
        naveski=naveski,
        divergence=div,
        fp1=round(fall_number - half, 1),
        fp2=round(fall_number + half, 1),
    )
