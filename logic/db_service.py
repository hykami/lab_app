"""
Сервис для работы с БД — все операции CRUD в одном месте.
UI-слой импортирует только этот модуль, не работает с sqlite3 напрямую.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from data.database import get_connection


# ── Модели данных ─────────────────────────────────────────────────────────────

@dataclass
class ImpurityNorm:
    id:         int
    culture_id: int
    group_name: str   # "СП" | "ЗП"
    name:       str
    min_val:    float
    max_val:    float


@dataclass
class Culture:
    id:            int
    name:          str
    sample_weight: float
    sp_min:        float
    sp_max:        float
    zp_min:        float
    zp_max:        float
    # Нормы показателей (мин/макс для генерации и валидации)
    humidity_min:     float = 8.0
    humidity_max:     float = 18.0
    natura_min:       float = 650.0
    natura_max:       float = 850.0
    gluten_min:       float = 18.0
    gluten_max:       float = 36.0
    protein_min:      float = 10.0
    protein_max:      float = 18.0
    vitreousness_min: float = 30.0
    vitreousness_max: float = 95.0
    idc_min:          float = 45.0
    idc_max:          float = 105.0
    fall_number_min:  float = 150.0
    fall_number_max:  float = 450.0
    impurities:    list[ImpurityNorm] = field(default_factory=list)


@dataclass
class Box:
    id:       int
    number:   str
    weight:   float
    box_type: str = "standard"   # 'standard' | 'mesh'


# ── Культуры ──────────────────────────────────────────────────────────────────

def get_all_cultures() -> list[Culture]:
    """Возвращает все культуры (без подгрузки норм примесей)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cultures ORDER BY id"
        ).fetchall()
        return [Culture(**dict(r)) for r in rows]


def get_culture_with_norms(culture_id: int) -> Optional[Culture]:
    """Возвращает культуру вместе со списком норм примесей. None если нет."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cultures WHERE id = ?", (culture_id,)
        ).fetchone()
        if not row:
            return None
        culture = Culture(**dict(row))

        imp_rows = conn.execute(
            "SELECT * FROM impurity_norms WHERE culture_id = ? "
            "ORDER BY group_name DESC, id",
            (culture_id,),
        ).fetchall()
        culture.impurities = [ImpurityNorm(**dict(r)) for r in imp_rows]
        return culture


# Колонки культуры, которые сохраняются через save_culture
# (id, name, sample_weight + 9 пар *_min/*_max).
_CULTURE_UPDATE_COLUMNS: tuple[str, ...] = (
    "name", "sample_weight",
    "sp_min", "sp_max", "zp_min", "zp_max",
    "humidity_min", "humidity_max",
    "natura_min", "natura_max",
    "gluten_min", "gluten_max",
    "protein_min", "protein_max",
    "vitreousness_min", "vitreousness_max",
    "idc_min", "idc_max",
    "fall_number_min", "fall_number_max",
)


def save_culture(culture: Culture) -> None:
    """Сохраняет основные нормы культуры."""
    set_clause = ", ".join(f"{c}=?" for c in _CULTURE_UPDATE_COLUMNS)
    values = tuple(getattr(culture, c) for c in _CULTURE_UPDATE_COLUMNS) + (culture.id,)
    with get_connection() as conn:
        conn.execute(f"UPDATE cultures SET {set_clause} WHERE id=?", values)


def save_impurity_norm(norm: ImpurityNorm) -> None:
    """Сохраняет диапазон одной примеси."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE impurity_norms SET min_val=?, max_val=? WHERE id=?",
            (norm.min_val, norm.max_val, norm.id),
        )


def add_culture(name: str, sample_weight: float = 50.0) -> Culture:
    """Добавляет новую культуру с нулевыми нормами и всеми примесями."""
    from data.database import SP_IMPURITIES, ZP_IMPURITIES
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO cultures (name, sample_weight) VALUES (?, ?)",
            (name, sample_weight),
        )
        cid = cur.lastrowid

        # Все примеси одной пакетной вставкой
        impurities = (
            [(cid, "СП", imp) for imp in SP_IMPURITIES]
            + [(cid, "ЗП", imp) for imp in ZP_IMPURITIES]
        )
        conn.executemany(
            "INSERT INTO impurity_norms (culture_id, group_name, name) VALUES (?, ?, ?)",
            impurities,
        )
    return get_culture_with_norms(cid)


def delete_culture(culture_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM cultures WHERE id = ?", (culture_id,))


# ── Бюксы ─────────────────────────────────────────────────────────────────────

def get_all_boxes() -> list[Box]:
    """Возвращает все бюксы, отсортированные по числовому значению номера."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM boxes ORDER BY "
            "CASE WHEN number GLOB '[0-9]*' THEN 0 ELSE 1 END, "
            "CAST(number AS INTEGER), number"
        ).fetchall()
    return [Box(**dict(r)) for r in rows]


def get_boxes_by_type(box_type: str) -> list[Box]:
    """Возвращает бюксы заданного типа ('standard' или 'mesh')."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM boxes WHERE box_type=? ORDER BY "
            "CASE WHEN number GLOB '[0-9]*' THEN 0 ELSE 1 END, "
            "CAST(number AS INTEGER), number",
            (box_type,),
        ).fetchall()
    return [Box(**dict(r)) for r in rows]


def save_box(box: Box) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE boxes SET weight=? WHERE id=?",
            (box.weight, box.id),
        )


def add_box(number: str, weight: float, box_type: str = "standard") -> Box:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO boxes (number, weight, box_type) VALUES (?, ?, ?)",
            (number, weight, box_type),
        )
        return Box(id=cur.lastrowid, number=number, weight=weight, box_type=box_type)


def delete_box(box_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM boxes WHERE id = ?", (box_id,))


# ── Карточки ──────────────────────────────────────────────────────────────────


@dataclass
class Card:
    id:            int
    probe_number:  str
    culture_name:  str
    card_type:     str              # Перегонка / Входной контроль / Отгрузка / Очистка / Контроль при хранении
    silo_id:       Optional[int]    # None если не выбран или тип не требует
    origin_country: Optional[str]   # Только для Входного контроля: РБ / РФ
    harvest_year:  Optional[str]    # Только для Входного контроля: год урожая
    supplier:      Optional[str]    # Только для Входного контроля: поставщик
    created_at:    str
    sp_total:      float
    zp_total:      float
    sp_items:      list
    zp_items:      list
    humidity:      Optional[float]
    natura:        Optional[float]
    gluten:        Optional[float]   # Клейковина экспресс
    gluten_arb:    Optional[float]   # Клейковина арбитраж (П3, П4)
    protein:       Optional[float]
    vitreousness:  Optional[float]
    idc:           Optional[float]
    fall_number:   Optional[float]
    incoming_ctrl: bool
    consignee:          Optional[str]    # Только для Отгрузки: грузополучатель
    distillation_place: Optional[str]    # Только для Перегонки: место (Свинки/КРС/Мукомолка/Рыбы)
    # Поля входного контроля (None если не применялся)
    sp_base:       Optional[float]
    zp_base:       Optional[float]
    sp_divergence: Optional[float]
    zp_divergence: Optional[float]
    sp_items_base: Optional[list]
    zp_items_base: Optional[list]


def _row_to_card(row) -> Card:
    """Преобразует sqlite Row в Card, парся JSON-поля и приводя bool."""
    d = dict(row)
    # JSON-поля
    d["sp_items"] = json.loads(d["sp_items"])
    d["zp_items"] = json.loads(d["zp_items"])
    d["sp_items_base"] = json.loads(d["sp_items_base"]) if d.get("sp_items_base") else None
    d["zp_items_base"] = json.loads(d["zp_items_base"]) if d.get("zp_items_base") else None
    # Bool из 0/1
    d["incoming_ctrl"] = bool(d.get("incoming_ctrl", 0))
    return Card(**d)


def _dump_json(value: Optional[list]) -> Optional[str]:
    """JSON-сериализация с поддержкой None и кириллицы."""
    return json.dumps(value, ensure_ascii=False) if value else None


def save_card(
    probe_number: str,
    culture_name: str,
    sp_total: float,
    zp_total: float,
    sp_items: list,
    zp_items: list,
    params: dict,
    card_type: str = "Перегонка",
    silo_id: Optional[int] = None,
    origin_country: Optional[str] = None,
    harvest_year: Optional[str] = None,
    supplier: Optional[str] = None,
    incoming_ctrl: bool = False,
    consignee: Optional[str] = None,
    distillation_place: Optional[str] = None,
    sp_base: Optional[float] = None,
    zp_base: Optional[float] = None,
    sp_divergence: Optional[float] = None,
    zp_divergence: Optional[float] = None,
    sp_items_base: Optional[list] = None,
    zp_items_base: Optional[list] = None,
) -> Card:
    """Создаёт новую карточку в БД и возвращает её с присвоенным id."""
    columns: dict[str, object] = {
        "probe_number":   probe_number,
        "culture_name":   culture_name,
        "card_type":      card_type,
        "silo_id":        silo_id,
        "origin_country": origin_country,
        "harvest_year":   harvest_year,
        "supplier":       supplier,
        "sp_total":       sp_total,
        "zp_total":       zp_total,
        "sp_items":       json.dumps(sp_items, ensure_ascii=False),
        "zp_items":       json.dumps(zp_items, ensure_ascii=False),
        "humidity":       params.get("humidity"),
        "natura":         params.get("natura"),
        "gluten":         params.get("gluten_express"),
        "gluten_arb":     params.get("gluten_arb"),
        "protein":        params.get("protein"),
        "vitreousness":   params.get("vitreousness"),
        "idc":            params.get("idc"),
        "fall_number":    params.get("fall_number"),
        "incoming_ctrl":  int(incoming_ctrl),
        "consignee":           consignee,
        "distillation_place":  distillation_place,
        "sp_base":        sp_base,
        "zp_base":        zp_base,
        "sp_divergence":  sp_divergence,
        "zp_divergence":  zp_divergence,
        "sp_items_base":  _dump_json(sp_items_base),
        "zp_items_base":  _dump_json(zp_items_base),
    }
    cols = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    with get_connection() as conn:
        cur = conn.execute(
            f"INSERT INTO cards ({cols}) VALUES ({placeholders})",
            tuple(columns.values()),
        )
        cid = cur.lastrowid
    return get_card(cid)


# Маппинг культуры → (crop_name, crop_class) в силосах.
# crop_class="" означает совпадение только по crop_name (все классы).
_CULTURE_TO_SILO: dict[str, tuple[str, str]] = {
    "Пшеница 3 кл.":  ("Пшеница",   "3"),
    "Пшеница 4 кл.":  ("Пшеница",   "4"),
    "Пшеница корм.":  ("Пшеница",   "корм."),
    "Ячмень":         ("Ячмень",    "корм."),
    "Овёс":           ("Овёс",      "корм."),
    "Тритикале":      ("Тритикале", "корм."),
    "Кукуруза":       ("Кукуруза",  "3"),
}


def get_silos_for_culture(culture_name: str) -> list[Silo]:
    """
    Возвращает силоса, соответствующие культуре.
    Фильтрация по crop_name и crop_class из _CULTURE_TO_SILO.
    Силоса с пустым crop_name исключаются (не заполнены).
    """
    mapping = _CULTURE_TO_SILO.get(culture_name)
    with get_connection() as conn:
        if mapping:
            crop_name, crop_class = mapping
            rows = conn.execute(
                "SELECT * FROM silos WHERE crop_name=? AND crop_class=? "
                "ORDER BY CAST(number AS INTEGER), number",
                (crop_name, crop_class),
            ).fetchall()
        else:
            rows = []
    return [Silo(**dict(r)) for r in rows]


def get_card(card_id: int) -> Optional[Card]:
    """Возвращает карточку по id, None если не найдена."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        return _row_to_card(row) if row else None


def get_all_cards(
    culture_filter: str = "",
    probe_search: str = "",
    card_type_filter: str = "",
    date_from: str = "",   # ISO date "YYYY-MM-DD"
    date_to: str = "",     # ISO date "YYYY-MM-DD"
    silo_id_filter: Optional[int] = None,
    place_filter: str = "",
) -> list[Card]:
    """
    Возвращает все карточки в обратном хронологическом порядке (новые сверху).
    Поддерживает фильтрацию по культуре, типу, дате, силосу, месту перегонки
    и поиск по фрагменту номера пробы.
    """
    sql = "SELECT * FROM cards WHERE 1=1"
    args: list = []
    if culture_filter:
        sql += " AND culture_name=?"
        args.append(culture_filter)
    if probe_search:
        sql += " AND probe_number LIKE ?"
        args.append(f"%{probe_search}%")
    if card_type_filter:
        sql += " AND card_type=?"
        args.append(card_type_filter)
    if date_from:
        sql += " AND DATE(created_at) >= ?"
        args.append(date_from)
    if date_to:
        sql += " AND DATE(created_at) <= ?"
        args.append(date_to)
    if silo_id_filter is not None:
        sql += " AND silo_id=?"
        args.append(silo_id_filter)
    if place_filter:
        sql += " AND distillation_place=?"
        args.append(place_filter)
    sql += " ORDER BY id DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_row_to_card(r) for r in rows]


def delete_cards_bulk(card_ids: list[int]) -> None:
    """Удаляет несколько карточек за одну транзакцию."""
    if not card_ids:
        return
    placeholders = ",".join("?" * len(card_ids))
    with get_connection() as conn:
        conn.execute(f"DELETE FROM cards WHERE id IN ({placeholders})", card_ids)


def update_card_params(
    card_id: int,
    humidity:      Optional[float],
    natura:        Optional[float],
    gluten:        Optional[float],
    gluten_arb:    Optional[float],
    protein:       Optional[float],
    vitreousness:  Optional[float],
    idc:           Optional[float],
    fall_number:   Optional[float],
    sp_total:      float,
    sp_items:      list,
    zp_total:      float,
    zp_items:      list,
) -> None:
    """Обновляет показатели и примеси существующей карточки."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE cards SET
                humidity=?, natura=?, gluten=?, gluten_arb=?, protein=?,
                vitreousness=?, idc=?, fall_number=?,
                sp_total=?, sp_items=?, zp_total=?, zp_items=?
            WHERE id=?
        """, (
            humidity, natura, gluten, gluten_arb, protein,
            vitreousness, idc, fall_number,
            sp_total, json.dumps(sp_items, ensure_ascii=False),
            zp_total, json.dumps(zp_items, ensure_ascii=False),
            card_id,
        ))


def delete_card(card_id: int) -> None:
    """Удаляет карточку по id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM cards WHERE id=?", (card_id,))


def delete_all_cards() -> int:
    """Удаляет все карточки. Возвращает количество удалённых."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM cards")
    return cur.rowcount


# ── Силоса ────────────────────────────────────────────────────────────────────

@dataclass
class Silo:
    id:           int
    number:       str
    crop_name:    str
    crop_class:   str
    harvest_year: str
    origin:       str


def get_all_silos() -> list[Silo]:
    """Возвращает все силоса, отсортированные по числовому значению номера."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM silos ORDER BY CAST(number AS INTEGER)"
        ).fetchall()
    return [Silo(**dict(r)) for r in rows]


def save_silo(silo: Silo) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE silos SET crop_name=?, crop_class=?, harvest_year=?, origin=? WHERE id=?",
            (silo.crop_name, silo.crop_class, silo.harvest_year, silo.origin, silo.id),
        )


# ── Персонал ──────────────────────────────────────────────────────────────────

@dataclass
class Worker:
    id:       int
    name:     str
    position: str


@dataclass
class Shift:
    id:      int
    number:  int
    name:    str
    workers: list  # list[Worker]


def get_all_workers() -> list[Worker]:
    """Возвращает всех работников, отсортированных по имени."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM workers ORDER BY name").fetchall()
    return [Worker(**dict(r)) for r in rows]


def add_worker(name: str) -> Worker:
    """Добавляет работника, возвращает с присвоенным id."""
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO workers (name) VALUES (?)", (name,))
    return Worker(id=cur.lastrowid, name=name, position="")


def delete_worker(worker_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM workers WHERE id=?", (worker_id,))


def get_all_shifts() -> list[Shift]:
    """Возвращает все смены вместе с их составами, отсортированными по имени работника."""
    with get_connection() as conn:
        shifts = conn.execute("SELECT * FROM shifts ORDER BY number").fetchall()
        result = []
        for s in shifts:
            worker_rows = conn.execute("""
                SELECT w.* FROM workers w
                JOIN shift_workers sw ON sw.worker_id = w.id
                WHERE sw.shift_id = ?
                ORDER BY w.name
            """, (s["id"],)).fetchall()
            workers = [Worker(**dict(r)) for r in worker_rows]
            result.append(Shift(
                id=s["id"], number=s["number"], name=s["name"], workers=workers,
            ))
    return result


def set_shift_workers(shift_id: int, worker_ids: list[int]) -> None:
    """Полностью заменяет состав смены."""
    with get_connection() as conn:
        conn.execute("DELETE FROM shift_workers WHERE shift_id=?", (shift_id,))
        if worker_ids:
            conn.executemany(
                "INSERT OR IGNORE INTO shift_workers (shift_id, worker_id) VALUES (?, ?)",
                [(shift_id, wid) for wid in worker_ids],
            )


def rename_shift(shift_id: int, name: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE shifts SET name=? WHERE id=?", (name, shift_id))


# ── Акты ──────────────────────────────────────────────────────────────────────

@dataclass
class Act:
    id:         int
    number:     float       # например 268.2
    act_type:   str         # 'daily' | 'shift1' | 'shift2'
    created_at: str
    file_path:  Optional[str]
    shift_id:   Optional[int] = None    # id смены (для среднесуточных)
    shift_id2:  Optional[int] = None    # id второй смены (для входного)

    @property
    def number_str(self) -> str:
        """Номер в виде строки без лишних нулей: 268.2"""
        n = int(self.number)
        return f"{n}.2"

    @property
    def type_label(self) -> str:
        return {
            "daily":  "Входной",
            "shift1": "Дневная см.",
            "shift2": "Ночная см.",
        }.get(self.act_type, self.act_type)


def get_all_acts() -> list[Act]:
    """Возвращает все акты в порядке убывания номера."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM acts ORDER BY number DESC"
        ).fetchall()
    return [Act(**dict(r)) for r in rows]


def get_act(act_id: int) -> Optional[Act]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM acts WHERE id=?", (act_id,)).fetchone()
    return Act(**dict(row)) if row else None


def create_act(act_type: str, file_path: str, acts_dir: str = "",
                shift_id: Optional[int] = None,
                shift_id2: Optional[int] = None) -> Act:
    """Создаёт новый акт. Номер определяется исключительно по файлам в папке актов."""
    from logic.act_writer import get_max_act_number_from_dir
    max_num = get_max_act_number_from_dir(acts_dir)
    number = max_num + 1 + 0.2
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO acts (number, act_type, file_path, shift_id, shift_id2) "
            "VALUES (?, ?, ?, ?, ?)",
            (number, act_type, file_path, shift_id, shift_id2),
        )
    return get_act(cur.lastrowid)


def delete_act(act_id: int) -> None:
    """Удаляет акт и все связанные с ним пробы."""
    with get_connection() as conn:
        conn.execute("DELETE FROM act_probes WHERE act_id=?", (act_id,))
        conn.execute("DELETE FROM acts WHERE id=?", (act_id,))


def update_act_file_path(act_id: int, file_path: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE acts SET file_path=? WHERE id=?", (file_path, act_id))


def update_act_shift(act_id: int, shift_id: Optional[int]) -> None:
    """Обновляет привязку смены к акту."""
    with get_connection() as conn:
        conn.execute("UPDATE acts SET shift_id=? WHERE id=?", (shift_id, act_id))


def get_shift_by_id(shift_id: int) -> Optional[Shift]:
    """Возвращает смену по id вместе с её работниками."""
    if shift_id is None:
        return None
    with get_connection() as conn:
        s = conn.execute("SELECT * FROM shifts WHERE id=?", (shift_id,)).fetchone()
        if not s:
            return None
        worker_rows = conn.execute("""
            SELECT w.* FROM workers w
            JOIN shift_workers sw ON sw.worker_id = w.id
            WHERE sw.shift_id = ?
            ORDER BY w.name
        """, (shift_id,)).fetchall()
        workers = [Worker(**dict(r)) for r in worker_rows]
        return Shift(id=s["id"], number=s["number"], name=s["name"], workers=workers)


def get_act_probes(act_id: int) -> list[Card]:
    """Возвращает карточки добавленные в акт, в порядке row_num."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT c.* FROM cards c
            JOIN act_probes ap ON ap.card_id = c.id
            WHERE ap.act_id = ?
            ORDER BY ap.row_num
        """, (act_id,)).fetchall()
    return [_row_to_card(r) for r in rows]


def add_probe_to_act(act_id: int, card_id: int) -> int:
    """
    Добавляет пробу в акт. Возвращает порядковый номер строки (row_num).
    Если проба уже в акте — возвращает существующий row_num.
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT row_num FROM act_probes WHERE act_id=? AND card_id=?",
            (act_id, card_id),
        ).fetchone()
        if existing:
            return existing[0]
        max_row = conn.execute(
            "SELECT MAX(row_num) FROM act_probes WHERE act_id=?", (act_id,)
        ).fetchone()[0] or 0
        row_num = max_row + 1
        conn.execute(
            "INSERT INTO act_probes (act_id, card_id, row_num) VALUES (?, ?, ?)",
            (act_id, card_id, row_num),
        )
    return row_num


def get_cards_not_in_act(act_id: int, act_type: str = "daily") -> list[Card]:
    """
    Карточки ещё не добавленные в данный акт.
    Для «Входного» акта (daily) — только карточки типа «Входной контроль».
    Для остальных актов — все карточки кроме «Входной контроль».
    """
    with get_connection() as conn:
        if act_type == "daily":
            rows = conn.execute("""
                SELECT * FROM cards
                WHERE card_type = 'Входной контроль'
                AND id NOT IN (
                    SELECT card_id FROM act_probes WHERE act_id = ?
                )
                ORDER BY id DESC
            """, (act_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM cards
                WHERE card_type != 'Входной контроль'
                AND id NOT IN (
                    SELECT card_id FROM act_probes WHERE act_id = ?
                )
                ORDER BY id DESC
            """, (act_id,)).fetchall()
    return [_row_to_card(r) for r in rows]


# ── Настройки ─────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
