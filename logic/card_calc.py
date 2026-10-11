"""
Логика генерации карточки зерна.

Алгоритм распределения примесей (v3 — плавающие веса):

СП: Органика > Дикие > Проход > Испорченные
  Центры из примера: Органика≈42%, Дикие≈30%, Проход≈19%, Испорченные≈9%
  Каждый вес гуляет в диапазоне ±6% от центра.

ЗП: Битые > Другие > Щуплые > Поврежденные
  Центры из примера: Битые≈43%, Другие≈26%, Щуплые≈22%, Поврежденные≈9%
  Аналогично.

При каждой генерации случайно смещаем веса в допустимых диапазонах,
затем нормируем к 1.0 и применяем к total.
Квантование к 0.02 сохраняет чётность значений.
"""

from __future__ import annotations
import random
from dataclasses import dataclass

from logic.calc_utils import UNIT, _balance_units, calc_grams


# ── Списки примесей ───────────────────────────────────────────────────────────

SP_IMPURITIES      = ["Проход", "Органика", "Дикие", "Испорченные"]
ZP_IMPURITIES      = ["Битые", "Щуплые", "Поврежденные", "Другие"]

SP_IMPURITIES_CORN = ["Проход", "Органика", "Испорченные"]
ZP_IMPURITIES_CORN = ["Битые", "Щуплые", "Поврежденные"]

# Второй ряд — дополнительные примеси (compact)
SP_IMPURITIES_ROW2      = ["Крупная СП", "Минеральная", "Выеденные", "Фузариозные"]
ZP_IMPURITIES_ROW2      = ["Давленные", "Проросшие", "Изъеденные", "Зелёные"]

SP_IMPURITIES_CORN_ROW2 = ["Крупная СП", "Минеральная", "Выеденные", "Фузариозные"]
ZP_IMPURITIES_CORN_ROW2 = ["Давленные", "Проросшие", "Изъеденные", "Зелёные"]

CORN_CULTURES = {"Кукуруза"}


# ── Плавающие весовые диапазоны ───────────────────────────────────────────────
#
# Формат: имя → (min_weight, max_weight)
# Центральные значения выведены из примера, диапазон ±6-8%
# Порядок важности: Органика > Дикие > Проход > Испорченные
#                   Битые > Другие > Щуплые > Поврежденные

SP_RANGES = {
    "Проход":      (0.13, 0.26),   # центр ≈ 19%
    "Органика":    (0.36, 0.50),   # центр ≈ 42%, самая большая
    "Дикие":       (0.24, 0.38),   # центр ≈ 30%
    "Испорченные": (0.05, 0.13),   # центр ≈ 9%, самая маленькая
}

ZP_RANGES = {
    "Битые":       (0.37, 0.51),   # центр ≈ 43%, самая большая
    "Щуплые":      (0.15, 0.22),   # центр ≈ 22%  — сужен чтобы всегда < Других
    "Поврежденные":(0.05, 0.12),   # центр ≈ 9%,  самая маленькая
    "Другие":      (0.23, 0.33),   # центр ≈ 26% — всегда > Щуплых
}

# Кукуруза — без Диких (СП) и без Других (ЗП)
# Перераспределяем их доли между оставшимися
SP_RANGES_CORN = {
    "Проход":      (0.18, 0.32),   # немного больше без Диких
    "Органика":    (0.44, 0.60),   # основная доля
    "Испорченные": (0.10, 0.22),
}

ZP_RANGES_CORN = {
    "Битые":       (0.42, 0.56),
    "Щуплые":      (0.22, 0.36),
    "Поврежденные":(0.10, 0.24),
}


@dataclass
class ImpurityEntry:
    name:    str
    percent: float
    grams:   float


@dataclass
class CardResult:
    culture_name: str
    naveski:      float
    sp_total:     float
    zp_total:     float
    sp_items:     list[ImpurityEntry]
    zp_items:     list[ImpurityEntry]


# ── Алгоритм распределения ────────────────────────────────────────────────────

def _enforce_order(weights: list[float], names: list[str],
                   order: list[str]) -> list[float]:
    """
    Гарантирует убывающий порядок (несколько проходов как bubble sort).
    """
    idx = {n: i for i, n in enumerate(names)}
    result = list(weights)
    for _ in range(len(order)):  # max len(order) проходов гарантируют сортировку
        changed = False
        for i in range(len(order) - 1):
            a, b = order[i], order[i + 1]
            if a in idx and b in idx:
                ia, ib = idx[a], idx[b]
                if result[ia] < result[ib]:
                    result[ia], result[ib] = result[ib], result[ia]
                    changed = True
        if not changed:
            break
    return result


def _split_with_ranges(
    total: float,
    names: list[str],
    ranges: dict[str, tuple[float, float]],
    desired_order: list[str] | None = None,
) -> list[float]:
    """
    Распределяет total по примесям используя плавающие весовые диапазоны.

    1. Для каждой примеси случайно выбираем вес из [min, max].
    2. Нормируем веса чтобы их сумма = 1.0.
    3. Применяем _enforce_order если передан desired_order.
    4. Умножаем на total, квантуем к UNIT.
    5. Выравниваем сумму до total.
    """
    n = len(names)
    if n == 0:
        return []
    if total <= 0:
        return [0.0] * n

    total_units = round(total / UNIT)
    if total_units == 0:
        return [0.0] * n

    # 1. Случайные веса из диапазонов
    weights = [random.uniform(*ranges.get(name, (0.1, 0.3))) for name in names]

    # 2. Нормируем к 1.0 (защита от нулевой суммы)
    w_sum = sum(weights)
    if w_sum <= 0:
        weights = [1.0 / n] * n
    else:
        weights = [w / w_sum for w in weights]

    # 3. Гарантируем желаемый порядок
    if desired_order:
        weights = _enforce_order(weights, names, desired_order)

    # 4. Переводим в единицы UNIT и квантуем
    raw_units = [max(0, round(w * total_units)) for w in weights]

    # Балансируем сумму у примесей с наибольшим весом (они менее заметны)
    order = sorted(range(n), key=lambda i: -weights[i])
    _balance_units(raw_units, total_units - sum(raw_units), order)

    # 5. Применяем порядок к финальным квантованным значениям
    if desired_order:
        raw_units = _enforce_order(raw_units, names, desired_order)

    return [round(u * UNIT, 2) for u in raw_units]


def generate_card(
    culture_name: str,
    naveski: float,
    sp_total: float,
    zp_total: float,
) -> CardResult:
    """
    Генерирует случайные значения примесей для карточки зерна.
    Распределение использует плавающие весовые диапазоны (см. _split_with_ranges).
    Для Кукурузы исключаются «Дикие» (СП) и «Другие» (ЗП).
    """
    is_corn = culture_name in CORN_CULTURES

    sp_names  = SP_IMPURITIES_CORN if is_corn else SP_IMPURITIES
    zp_names  = ZP_IMPURITIES_CORN if is_corn else ZP_IMPURITIES
    sp_ranges = SP_RANGES_CORN     if is_corn else SP_RANGES
    zp_ranges = ZP_RANGES_CORN     if is_corn else ZP_RANGES

    # Желаемый порядок убывания
    SP_ORDER      = ["Органика", "Дикие", "Проход", "Испорченные"]
    ZP_ORDER      = ["Битые", "Другие", "Щуплые", "Поврежденные"]
    SP_ORDER_CORN = ["Органика", "Проход", "Испорченные"]
    ZP_ORDER_CORN = ["Битые", "Щуплые", "Поврежденные"]

    sp_order = SP_ORDER_CORN if is_corn else SP_ORDER
    zp_order = ZP_ORDER_CORN if is_corn else ZP_ORDER

    sp_parts = _split_with_ranges(sp_total, sp_names, sp_ranges, sp_order)
    zp_parts = _split_with_ranges(zp_total, zp_names, zp_ranges, zp_order)

    sp_items = [
        ImpurityEntry(name=name, percent=pct,
                      grams=round(pct * naveski / 100, 2))
        for name, pct in zip(sp_names, sp_parts)
    ]
    zp_items = [
        ImpurityEntry(name=name, percent=pct,
                      grams=calc_grams(name, pct, naveski, culture_name))
        for name, pct in zip(zp_names, zp_parts)
    ]

    return CardResult(
        culture_name=culture_name, naveski=naveski,
        sp_total=sp_total, zp_total=zp_total,
        sp_items=sp_items, zp_items=zp_items,
    )
