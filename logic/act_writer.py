"""
Запись данных карточек в Word-акт (таблица 1 — основная).
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import date, timedelta
from typing import Optional

from docx import Document

from logic.db_service import Act, Card, Silo
from logic.file_lock import check_file_writable, FileLockError
from logic.card_params import CARD_TYPE_WASTE

logger = logging.getLogger(__name__)

import re

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "act_template.docx",
)

# Заголовок первой ячейки основной таблицы проб
_PROBES_TABLE_HEADER = "№ п/п"


def _find_probes_table(doc):
    """Находит основную таблицу проб по заголовку первой ячейки."""
    for tbl in doc.tables:
        if tbl.rows and tbl.cell(0, 0).text.strip() == _PROBES_TABLE_HEADER:
            return tbl
    raise ValueError(f"Таблица с заголовком '{_PROBES_TABLE_HEADER}' не найдена в документе")

# Маппинг культуры → (наименование для акта, ТНПА)
_CULTURE_META: dict[str, tuple[str, str]] = {
    "Пшеница 3 кл.":  ("Пшеница\n3 класс\nГОСТ 9353-90",    "ГОСТ 9353-90,\nТР ТС 015/2011"),
    "Пшеница 4 кл.":  ("Пшеница\n4 класс\nГОСТ 9353-90",    "ГОСТ 9353-90,\nТР ТС 015/2011"),
    "Пшеница корм.":  ("Пшеница\nкормовая\nСТБ 1135-98",     "СТБ 1135-98,\nТР ТС 015/2011"),
    "Тритикале":      ("Тритикале кормовая\nСТБ 1193-99",    "СТБ 1193-99,\nТР ТС 015/2011"),
    "Кукуруза":       ("Кукуруза\n3 класс\nГОСТ 13634-90",  "ГОСТ 13634-90,\nТР ТС 015/2011"),
    "Ячмень":         ("Ячмень кормовой\nСТБ 1136-98",       "СТБ 1136-98,\nТР ТС 015/2011"),
    "Овёс":           ("Овёс кормовой\nСТБ 1137-98",         "СТБ 1137-98,\nТР ТС 015/2011"),
}

# Для пшениц РФ — отдельный ТНПА
_WHEAT_RF_TNPA = "ГОСТ 9353-2016,\nТР ТС 015/2011"

_TNPA_SAMPLING   = "ГОСТ 13586.3-2015"
_PROBE_SIZE      = "2,0 кг"
_PACKAGING       = "Пластиковый контейнер. Целостность не нарушена"
_INDICATORS      = "Согласно схеме входного лабораторного контроля зерна департамента агропромышленного производства"


def _culture_name_tnpa(card: Card) -> tuple[str, str]:
    """Возвращает (наименование культуры, ТНПА показателей) для строки таблицы."""
    meta = _CULTURE_META.get(card.culture_name)
    if not meta:
        return card.culture_name, "ТР ТС 015/2011"

    name, tnpa = meta
    # Для пшеницы РФ меняем ТНПА
    is_wheat = card.culture_name.startswith("Пшеница") and card.culture_name != "Пшеница корм."
    if is_wheat and getattr(card, "origin_country", None) == "РФ":
        tnpa = _WHEAT_RF_TNPA
        # Меняем ГОСТ 9353-90 на ГОСТ 9353-2016 в наименовании
        name = name.replace("ГОСТ 9353-90", "ГОСТ 9353-2016")

    return name, tnpa


def _col4_manufacturer(card: Card) -> str:
    """Столбец 4 — сведения об изготовителе/поставщике."""
    supplier = getattr(card, "supplier", None) or ""
    base = supplier if supplier else "РБ, с/х предприятия;\nЗАО «БНБК»"
    return base


def _col5_harvest(card: Card, silo: Optional[Silo] = None) -> str:
    """
    Столбец 5 — дата изготовления (год урожая).

    Источники в порядке приоритета:
      1. card.harvest_year (для карточек Входного контроля)
      2. silo.harvest_year (для Перегонки/Отгрузки/Контроля при хранении)
    """
    year = getattr(card, "harvest_year", None)
    if not year and silo is not None:
        year = getattr(silo, "harvest_year", None)
    if year:
        return f"Урожай\n{year} г."
    return ""


def _col7_location(card: Card, silo: Optional[Silo]) -> str:
    """Столбец 7 — место отбора пробы (для актов Входного контроля)."""
    return ("Среднесуточная проба из автомобильного транспорта\n"
            "(входной контроль)")


def _origin_for_card(card: Card, silo: Optional[Silo]) -> str:
    """
    Возвращает 'РБ' или 'РФ' для подстановки в текст столбцов 4/7.
    Источники: card.origin_country → silo.origin → 'РБ' по умолчанию.
    """
    val = getattr(card, "origin_country", None)
    if not val and silo is not None:
        val = getattr(silo, "origin", None)
    return val or "РБ"


def _silo_number(silo: Optional[Silo]) -> str:
    """Номер силоса в виде строки (или '?' если не задан)."""
    if silo is None:
        return "?"
    n = getattr(silo, "number", None)
    return str(n) if n not in (None, "") else "?"


# Маппинг места перегонки → (примечание для столбца 4, примечание для столбца 7)
# Текст в скобках добавляется после страны (столбец 4) и после "Силос N" (столбец 7).
_DISTILLATION_LOCATION_TEXT: dict[str, tuple[str, str]] = {
    "Мукомолка": (
        "(мукомольное производство)",
        "(мукомольное производство)",
    ),
    "Свинки": (
        "перемещение из зернохранилища в производство комбикормов "
        "для с/х животных и птицы (Цех №1)",
        "(перемещение из зернохранилища в производство комбикормов "
        "для с/х животных и птицы (Цех №1)",
    ),
    "КРС": (
        "перемещение из зернохранилища в производство комбикормов "
        "для с/х животных и птицы (Цех №2)",
        "(перемещение из зернохранилища в производство комбикормов "
        "для с/х животных и птицы (Цех №2)",
    ),
    "Рыбы": (
        "(производство комбикормов для рыб)\n(Цех № 3)",
        "(перемещение из зернохранилища в производство "
        "комбикормов для рыб)\n(Цех № 3)",
    ),
}


def _col4_daily(card: Card, silo: Optional[Silo]) -> str:
    """Столбец 4 для среднесуточного акта."""
    ct = card.card_type

    if ct == "Перегонка":
        place = getattr(card, "distillation_place", None)
        meta = _DISTILLATION_LOCATION_TEXT.get(place or "")
        if meta:
            country = _origin_for_card(card, silo)
            note4, _ = meta
            return f"{country}, с/х предприятия;\nЗАО «БНБК» {note4}"

    if ct == "Отгрузка":
        country = _origin_for_card(card, silo)
        return f"{country}, с/х предприятия;\nЗАО «БНБК»"

    if ct == "Контроль при хранении":
        country = _origin_for_card(card, silo)
        return f"{country}, с/х предприятия;\nЗАО «БНБК»"

    if ct == CARD_TYPE_WASTE:
        return "РБ, Экология города"

    # Заглушка для прочих типов (Очистка) — будет уточнено отдельно
    return _col4_manufacturer(card)


def _col7_daily(card: Card, silo: Optional[Silo]) -> str:
    """Столбец 7 для среднесуточного акта."""
    ct = card.card_type

    if ct == "Перегонка":
        place = getattr(card, "distillation_place", None)
        meta = _DISTILLATION_LOCATION_TEXT.get(place or "")
        if meta:
            _, note7 = meta
            return f"Силос {_silo_number(silo)}\n{note7}"

    if ct == "Отгрузка":
        consignee = (getattr(card, "consignee", None) or "").strip()
        lines = [
            f"Силос {_silo_number(silo)}",
            "(Контроль при отгрузке)",
        ]
        if consignee:
            lines.append(consignee)
        return "\n".join(lines)

    if ct == "Контроль при хранении":
        return f"Силос {_silo_number(silo)}\nКонтроль при хранении"

    if ct == CARD_TYPE_WASTE:
        return "Зернохранилище\n(контроль при\nотгрузке)"

    # Заглушка для прочих типов (Очистка) — будет уточнено отдельно
    return ""


def _col8_probe(card: Card) -> str:
    """Столбец 8 — размер пробы + номер пробы."""
    return f"{_PROBE_SIZE}\n{card.probe_number}"



def get_max_act_number_from_dir(acts_dir: str) -> int:
    """
    Сканирует папку актов и возвращает максимальный целочисленный номер.
    Парсит имена вида «Акт отбора проб №273.2 от ...».
    Поддерживает разные форматы суффикса (.2, пробелы и т.д.).
    Если папка пустая или не существует — возвращает 0.
    """
    if not acts_dir or not os.path.isdir(acts_dir):
        return 0

    # Ищем число после № и перед .2 (точка-двойка обязательна)
    pattern = re.compile(r"[№#](\d+)[.,]2", re.UNICODE)
    max_num = 0
    for fname in os.listdir(acts_dir):
        if not fname.endswith(".docx"):
            continue
        m = pattern.search(fname)
        if m:
            max_num = max(max_num, int(m.group(1)))
            logger.debug("Найден акт: %s → номер %s", fname, m.group(1))
        else:
            logger.debug("Не распознан: %s", fname)
    return max_num


def build_act_filename(act: Act) -> str:
    """Формирует имя файла акта."""
    today = date.today()
    if act.act_type == "shift2":
        # Дата следующего дня
        d = today + timedelta(days=1)
    else:
        d = today

    date_str = d.strftime("%d.%m.%Y")
    num = act.number_str

    if act.act_type == "daily":
        return f"Акт отбора проб №{num} от {date_str}.docx"
    elif act.act_type == "shift1":
        return f"Акт отбора проб №{num} от {date_str} - 1 см.docx"
    else:  # shift2
        return f"Акт отбора проб №{num} от {date_str} - 2 см.docx"


def create_act_file(act: Act, acts_dir: str) -> str:
    """
    Копирует шаблон в папку актов, заполняет шапку (даты, работников,
    номер акта, колонтитул) и возвращает путь к новому файлу.
    """
    os.makedirs(acts_dir, exist_ok=True)
    filename = build_act_filename(act)
    dest = os.path.join(acts_dir, filename)
    shutil.copy2(TEMPLATE_PATH, dest)

    # Заполняем шапку и подписи
    try:
        _fill_act_header(dest, act)
    except Exception:
        # Не падаем на этапе заполнения шапки — файл уже создан
        logger.exception("Не удалось заполнить шапку акта %s", dest)

    logger.info("Создан файл акта: %s", dest)
    return dest


# ── Месяцы в родительном падеже ──────────────────────────────────────────────
_MONTHS_RU_GEN = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _format_period_date(act_type: str, today: Optional[date] = None) -> str:
    """
    Дата периода отбора:
      - shift2 (ночная): 'DD-DD.MM.YYYY' (сегодня-завтра).
        Если переход через месяц/год — формат остаётся тем же,
        день берётся как день завтра.
      - shift1 / daily: 'DD.MM.YYYY' (только сегодня).
    """
    today = today or date.today()
    if act_type == "shift2":
        tomorrow = today + timedelta(days=1)
        return f"{today.day:02d}-{tomorrow.day:02d}.{tomorrow.month:02d}.{tomorrow.year}"
    return today.strftime("%d.%m.%Y")


def _format_short_date(today: Optional[date] = None) -> str:
    """Короткий формат для колонтитула: DD.MM.YYYY (всегда сегодняшняя)."""
    today = today or date.today()
    return today.strftime("%d.%m.%Y")


def _swap_initials(name: str) -> str:
    """
    Преобразует 'Фамилия И.О.' → 'И.О. Фамилия' (для подписей).
    Если формат не распознан — возвращает исходную строку.
    """
    s = (name or "").strip()
    if not s:
        return s
    # Ищем последний кусок, состоящий только из инициалов (заглавные + точки)
    parts = s.split()
    if len(parts) < 2:
        return s
    # Берём всё кроме последнего как фамилию (на случай двойных фамилий
    # без дефиса) — хотя обычно фамилия одна.
    surname = " ".join(parts[:-1])
    initials = parts[-1]
    # Проверяем, что последний токен — это инициалы (содержит хотя бы одну точку)
    if "." in initials:
        return f"{initials} {surname}"
    return s


def _replace_paragraph_text(paragraph, new_text: str) -> None:
    """
    Заменяет текст параграфа на new_text, сохраняя форматирование первого run.
    Все остальные run-ы внутри параграфа удаляются.

    Поддерживает многострочный текст: '\n' → отдельный <w:br/>.
    """
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import copy

    runs = paragraph.runs
    if not runs:
        # В параграфе вообще нет run-ов — добавим простой
        run = paragraph.add_run(new_text)
        return

    # Сохраняем первый run и его свойства
    first_run = runs[0]
    first_rPr = first_run._r.find(qn("w:rPr"))

    # Удаляем все runs кроме первого
    for r in runs[1:]:
        r._r.getparent().remove(r._r)

    # Очищаем содержимое первого run, оставляя только rPr
    for child in list(first_run._r):
        if child.tag != qn("w:rPr"):
            first_run._r.remove(child)

    # Заполняем текст с поддержкой переносов строк
    lines = new_text.split("\n") if new_text else [""]
    for i, line in enumerate(lines):
        if i > 0:
            br = OxmlElement("w:br")
            first_run._r.append(br)
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = line
        first_run._r.append(t)


def _replace_in_paragraph(paragraph, search: str, replacement: str) -> bool:
    """
    Заменяет подстроку search → replacement в тексте параграфа.
    Все runs склеиваются в первый, форматирование первого run сохраняется.
    Возвращает True если замена произошла.
    """
    text = paragraph.text
    if search not in text:
        return False
    new_text = text.replace(search, replacement)
    _replace_paragraph_text(paragraph, new_text)
    return True


def _iter_all_paragraphs(doc):
    """Итерируется по всем параграфам документа: тело, таблицы, колонтитулы."""
    yield from doc.paragraphs
    for table in doc.tables:
        for row in table.rows:
            # Используем уникальные tc через _tr.iterchildren — иначе merged
            # cells выдадут одни и те же параграфы несколько раз.
            from docx.oxml.ns import qn
            from docx.table import _Cell
            seen = set()
            for tc in row._tr.iterchildren(qn("w:tc")):
                tc_id = id(tc)
                if tc_id in seen:
                    continue
                seen.add(tc_id)
                cell = _Cell(tc, row.table)
                yield from cell.paragraphs
                # Вложенные таблицы
                for inner in cell.tables:
                    for ir in inner.rows:
                        for ic in ir.cells:
                            yield from ic.paragraphs

    for section in doc.sections:
        for hf in (section.header, section.footer):
            yield from hf.paragraphs
            for table in hf.tables:
                for row in table.rows:
                    from docx.oxml.ns import qn
                    from docx.table import _Cell
                    seen = set()
                    for tc in row._tr.iterchildren(qn("w:tc")):
                        tc_id = id(tc)
                        if tc_id in seen:
                            continue
                        seen.add(tc_id)
                        cell = _Cell(tc, row.table)
                        yield from cell.paragraphs


def _normalize_split_placeholders_in_xml(xml_text: str) -> str:
    """
    Word иногда разбивает плейсхолдер {{NAME}} на несколько <w:t>,
    что мешает прямой замене подстроки. Эта функция склеивает
    разбитый плейсхолдер обратно в один <w:t> внутри одного <w:r>.

    Работает напрямую с XML — потому что python-docx не всегда видит
    все runs (например, runs внутри <w:hyperlink>, <w:smartTag>, и т.д.)
    """
    import re
    # Регулярка ищет «фрагмент XML параграфа», где между {{ и }} прерывается
    # XML-тегами — и склеивает текст обратно.
    # Алгоритм: проходим по тексту, находим любые '{', '}', и собираем
    # placeholder'ы, разбитые на несколько <w:t>.

    # Собираем чистый текст из всего параграфа, проходя только содержимое <w:t>
    # и заменяя плейсхолдер на единый блок текста — это слишком сложно делать
    # регуляркой надёжно.

    # Простой и надёжный подход: regex, который ищет {{NAME}} разбитый
    # на несколько <w:t>...</w:t> с XML-мусором между ними, и склеивает.
    PLACEHOLDER_NAMES = [
        "DAY", "MONTH", "YEAR", "PERIOD",
        "WORKERS", "ISSUER",
        "SIGN1", "SIGN2", "SIGN3",
        "ACTNUM", "FOOTER_DATE",
        "TEMP_MIN", "TEMP_MAX", "HUM_MIN", "HUM_MAX",
        "TOTAL_PAGES",
    ]

    for name in PLACEHOLDER_NAMES:
        full = "{{" + name + "}}"
        if full in xml_text:
            continue  # уже целым куском — склеивать не нужно

        # Если плейсхолдера не видно как одной строки, ищем его разбитую
        # версию: { { NAME } } в любом порядке через любые XML-теги.
        # Создаём регулярку, которая ищет каждый символ плейсхолдера
        # с допуском произвольных XML-тегов между ними.
        chars = list(full)  # ['{', '{', 'N', 'A', 'M', 'E', '}', '}']
        pattern_parts = []
        for c in chars:
            pattern_parts.append(re.escape(c))
            pattern_parts.append(r"(?:<[^>]+>)*")
        # Убираем последний "(?:...)" чтобы не было лишнего хвоста
        pattern_parts.pop()
        pattern = "".join(pattern_parts)

        # Если разбит — склеиваем в одну строку (заменяем найденное на full)
        xml_text = re.sub(pattern, full, xml_text)

    return xml_text


def _fill_act_header(file_path: str, act: Act) -> None:
    """
    Заполняет шапку акта подстановкой плейсхолдеров {{...}}.

    Работа идёт напрямую на уровне XML внутри docx-архива,
    что гарантирует замену даже если Word разбил плейсхолдер
    на несколько <w:t> или поместил в <w:hyperlink>/<w:smartTag>.

    Заменяемые плейсхолдеры:
      {{DAY}}, {{MONTH}}, {{YEAR}} — верхняя дата составления и выдачи
      {{PERIOD}}                  — Дата (период) отбора
      {{WORKERS}}                 — все работники смены через запятую
      {{ISSUER}}                  — один работник (составитель акта)
      {{SIGN1}}, {{SIGN2}}, {{SIGN3}} — подписи (формат «И.О. Фамилия»)
      {{ACTNUM}}                  — номер акта (например 262.2)
      {{FOOTER_DATE}}             — дата в нижнем колонтитуле

    Плейсхолдеры {{TEMP_MIN}}, {{TEMP_MAX}}, {{HUM_MIN}}, {{HUM_MAX}},
    {{TOTAL_PAGES}} НЕ заполняются здесь — они для функции «Печать».
    """
    import zipfile
    import shutil as _shutil
    import os as _os
    import tempfile
    import random
    from xml.sax.saxutils import escape as xml_escape

    from logic.db_service import get_shift_by_id

    today = date.today()
    if act.act_type == "shift2":
        top_date = today + timedelta(days=1)
    else:
        top_date = today

    period_str = _format_period_date(act.act_type, today)
    footer_date = top_date.strftime("%d.%m.%Y")

    # Подбор работников для подстановки.
    #
    # Среднесуточный акт (shift1/shift2):
    #   Все работники одной смены (act.shift_id) — 3 человека.
    #
    # Входной акт (daily):
    #   По одному случайному работнику из каждой из двух смен.
    #   Issuer (составитель) — работник из второй смены.
    #   Подписи — оба работника (1 и 2 строки), 3-я строка пустая.
    if act.act_type == "daily":
        shift_a = get_shift_by_id(act.shift_id)  if act.shift_id  else None
        shift_b = get_shift_by_id(act.shift_id2) if act.shift_id2 else None
        worker_a = random.choice(shift_a.workers) if (shift_a and shift_a.workers) else None
        worker_b = random.choice(shift_b.workers) if (shift_b and shift_b.workers) else None

        worker_names: list[str] = []
        if worker_a:
            worker_names.append(worker_a.name)
        if worker_b:
            worker_names.append(worker_b.name)

        # Issuer — работник второй смены, если он есть; иначе первой.
        issuer_name = (worker_b.name if worker_b
                       else (worker_a.name if worker_a else ""))

        # Подписи: 2 строки (А, Б), 3-я пустая.
        sign_names = [
            _swap_initials(worker_a.name) if worker_a else "",
            _swap_initials(worker_b.name) if worker_b else "",
            "",
        ]
    else:
        shift = get_shift_by_id(act.shift_id) if act.shift_id else None
        workers = list(shift.workers) if shift else []
        worker_names = [w.name for w in workers]
        issuer_name = worker_names[0] if worker_names else ""
        sign_names = [_swap_initials(n) for n in worker_names[:3]]
        while len(sign_names) < 3:
            sign_names.append("")

    workers_csv = ", ".join(worker_names) if worker_names else ""

    # Карта замен — значения экранируются для XML
    replacements: dict[str, str] = {
        "{{DAY}}":         xml_escape(f"{top_date.day:02d}"),
        "{{MONTH}}":       xml_escape(_MONTHS_RU_GEN[top_date.month - 1]),
        "{{YEAR}}":        xml_escape(str(top_date.year)),
        "{{PERIOD}}":      xml_escape(period_str),
        "{{WORKERS}}":     xml_escape(workers_csv),
        "{{ISSUER}}":      xml_escape(issuer_name),
        "{{SIGN1}}":       xml_escape(sign_names[0]),
        "{{SIGN2}}":       xml_escape(sign_names[1]),
        "{{SIGN3}}":       xml_escape(sign_names[2]),
        "{{ACTNUM}}":      xml_escape(act.number_str),
        "{{FOOTER_DATE}}": xml_escape(footer_date),
    }

    # Файлы внутри docx-архива, которые могут содержать плейсхолдеры
    target_xml_files = [
        "word/document.xml",
        "word/header1.xml", "word/header2.xml", "word/header3.xml",
        "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
    ]

    # Работаем через временный файл — переписываем только нужные XML внутри zip
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    _os.close(tmp_fd)
    try:
        with zipfile.ZipFile(file_path, "r") as zin:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename in target_xml_files:
                        try:
                            text = data.decode("utf-8")
                        except UnicodeDecodeError:
                            zout.writestr(item, data)
                            continue
                        # 1. Склеиваем разбитые плейсхолдеры в один <w:t>
                        text = _normalize_split_placeholders_in_xml(text)
                        # 2. Подставляем значения
                        for key, value in replacements.items():
                            if key in text:
                                text = text.replace(key, value)
                        data = text.encode("utf-8")
                    zout.writestr(item, data)
        _shutil.move(tmp_path, file_path)
    finally:
        if _os.path.exists(tmp_path):
            try:
                _os.remove(tmp_path)
            except OSError:
                pass


def _set_cell_text(cell, text: str) -> None:
    """
    Заполняет ячейку текстом. Удаляет все существующие параграфы
    и создаёт один новый с правильным порядком элементов.

    Использует python-docx high-level API (cell.paragraphs[0]) +
    OxmlElement для форматирования run-ов.
    """
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    tc = cell._tc

    # Удаляем все существующие параграфы внутри tc
    for p in list(tc.iterchildren(qn("w:p"))):
        tc.remove(p)

    # Создаём один пустой параграф через нижний XML
    # (cell.add_paragraph не может — нет параграфов вообще)
    p_elem = OxmlElement("w:p")

    # pPr с выравниванием по центру
    pPr = OxmlElement("w:pPr")
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    pPr.append(jc)
    p_elem.append(pPr)

    # Текст с разбивкой по строкам
    lines = text.split("\n") if text else [""]
    for i, line in enumerate(lines):
        r = OxmlElement("w:r")

        rPr = OxmlElement("w:rPr")
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(qn("w:ascii"), "Times New Roman")
        rFonts.set(qn("w:hAnsi"), "Times New Roman")
        rPr.append(rFonts)
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "16")  # 8pt
        rPr.append(sz)
        szCs = OxmlElement("w:szCs")
        szCs.set(qn("w:val"), "16")
        rPr.append(szCs)
        r.append(rPr)

        # Перенос строки внутри run для строк после первой
        if i > 0:
            br = OxmlElement("w:br")
            r.append(br)

        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = line
        r.append(t)
        p_elem.append(r)

    # Вставляем параграф в правильную позицию:
    # OOXML требует tcPr -> p (если tcPr есть)
    tcPr = tc.find(qn("w:tcPr"))
    if tcPr is not None:
        tcPr.addnext(p_elem)
    else:
        tc.insert(0, p_elem)


def append_row_to_act(file_path: str, card: Card,
                       row_num: int, silo: Optional[Silo] = None,
                       act_type: str = "incoming") -> None:
    """
    Добавляет строку с данными карточки в основную таблицу акта.

    Параметры:
      file_path — путь к файлу акта.
      card — карточка пробы.
      row_num — номер строки в таблице.
      silo — связанный силос (для Перегонки/Отгрузки/Контроля при хранении).
      act_type — тип акта в БД:
                 'daily'  — акт входного контроля,
                 'shift1' — среднесуточный (1 смена),
                 'shift2' — среднесуточный (2 смена).
                 От него зависит наполнение столбцов 4 и 7.
    """
    from docx.oxml.ns import qn
    import copy

    # Проверяем доступность файла ДО начала операции
    check_file_writable(file_path)

    doc = Document(file_path)
    table = _find_probes_table(doc)

    # Берём «эталонную» строку из чистого шаблона
    template_doc = Document(TEMPLATE_PATH)
    template_table = _find_probes_table(template_doc)
    template_row_tr = template_table.rows[-1]._tr
    new_tr = copy.deepcopy(template_row_tr)

    # Вставляем клон ПЕРЕД последней строкой текущего акта
    last_tr = table.rows[-1]._tr
    last_tr.addprevious(new_tr)

    # Тип акта в БД:
    #   "daily"  — Входной контроль  (название историческое)
    #   "shift1" — Среднесуточный (1 смена)
    #   "shift2" — Среднесуточный (2 смена)
    is_daily = act_type in ("shift1", "shift2")
    if is_daily:
        col4_text = _col4_daily(card, silo)
        col7_text = _col7_daily(card, silo)
    else:
        col4_text = _col4_manufacturer(card)
        col7_text = _col7_location(card, silo)

    # Подготавливаем данные
    culture_name, tnpa_indicators = _culture_name_tnpa(card)
    cells_data = [
        str(row_num),                      # 1. № п/п
        culture_name,                      # 2. Наименование продукта
        _TNPA_SAMPLING,                    # 3. ТНПА правил отбора
        col4_text,                         # 4. Сведения об изготовителе
        _col5_harvest(card, silo),         # 5. Дата изготовления
        "",                                # 6. Размер партии (пустой)
        col7_text,                         # 7. Место отбора
        _col8_probe(card),                 # 8. Размер пробы + ID
        _PACKAGING,                        # 9. Состояние упаковки
        _INDICATORS,                       # 10. Показатели
        tnpa_indicators,                   # 11. ТНПА показателей
    ]

    # Заполняем ячейки через python-docx API.
    # Используем table.rows для получения свежего отображения row после addprevious.
    new_row = None
    for r in table.rows:
        if r._tr is new_tr:
            new_row = r
            break

    if new_row is None:
        raise RuntimeError("Не удалось найти вставленную строку в таблице")

    cells = new_row.cells
    if len(cells) < len(cells_data):
        logger.warning(
            "В строке акта только %d ячеек, ожидалось %d",
            len(cells), len(cells_data),
        )

    for i, text in enumerate(cells_data):
        if i >= len(cells):
            break
        _set_cell_text(cells[i], text)

    doc.save(file_path)
    logger.info("Добавлена строка %d в акт %s", row_num, file_path)
