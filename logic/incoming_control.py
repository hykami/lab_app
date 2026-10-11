"""
Входной контроль — добавление допускаемого расхождения к СП и ЗП.
"""

from __future__ import annotations
from dataclasses import dataclass
from logic.card_calc import ImpurityEntry
from logic.calc_utils import split_weighted_even, calc_grams

_TABLE: list[tuple[float, float]] = [
    (0.5,  0.2), (1.0,  0.4), (2.0,  0.6), (3.0,  0.8),
    (4.0,  1.0), (5.0,  1.2), (6.0,  1.4), (7.0,  1.6),
    (8.0,  1.8), (9.0,  2.0), (10.0, 2.2), (15.0, 3.0),
]
_MAX_DIVERGENCE = 3.8


def get_divergence(value: float) -> float:
    """
    Возвращает допускаемое расхождение для значения СП или ЗП.
    Берётся из таблицы _TABLE по принципу «не больше порога».
    Для значений выше последнего порога — _MAX_DIVERGENCE.
    """
    for threshold, div in _TABLE:
        if value <= threshold:
            return div
    return _MAX_DIVERGENCE


@dataclass
class IncomingControlResult:
    sp_base:       float
    zp_base:       float
    sp_items_base: list[ImpurityEntry]
    zp_items_base: list[ImpurityEntry]
    sp_divergence: float
    zp_divergence: float
    sp_total:      float
    zp_total:      float
    sp_items:      list[ImpurityEntry]
    zp_items:      list[ImpurityEntry]


def _split_addition(base_items: list[ImpurityEntry], addition: float,
                    naveski: float, culture_name: str) -> list[ImpurityEntry]:
    """Распределяет add (допускаемое расхождение) пропорционально по примесям.
    Нулевые примеси не участвуют в распределении и остаются нулевыми."""
    if not base_items:
        return []

    nonzero = [i for i in base_items if i.percent > 0]
    if not nonzero:
        # Все нули — ничего не накидываем
        return [ImpurityEntry(name=i.name, percent=0.0,
                              grams=0.0) for i in base_items]

    total_base = sum(i.percent for i in nonzero)
    weights = [i.percent / total_base for i in nonzero]
    add_parts = split_weighted_even(addition, weights)

    # Строим словарь накидок для ненулевых
    bump_map: dict[str, float] = {
        imp.name: add
        for imp, add in zip(nonzero, add_parts)
    }

    result = []
    for imp in base_items:
        add = bump_map.get(imp.name, 0.0)
        new_percent = round(imp.percent + add, 2)
        result.append(ImpurityEntry(
            name=imp.name,
            percent=new_percent,
            grams=calc_grams(imp.name, new_percent, naveski, culture_name),
        ))
    return result


def apply_incoming_control(
    sp_base: float, zp_base: float,
    sp_items_base: list[ImpurityEntry],
    zp_items_base: list[ImpurityEntry],
    naveski: float, culture_name: str,
) -> IncomingControlResult:
    """
    Применяет входной контроль: добавляет к базовым СП и ЗП допускаемое
    расхождение и пропорционально распределяет добавку по примесям.
    Возвращает IncomingControlResult с базовыми и итоговыми значениями.
    """
    sp_div   = get_divergence(sp_base)
    zp_div   = get_divergence(zp_base)
    sp_total = round(sp_base + sp_div, 2)
    zp_total = round(zp_base + zp_div, 2)

    return IncomingControlResult(
        sp_base=sp_base, zp_base=zp_base,
        sp_items_base=sp_items_base, zp_items_base=zp_items_base,
        sp_divergence=sp_div, zp_divergence=zp_div,
        sp_total=sp_total, zp_total=zp_total,
        sp_items=_split_addition(sp_items_base, sp_div, naveski, culture_name),
        zp_items=_split_addition(zp_items_base, zp_div, naveski, culture_name),
    )
