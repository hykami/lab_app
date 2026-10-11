"""
Общие вспомогательные функции для расчётов.
Используются в card_calc.py и incoming_control.py.
"""

from __future__ import annotations
import random

# Единица квантования: все значения примесей кратны этому шагу
UNIT: float = 0.02


def _balance_units(parts: list[int], diff: int, indices: list[int]) -> None:
    """
    Выравнивает сумму parts на величину diff, изменяя элементы в порядке indices.
    diff > 0 — добавляем единицы к «весомым» индексам.
    diff < 0 — снимаем единицы (защита от зацикливания при parts == 0).
    Изменяет parts на месте.
    """
    n = len(parts)
    if n == 0 or diff == 0:
        return

    if diff > 0:
        i = 0
        while diff > 0:
            parts[indices[i % n]] += 1
            diff -= 1
            i += 1
        return

    # diff < 0: снимаем дефицит, прерываем цикл если за полный круг
    # не удалось ничего снять (все parts == 0)
    attempts_without_progress = 0
    i = 0
    while diff < 0 and attempts_without_progress < n:
        idx = indices[i % n]
        if parts[idx] > 0:
            parts[idx] -= 1
            diff += 1
            attempts_without_progress = 0
        else:
            attempts_without_progress += 1
        i += 1


def split_weighted_even(total: float, weights: list[float]) -> list[float]:
    """
    Делит total на len(weights) частей пропорционально весам.
    Все значения чётные (кратны UNIT). Сумма точно равна total.

    Защиты:
    - Пустой список весов → [].
    - Все веса == 0 или сумма весов <= 0 → равномерное распределение.
    - Total <= 0 или total < UNIT → нули.
    - Гарантия отсутствия зацикливания при балансировке.
    """
    n = len(weights)
    if n == 0:
        return []
    if total <= 0:
        return [0.0] * n

    total_units = round(total / UNIT)
    if total_units == 0:
        return [0.0] * n

    # Нормировка весов (защита от нулевой/отрицательной суммы)
    weights_sum = sum(weights)
    if weights_sum <= 0:
        weights = [1.0] * n
        weights_sum = float(n)

    # Распределение пропорционально весам с округлением до целых единиц
    raw = [w / weights_sum * total_units for w in weights]
    parts = [max(0, round(r)) for r in raw]

    # Балансировка суммы: добавляем/снимаем единицы у «весомых» индексов
    indices = sorted(range(n), key=lambda i: -weights[i])
    _balance_units(parts, total_units - sum(parts), indices)

    # Лёгкое перемешивание для естественности значений
    if n >= 2:
        for _ in range(min(total_units // 4, 5)):
            a, b = random.sample(range(n), 2)
            if parts[a] > 0:
                parts[a] -= 1
                parts[b] += 1

    return [round(p * UNIT, 2) for p in parts]


# Культуры с особым правилом расчёта граммов «Битых»
_WHEAT_BROKEN_AS_PERCENT = frozenset({"Пшеница 3 кл.", "Пшеница 4 кл."})
_CORN = "Кукуруза"


def calc_grams(name: str, percent: float, naveski: float,
               culture_name: str) -> float:
    """
    Расчёт граммов примеси.
    Специальные правила для «Битых»:
      - Пшеница 3/4 кл.: граммы = %
      - Кукуруза: граммы = % * 2
    Для остальных случаев: граммы = % * naveski / 100.
    """
    if name == "Битые":
        if culture_name in _WHEAT_BROKEN_AS_PERCENT:
            return round(percent, 2)
        if culture_name == _CORN:
            return round(percent * 2, 2)
    return round(percent * naveski / 100, 2)
