"""
Дополнительные параметры карточки зерна.
"""

from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Optional


RANGES = {
    "gluten_express": (18.0, 36.0),  # Клейковина (экспресс), %
    "gluten_arb":     (18.0, 36.0),  # Клейковина (арбитраж), %
    "humidity":       (8.0,  18.0),
    "natura":         (650,  850),
    "protein":        (10.0, 18.0),
    "vitreousness":   (30,   95),
    "idc":            (45,   105),
    "fall_number":    (150,  450),
}


@dataclass
class CardParams:
    humidity:        Optional[float] = None
    natura:          Optional[float] = None
    gluten_express:  Optional[float] = None  # Клейковина (экспресс), %
    gluten_arb:      Optional[float] = None  # Клейковина (арбитраж), % — только П3/П4
    protein:         Optional[float] = None
    vitreousness:    Optional[float] = None
    idc:             Optional[float] = None
    fall_number:     Optional[float] = None


NO_NATURA      = {"Кукуруза"}
WHEAT_CULTURES = {"Пшеница 3 кл.", "Пшеница 4 кл.", "Пшеница корм."}
WHEAT_EXTRA    = {"Пшеница 3 кл.", "Пшеница 4 кл."}
PROTEIN_CULTURES = {"Ячмень", "Овёс"}

# Культуры с арбитражной клейковиной
GLUTEN_ARB_CULTURES = {"Пшеница 3 кл.", "Пшеница 4 кл."}

# Тип карточки «Отходы» — только влажность в показателях
CARD_TYPE_WASTE = "Отходы"


# Маппинг ключей показателей в имена атрибутов Culture
# (для случаев, когда атрибут называется иначе, чем ключ).
_CULTURE_ATTR_KEY: dict[str, str] = {
    "gluten_express": "gluten",
}


def get_range(key: str, culture: object = None) -> tuple[float, float]:
    """
    Возвращает (min, max) для показателя.
    Если передан объект culture с атрибутами {key}_min/{key}_max — берёт их.
    Иначе — дефолтные RANGES.
    """
    if culture is not None:
        attr_key = _CULTURE_ATTR_KEY.get(key, key)
        lo_attr = f"{attr_key}_min"
        hi_attr = f"{attr_key}_max"
        if hasattr(culture, lo_attr) and hasattr(culture, hi_attr):
            return getattr(culture, lo_attr), getattr(culture, hi_attr)
    return RANGES.get(key, (0.0, 999.0))


def _calc_gluten_arb(express_val: float | None) -> float:
    """
    Арбитражная клейковина = экспресс + поправка от +0.1 до +0.4.
    Конечный результат всегда чётный (кратен 0.2).
    Алгоритм:
      1. Берём экспресс и добавляем случайное значение из [0.1, 0.4].
      2. Округляем результат вверх до ближайшего чётного (кратного 0.2).
      3. Если после округления результат оказался ниже экспресс+0.1 — добавляем 0.2.
    Если express_val некорректен (None/NaN), возвращает 0.0.
    """
    if express_val is None:
        return 0.0
    try:
        express_val = float(express_val)
    except (TypeError, ValueError):
        return 0.0
    if express_val != express_val:  # NaN
        return 0.0

    raw_result = express_val + random.uniform(0.1, 0.4)
    result = round(round(raw_result / 0.2) * 0.2, 1)

    # Гарантируем что арбитраж > экспресс (минимум +0.1)
    if result < express_val + 0.1 - 1e-9:
        result = round(round((express_val + 0.2) / 0.2) * 0.2, 1)

    return max(0.0, result)


def generate_params(
    culture_name: str,
    user_values: dict[str, str],
    culture: object = None,   # Culture из db_service (опционально)
    card_type: str = "",      # Тип карточки (например CARD_TYPE_WASTE)
) -> tuple[CardParams, list[str]]:
    """
    Генерирует значения показателей для карточки.
    Если в user_values для показателя есть значение — оно используется и валидируется.
    Иначе — генерируется случайно из диапазона культуры или из дефолтных RANGES.
    Для типа «Отходы» генерируется только Влажность.

    Возвращает: (заполненный CardParams, список активных ключей).
    """

    def get_user(key: str, decimals: int = 1) -> Optional[float]:
        """Парсит пользовательский ввод. Возвращает None если пусто или невалидно."""
        raw = user_values.get(key, "").strip()
        if not raw:
            return None
        try:
            return round(float(raw.replace(",", ".")), decimals)
        except ValueError:
            return None

    def val(key: str, decimals: int = 1) -> float:
        """Возвращает пользовательское значение или случайное из диапазона."""
        user_val = get_user(key, decimals)
        if user_val is not None:
            return user_val
        lo, hi = get_range(key, culture)
        return round(lo + random.random() * (hi - lo), decimals)

    def val_int(key: str) -> float:
        """Целочисленный аналог val (возвращает float для совместимости)."""
        user_val = get_user(key, 0)
        if user_val is not None:
            return user_val
        lo, hi = get_range(key, culture)
        return float(random.randint(int(lo), int(hi)))

    params = CardParams()
    active: list[str] = []

    # Тип «Отходы» — только влажность
    if card_type == CARD_TYPE_WASTE:
        active.append("humidity")
        params.humidity = val("humidity")
        return params, active

    # Влажность — все культуры
    active.append("humidity")
    params.humidity = val("humidity")

    # Натура — все кроме Кукурузы
    if culture_name not in NO_NATURA:
        active.append("natura")
        params.natura = val_int("natura")

    # Клейковина — все виды пшеницы
    if culture_name in WHEAT_CULTURES:
        active.append("gluten_express")
        params.gluten_express = val("gluten_express")

    # Арбитражная клейковина — только П3 и П4 (сразу после экспресс)
    if culture_name in GLUTEN_ARB_CULTURES:
        active.append("gluten_arb")
        manual_arb = get_user("gluten_arb")
        params.gluten_arb = (
            manual_arb if manual_arb is not None
            else _calc_gluten_arb(params.gluten_express)
        )

    # Белок — все виды пшеницы + Ячмень + Овёс
    if culture_name in WHEAT_CULTURES or culture_name in PROTEIN_CULTURES:
        active.append("protein")
        params.protein = val("protein")

    # Стекловидность, ИДК, ЧП — П3 и П4
    if culture_name in WHEAT_EXTRA:
        active.append("vitreousness")
        params.vitreousness = val_int("vitreousness")
        active.append("idc")
        params.idc = val("idc")
        active.append("fall_number")
        params.fall_number = val_int("fall_number")

    return params, active


# Метаданные для отображения
PARAM_META: dict[str, tuple[str, str, int]] = {
    "humidity":       ("Влажность",               "%",   1),
    "natura":         ("Натура",                  "г/л", 0),
    "gluten_express": ("Клейковина (экспресс)",   "%",   1),
    "gluten_arb":     ("Клейковина (арбитраж)",   "%",   1),
    "protein":        ("М.д. белка",              "%",   1),
    "vitreousness":   ("Стекловидность",          "%",   0),
    "idc":            ("ИДК",                     "",    1),
    "fall_number":    ("ЧП",                      "с",   0),
}


def validate_params(
    user_values: dict[str, str],
    active_keys: list[str],
    culture: object = None,
) -> dict[str, str]:
    """
    Валидирует пользовательские значения показателей.
    Возвращает dict {key: сообщение_об_ошибке} для полей с нарушениями.
    """
    errors: dict[str, str] = {}

    for key in active_keys:
        raw = user_values.get(key, "").strip()
        if not raw:
            continue  # пустое = авто, не валидируем
        try:
            val = float(raw.replace(",", "."))
        except ValueError:
            errors[key] = f"Некорректное значение: «{raw}»"
            continue
        lo, hi = get_range(key, culture)
        label = PARAM_META.get(key, (key, "", 1))[0]
        if val < lo:
            errors[key] = f"{label}: {val} ниже допустимого минимума {lo}"
        elif val > hi:
            errors[key] = f"{label}: {val} выше допустимого максимума {hi}"

    return errors
