"""
Калькулятор клейковины.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


def _rand_step(lo: float, hi: float, step: float) -> float:
    """Случайное число из диапазона с заданным шагом."""
    n = round((hi - lo) / step)
    return round(lo + random.randint(0, n) * step, 10)


def _rand_even(lo: float, hi: float) -> float:
    """Случайное чётное дробное с шагом 0.2."""
    return round(_rand_step(lo, hi, 0.2), 1)


@dataclass
class GlutenCalc:
    """Один расчёт клейковины (из двух)."""
    v1: float   # клейковина / 4
    v2: float   # v1 + rand(0.04..0.10)
    v3: float   # v2 + rand(0.15..0.46)
    # выводятся в порядке: v3, v2, v1


@dataclass
class IdkCalc:
    """Один расчёт ИДК (из двух)."""
    idk_input: float
    divergence: float
    idk1: float   # idk - div/2
    idk2: float   # idk + div/2


@dataclass
class GlutenResult:
    gluten_input: float
    idk_input:    float
    calc1:        GlutenCalc
    calc2:        GlutenCalc
    idk1:         IdkCalc
    idk2:         IdkCalc


def _gluten_calc(gluten: float) -> GlutenCalc:
    v1 = round(gluten / 4, 2)
    v2 = round(v1 + _rand_step(0.04, 0.10, 0.01), 2)
    v3 = round(v2 + _rand_step(0.15, 0.46, 0.01), 2)
    return GlutenCalc(v1=v1, v2=v2, v3=v3)


def _idk_calc(idk: float) -> IdkCalc:
    div  = _rand_even(0.2, 4.0)
    idk1 = round(idk - div / 2, 1)
    idk2 = round(idk + div / 2, 1)
    return IdkCalc(idk_input=idk, divergence=div, idk1=idk1, idk2=idk2)


def calc_gluten(gluten: float, idk: float) -> GlutenResult:
    """
    Рассчитывает данные для журнала клейковины: 2 параллельных расчёта v1/v2/v3
    и 2 расчёта ИДК со случайным расхождением.
    """
    return GlutenResult(
        gluten_input=gluten,
        idk_input=idk,
        calc1=_gluten_calc(gluten),
        calc2=_gluten_calc(gluten),
        idk1=_idk_calc(idk),
        idk2=_idk_calc(idk),
    )
