"""
Запись данных карточек в Excel-отчёт.
Два листа: «Производства АПП» (КРС/Свинки) и «МКМЦ» (Мукомолка).
"""

from __future__ import annotations

import logging
import os
import random
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, Side

from logic.card_params import GLUTEN_ARB_CULTURES, WHEAT_CULTURES
from logic.db_service import Card
from logic.file_lock import check_file_writable, FileLockError

logger = logging.getLogger(__name__)


@dataclass
class ExportRow:
    """Данные одной строки для записи в Excel."""
    card:        Card
    silo:        object          # Silo — данные из силоса
    weight_kg:   str             # вес, кг (необязательный)
    executor:    str             # исполнитель
    tank_number: str             # M: номер ёмкости (для МКМЦ)
    workshop:    str = ""        # Цех 1 / Цех 2 (для АПП)


# ── Жирные колонки ────────────────────────────────────────────────────────────
# Объявлены наверху, чтобы порядок был линейным:
# (определения) → (низкоуровневые функции) → (публичный API).

# АПП: A-H (силос-данные), R (humidity), S (sp_total)
_BOLD_COLS_APP: frozenset[int]   = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 18, 19})
# МКМЦ: только A (№ п/п)
_BOLD_COLS_MKMTS: frozenset[int] = frozenset({1})


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _next_num(ws) -> int:
    """
    Следующий порядковый номер № п/п.
    Ищет последнее числовое значение в колонке A, начиная с конца.
    Это устойчиво к строкам типа «Итого» в первой колонке.
    """
    for r in range(ws.max_row, 2, -1):
        val = ws.cell(r, 1).value
        if val is None:
            continue
        try:
            return int(val) + 1
        except (TypeError, ValueError):
            continue
    return 1


def _last_data_row(ws) -> int:
    """Возвращает номер последней строки с данными (начиная с row=3)."""
    for r in range(ws.max_row, 2, -1):
        if ws.cell(r, 1).value is not None:
            return r
    return 2  # нет данных — вернём строку заголовка


# ── АПП (КРС / Свинки) ───────────────────────────────────────────────────────
# Колонки:
#  A(1)  = № п/п
#  B(2)  = дата
#  C(3)  = № пробы
#  D(4)  = силос номер
#  E(5)  = культура (crop_name)
#  F(6)  = класс (crop_class)
#  G(7)  = год урожая (harvest_year)
#  H(8)  = происхождение (origin)
#  I(9)  = вес (необяз.)
#  J(10) = вес (необяз.)
#  L(12) = "Отгрузка (производства)"
#  M(13) = цех: "для КРС" или "для свиней"
#  O(15) = "свойств."
#  P(16) = "свойств."
#  Q(17) = "н/обн."
#  R(18) = humidity
#  S(19) = sp_total
#  T(20) = zp_total
#  V(22) = gluten (экспресс) — все пшеницы
#  W(23) = gluten_arb (арбитраж) — только П3/П4
#  X(24) = idc
#  Z(26) = natura
#  AA(27)= vitreousness
#  AB(28)= fall_number
#  AC(29)= protein
#  AF(32)= исполнитель

_APP_MAP: dict[int, str] = {
    1:  "__num__",
    2:  "__date__",
    3:  "probe_number",
    4:  "__silo_number__",
    5:  "__silo_crop__",
    6:  "__silo_class__",
    7:  "__silo_year__",
    8:  "__silo_origin__",
    9:  "__weight__",
    10: "__weight__",
    12: "Отгрузка (производства)",
    13: "__workshop__",
    15: "свойств.",
    16: "свойств.",
    17: "н/обн.",
    18: "humidity",
    19: "sp_total",
    20: "zp_total",
    22: "__gluten_express__",
    23: "__gluten_arb__",
    24: "idc",
    26: "natura",
    27: "vitreousness",
    28: "fall_number",
    29: "protein",
    32: "__executor__",
}

# ── МКМЦ (Мукомолка) ─────────────────────────────────────────────────────────
# Правила:
#  A(1)  = № п/п
#  B(2)  = сегодняшняя дата
#  C(3)  = № пробы
#  D(4)  = silo.number
#  E(5)  = silo.crop_name
#  F(6)  = silo.crop_class
#  G(7)  = silo.harvest_year
#  H(8)  = silo.origin
#  I(9)  = weight_kg
#  K(11) = копируется — наименование операции
#  L(12) = копируется — получатель
#  M(13) = tank_number — номер ёмкости
#  N(14) = копируется
#  O(15) = копируется
#  P(16) = копируется
#  R(18) = humidity
#  T(20) = sp_total
#  U(21) = zp_total
#  V(22) = случайное 0.2 или 0.3
#  W(23) = gluten экспресс (пшеницы)
#  X(24) = gluten арбитраж (П3/П4)
#  Y(25) = idc
#  Z(26) = "II"
#  AA(27)= natura
#  AB(28)= vitreousness
#  AC(29)= fall_number
#  AD(30)= protein
#  AF(32)= исполнитель (3 строки: Начало/Окончание/Скорость)
#  AG(33)= исполнитель

_MKMTS_MAP: dict[int, str] = {
    1:  "__num__",
    2:  "__date__",
    3:  "probe_number",
    4:  "__silo_number__",
    5:  "__silo_crop__",
    6:  "__silo_class__",
    7:  "__silo_year__",
    8:  "__silo_origin__",
    9:  "__weight__",
    11: "__copy__",           # K
    12: "__copy__",           # L
    13: "__tank__",           # M
    14: "__copy__",           # N
    15: "__copy__",           # O
    16: "__copy__",           # P
    18: "humidity",           # R
    20: "sp_total",           # T
    21: "zp_total",           # U
    22: "__random_02_03__",   # V — случайное 0.2 или 0.3
    23: "__gluten_express__", # W — клейковина экспресс
    24: "__gluten_arb__",     # X — клейковина арбитраж
    25: "idc",                # Y
    26: "II",                 # Z
    27: "natura",             # AA
    28: "vitreousness",       # AB
    29: "fall_number",        # AC
    30: "protein",            # AD
    32: "__mkmts_af__",       # AF — многострочное примечание
    33: "__executor__",       # AG
}


def _get_val(card: Card, field: str, row: ExportRow):
    """
    Возвращает значение для записи в ячейку Excel.

    Виртуальные поля (с двойным подчёркиванием) обрабатываются особо.
    Поля без подчёркивания читаются прямо из card по имени атрибута.
    """
    # Виртуальные поля строки экспорта
    if field == "__num__":          return None  # подставляется позже
    if field == "__date__":         return None  # подставляется позже
    if field == "__copy__":         return None  # копируется позже
    if field == "__weight__":       return row.weight_kg or None
    if field == "__executor__":     return row.executor
    if field == "__tank__":         return row.tank_number

    # Виртуальные поля силоса
    silo = row.silo
    if field == "__silo_number__":  return silo.number       if silo else None
    if field == "__silo_crop__":    return silo.crop_name    if silo else None
    if field == "__silo_class__":   return silo.crop_class   if silo else None
    if field == "__silo_year__":    return silo.harvest_year if silo else None
    if field == "__silo_origin__":  return silo.origin       if silo else None

    # Виртуальные поля специальных значений
    if field == "__random_02_03__": return random.choice([0.2, 0.3])
    if field == "__mkmts_af__":
        now = datetime.now().strftime("%H:%M")
        return f"Начало подачи {now}\nОкончание подачи {now}\nСкорость подачи 100 т/ч"
    if field == "__workshop__":
        return _WORKSHOP_LABELS.get(row.workshop, row.workshop or None)

    # Клейковина (экспресс) — только для пшеницы
    if field == "__gluten_express__":
        return card.gluten if card.culture_name in WHEAT_CULTURES else None
    # Клейковина (арбитраж) — только для П3/П4
    if field == "__gluten_arb__":
        return card.gluten_arb if card.culture_name in GLUTEN_ARB_CULTURES else None

    # Прямое чтение атрибута из Card; если такого нет — возвращаем имя
    # (это поведение позволяет «закладывать» в _APP_MAP/_MKMTS_MAP литералы).
    return getattr(card, field, field)


# Маппинг workshop (distillation_place) → текст для Excel-ячейки
_WORKSHOP_LABELS: dict[str, str] = {
    "Свинки":   "для свиней",
    "КРС":      "для КРС",
    "Мукомолка": "Мукомолка",
    "Рыбы":     "для рыб",
    # обратная совместимость со старыми значениями
    "Цех 1": "для КРС",
    "Цех 2": "для свиней",
}


# Поля требующие числового формата "0.0"
_NUMERIC_FORMAT_1 = {"humidity", "sp_total", "zp_total",
                     "__gluten_express__", "__gluten_arb__",
                     "idc", "vitreousness", "fall_number", "protein", "natura"}


def _apply_row_format(ws, row_num: int,
                      bold_cols: frozenset[int],
                      wrap_cols: frozenset[int] | set[int] | None = None) -> None:
    """
    Применяет единый формат ко всем ячейкам строки.
    bold_cols — колонки с жирным шрифтом.
    wrap_cols — колонки с переносом строк (wrap_text=True).
    """
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap_set = wrap_cols or frozenset()

    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row_num, col)
        cell.font      = Font(name="Times New Roman", size=10,
                              bold=col in bold_cols)
        cell.border    = border
        cell.alignment = Alignment(
            horizontal="center", vertical="center",
            wrap_text=col in wrap_set,
        )


def _write_rows(ws, mapping: dict, rows: list[ExportRow],
                bold_cols: frozenset[int],
                wrap_cols: frozenset[int] | set[int] | None = None,
                progress_cb=None) -> int:
    """Дописывает строки в лист. Возвращает количество записанных строк."""
    last = _last_data_row(ws)
    start_num = _next_num(ws)
    today_str = date.today().strftime("%d.%m.%Y")
    written = 0

    for i, row in enumerate(rows):
        dst_row = last + 1 + i
        num = start_num + i

        for col, field in mapping.items():
            cell = ws.cell(dst_row, col)
            if field == "__num__":
                cell.value = num
            elif field == "__date__":
                cell.value = today_str
            elif field == "__copy__":
                cell.value = ws.cell(last, col).value
            else:
                val = _get_val(row.card, field, row)
                if val is not None:
                    cell.value = val
                    if (field in _NUMERIC_FORMAT_1
                            and isinstance(val, (int, float))):
                        cell.number_format = "0.0"

        _apply_row_format(ws, dst_row, bold_cols=bold_cols, wrap_cols=wrap_cols)

        written += 1
        if progress_cb:
            progress_cb(written)

    return written


# ── Защита файла ──────────────────────────────────────────────────────────────


def _backup(excel_path: str, backup_dir: str | None = None) -> str:
    """
    Создаёт резервную копию Excel-файла.
    Если backup_dir задан — сохраняет в эту папку с временной меткой в имени.
    Иначе — рядом с оригиналом (имя_файла.backup.xlsx), перезаписывает.
    """
    from datetime import datetime
    directory = os.path.dirname(os.path.abspath(excel_path))
    name, ext = os.path.splitext(os.path.basename(excel_path))
    if backup_dir and os.path.isdir(backup_dir):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{name}_{ts}{ext}")
    else:
        backup_path = os.path.join(directory, f"{name}.backup{ext}")
    shutil.copy2(excel_path, backup_path)
    return backup_path


def _safe_export(excel_path: str, sheet_name: str, mapping: dict,
                 rows: list[ExportRow],
                 bold_cols: frozenset[int],
                 wrap_cols: frozenset[int] | set[int] | None = None,
                 progress_cb=None) -> int:
    """
    Безопасный экспорт с тремя уровнями защиты.
    progress_cb(step, total) — необязательный колбэк прогресса.
    Шаги: 0=бэкап, 1=копия, 2..N+1=строки, N+2=проверка, N+3=замена.
    """
    # Проверяем доступность файла ДО начала операции
    check_file_writable(excel_path)

    backup_path = None
    tmp_path = None
    total_steps = len(rows) + 4  # бэкап + копия + N строк + проверка + замена

    def _progress(step: int) -> None:
        if progress_cb:
            progress_cb(step, total_steps)

    try:
        _progress(0)
        from logic.db_service import get_setting
        excel_backup_dir = get_setting("excel_backup_dir") or None
        backup_path = _backup(excel_path, backup_dir=excel_backup_dir)

        _progress(1)
        directory = os.path.dirname(os.path.abspath(excel_path))
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx", dir=directory)
        os.close(tmp_fd)
        shutil.copy2(excel_path, tmp_path)

        wb = load_workbook(tmp_path)
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Лист «{sheet_name}» не найден в файле")
        ws = wb[sheet_name]
        count = _write_rows(ws, mapping, rows,
                            bold_cols=bold_cols, wrap_cols=wrap_cols,
                            progress_cb=lambda i: _progress(2 + i))
        wb.save(tmp_path)
        wb.close()

        _progress(total_steps - 2)
        wb_check = load_workbook(tmp_path, data_only=True, read_only=True)
        if sheet_name not in wb_check.sheetnames:
            raise ValueError("Проверка после записи не прошла: лист не найден")
        wb_check.close()

        _progress(total_steps - 1)
        shutil.move(tmp_path, excel_path)
        tmp_path = None

        _progress(total_steps)
        return count

    except Exception:
        if backup_path and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, excel_path)
            except Exception:
                # Восстановление не удалось — оригинал может быть в неконсистентном
                # состоянии. Логируем, но пробрасываем исходную ошибку.
                logger.exception("Не удалось восстановить из бэкапа %r", backup_path)
        raise

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.exception("Не удалось удалить временный файл %r", tmp_path)


# ── Публичный API ─────────────────────────────────────────────────────────────

def export_to_app(excel_path: str, rows: list[ExportRow],
                  progress_cb=None) -> int:
    """Записывает строки на лист «Производства АПП»."""
    return _safe_export(
        excel_path, "Производства АПП", _APP_MAP, rows,
        bold_cols=_BOLD_COLS_APP, progress_cb=progress_cb,
    )


def export_to_mkmts(excel_path: str, rows: list[ExportRow],
                    progress_cb=None) -> int:
    """Записывает строки на лист «МКМЦ»."""
    return _safe_export(
        excel_path, "МКМЦ", _MKMTS_MAP, rows,
        bold_cols=_BOLD_COLS_MKMTS, wrap_cols=frozenset({32}),  # AF — перенос строк
        progress_cb=progress_cb,
    )
