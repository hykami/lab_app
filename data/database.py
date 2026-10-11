"""
Инициализация SQLite базы данных.
Файл БД: data/lab_app.db
"""

from __future__ import annotations

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab_app.db")


def get_connection() -> sqlite3.Connection:
    """Возвращает соединение к БД. Внешние ключи и Row-фабрика включены."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Хелперы миграций ──────────────────────────────────────────────────────────

def _get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Возвращает множество имён колонок таблицы."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_missing_columns(
    conn: sqlite3.Connection,
    table: str,
    columns: list[tuple[str, str]],
) -> None:
    """
    Добавляет недостающие колонки в таблицу.
    columns — список пар (имя_колонки, SQL-определение).
    """
    existing = _get_columns(conn, table)
    for col, definition in columns:
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")


def _is_migration_done(conn: sqlite3.Connection, name: str) -> bool:
    """Проверяет, выполнялась ли уже одноразовая миграция."""
    return conn.execute(
        "SELECT 1 FROM migrations WHERE name = ?", (name,)
    ).fetchone() is not None


def _mark_migration_done(conn: sqlite3.Connection, name: str) -> None:
    """Помечает миграцию выполненной."""
    conn.execute(
        "INSERT OR IGNORE INTO migrations (name) VALUES (?)", (name,)
    )


def _table_is_empty(conn: sqlite3.Connection, table: str) -> bool:
    """True если таблица не содержит ни одной строки."""
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def init_db() -> None:
    """Создаёт таблицы и заполняет дефолтными данными если БД пустая."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cultures (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL UNIQUE,
                sample_weight REAL    NOT NULL DEFAULT 50,
                sp_min        REAL    NOT NULL DEFAULT 0,
                sp_max        REAL    NOT NULL DEFAULT 0,
                zp_min        REAL    NOT NULL DEFAULT 0,
                zp_max        REAL    NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS impurity_norms (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                culture_id INTEGER NOT NULL REFERENCES cultures(id) ON DELETE CASCADE,
                group_name TEXT    NOT NULL,
                name       TEXT    NOT NULL,
                min_val    REAL    NOT NULL DEFAULT 0,
                max_val    REAL    NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS boxes (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                number   TEXT    NOT NULL,
                weight   REAL    NOT NULL,
                box_type TEXT    NOT NULL DEFAULT 'standard',
                UNIQUE(number, box_type)
            );

            CREATE TABLE IF NOT EXISTS silos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                number       TEXT    NOT NULL UNIQUE,
                crop_name    TEXT    NOT NULL DEFAULT '',
                crop_class   TEXT    NOT NULL DEFAULT '',
                harvest_year TEXT    NOT NULL DEFAULT '',
                origin       TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS cards (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                probe_number   TEXT    NOT NULL,
                culture_name   TEXT    NOT NULL,
                card_type      TEXT    NOT NULL DEFAULT 'Перегонка',
                silo_id        INTEGER REFERENCES silos(id) ON DELETE SET NULL,
                origin_country TEXT,
                harvest_year   TEXT,
                supplier       TEXT,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                sp_total       REAL    NOT NULL DEFAULT 0,
                zp_total       REAL    NOT NULL DEFAULT 0,
                sp_items       TEXT    NOT NULL DEFAULT '[]',
                zp_items       TEXT    NOT NULL DEFAULT '[]',
                humidity       REAL,
                natura         REAL,
                gluten         REAL,
                gluten_arb     REAL,
                protein        REAL,
                vitreousness   REAL,
                idc            REAL,
                fall_number    REAL,
                incoming_ctrl  INTEGER NOT NULL DEFAULT 0,
                sp_base        REAL,
                zp_base        REAL,
                sp_divergence  REAL,
                zp_divergence  REAL,
                sp_items_base  TEXT,
                zp_items_base  TEXT
            );

            CREATE TABLE IF NOT EXISTS acts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                number     REAL    NOT NULL UNIQUE,   -- например 268.2
                act_type   TEXT    NOT NULL,           -- 'daily' / 'shift1' / 'shift2'
                created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                file_path  TEXT                        -- путь к Word-файлу
            );

            CREATE TABLE IF NOT EXISTS act_probes (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                act_id   INTEGER NOT NULL REFERENCES acts(id) ON DELETE CASCADE,
                card_id  INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                row_num  INTEGER NOT NULL,             -- порядковый номер строки в таблице
                UNIQUE(act_id, card_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS migrations (
                name TEXT PRIMARY KEY
            );
        """)

        # Миграция: добавляем card_type и silo_id если их нет
        _add_missing_columns(conn, "cards", [
            ("card_type",      "TEXT NOT NULL DEFAULT 'Перегонка'"),
            ("silo_id",        "INTEGER REFERENCES silos(id) ON DELETE SET NULL"),
            ("origin_country", "TEXT"),
            ("harvest_year",   "TEXT"),
            ("supplier",       "TEXT"),
        ])

        # Миграция: добавляем колонки грузополучателя и места перегонки
        _add_missing_columns(conn, "cards", [
            ("consignee",          "TEXT"),
            ("distillation_place", "TEXT"),
        ])

        # Миграция: добавляем shift_id в acts (для привязки смены работников)
        _add_missing_columns(conn, "acts", [
            ("shift_id",  "INTEGER REFERENCES shifts(id) ON DELETE SET NULL"),
            ("shift_id2", "INTEGER REFERENCES shifts(id) ON DELETE SET NULL"),
        ])

        # Миграция: добавляем колонки входного контроля если их нет
        _add_missing_columns(conn, "cards", [
            ("sp_base",       "REAL"),
            ("zp_base",       "REAL"),
            ("sp_divergence", "REAL"),
            ("zp_divergence", "REAL"),
            ("sp_items_base", "TEXT"),
            ("zp_items_base", "TEXT"),
            ("gluten_arb",    "REAL"),
        ])

        # Миграция: добавляем колонки норм показателей в cultures
        _add_missing_columns(conn, "cultures", [
            ("humidity_min",     "REAL DEFAULT 8.0"),
            ("humidity_max",     "REAL DEFAULT 18.0"),
            ("natura_min",       "REAL DEFAULT 650.0"),
            ("natura_max",       "REAL DEFAULT 850.0"),
            ("gluten_min",       "REAL DEFAULT 18.0"),
            ("gluten_max",       "REAL DEFAULT 36.0"),
            ("protein_min",      "REAL DEFAULT 10.0"),
            ("protein_max",      "REAL DEFAULT 18.0"),
            ("vitreousness_min", "REAL DEFAULT 30.0"),
            ("vitreousness_max", "REAL DEFAULT 95.0"),
            ("idc_min",          "REAL DEFAULT 45.0"),
            ("idc_max",          "REAL DEFAULT 105.0"),
            ("fall_number_min",  "REAL DEFAULT 150.0"),
            ("fall_number_max",  "REAL DEFAULT 450.0"),
        ])

        # Миграция: пересоздаём таблицу силосов до новой схемы (одноразово)
        if "crop_name" not in _get_columns(conn, "silos"):
            conn.execute("DROP TABLE IF EXISTS silos")
            conn.execute("""
                CREATE TABLE silos (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    number       TEXT    NOT NULL UNIQUE,
                    crop_name    TEXT    NOT NULL DEFAULT '',
                    crop_class   TEXT    NOT NULL DEFAULT '',
                    harvest_year TEXT    NOT NULL DEFAULT '',
                    origin       TEXT    NOT NULL DEFAULT ''
                )
            """)

        # Заполняем силосы если таблица пустая
        if _table_is_empty(conn, "silos"):
            _seed_silos(conn)

        # Создаём таблицы персонала
        _create_personnel_tables(conn)

        # Миграция: удаляем "Дикие" (СП) и "Другие" (ЗП) из норм Кукурузы
        if not _is_migration_done(conn, "remove_corn_impurities"):
            conn.execute("""
                DELETE FROM impurity_norms
                WHERE name IN ('Дикие', 'Другие')
                AND culture_id = (SELECT id FROM cultures WHERE name = 'Кукуруза')
            """)
            _mark_migration_done(conn, "remove_corn_impurities")

        # Миграция: удаляем Раздутые и Морозобойные если они есть (одноразово)
        if not _is_migration_done(conn, "remove_legacy_impurities"):
            conn.execute(
                "DELETE FROM impurity_norms WHERE name IN ('Раздутые', 'Морозобойные')"
            )
            _mark_migration_done(conn, "remove_legacy_impurities")

        # Заполняем культуры если таблица пустая
        if _table_is_empty(conn, "cultures"):
            _seed_cultures(conn)

        # Миграция: пересоздаём таблицу boxes с UNIQUE(number, box_type)
        # вместо старого UNIQUE(number) — это позволяет иметь одинаковые
        # номера у обычных и сетчатых бюкс.
        if not _is_migration_done(conn, "boxes_unique_number_type"):
            conn.execute("""
                CREATE TABLE boxes_new (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    number   TEXT    NOT NULL,
                    weight   REAL    NOT NULL,
                    box_type TEXT    NOT NULL DEFAULT 'standard',
                    UNIQUE(number, box_type)
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO boxes_new (id, number, weight, box_type)
                SELECT id, number, weight, COALESCE(box_type, 'standard')
                FROM boxes
            """)
            conn.execute("DROP TABLE boxes")
            conn.execute("ALTER TABLE boxes_new RENAME TO boxes")
            _mark_migration_done(conn, "boxes_unique_number_type")

        # Заполняем бюксы если таблица пустая
        if _table_is_empty(conn, "boxes"):
            _seed_boxes(conn)

        # Миграция: заполняем нулевые значения примесей — после seed_cultures!
        _seed_impurity_values(conn)

        # Миграция: добавляем культуру «Отходы» если её ещё нет
        if not _is_migration_done(conn, "add_waste_culture"):
            exists = conn.execute(
                "SELECT 1 FROM cultures WHERE name = 'Отходы'"
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO cultures (name, sample_weight, sp_min, sp_max, zp_min, zp_max) "
                    "VALUES ('Отходы', 10, 0, 5.0, 0, 10.0)"
                )
                cid = conn.execute(
                    "SELECT id FROM cultures WHERE name = 'Отходы'"
                ).fetchone()["id"]
                for imp in SP_IMPURITIES:
                    conn.execute(
                        "INSERT INTO impurity_norms (culture_id, group_name, name, min_val, max_val) "
                        "VALUES (?, 'СП', ?, 0, 1.50)", (cid, imp),
                    )
                for imp in ZP_IMPURITIES:
                    conn.execute(
                        "INSERT INTO impurity_norms (culture_id, group_name, name, min_val, max_val) "
                        "VALUES (?, 'ЗП', ?, 0, 1.50)", (cid, imp),
                    )
            _mark_migration_done(conn, "add_waste_culture")


# ── Дефолтные данные ──────────────────────────────────────────────────────────

SP_IMPURITIES = [
    "Крупная СП",
    "Проход",
    "Органика",
    "Минеральная",
    "Дикие",
    "Испорченные",
    "Выеденные",
    "Фузариозные",
]

ZP_IMPURITIES = [
    "Битые",
    "Давленные",
    "Щуплые",
    "Проросшие",
    "Изъеденные",
    "Поврежденные",
    "Зелёные",
    "Другие",
]

DEFAULT_CULTURES = [
    # (name, sample_weight, sp_min, sp_max, zp_min, zp_max)
    ("Пшеница 3 кл.", 50,  0, 2.0, 0, 5.0),
    ("Пшеница 4 кл.", 50,  0, 3.0, 0, 7.0),
    ("Пшеница корм.", 50,  0, 5.0, 0, 15.0),
    ("Кукуруза",      100, 0, 3.0, 0, 15.0),
    ("Ячмень",        50,  0, 2.0, 0, 7.0),
    ("Овёс",          50,  0, 3.0, 0, 7.0),
    ("Тритикале",     50,  0, 3.0, 0, 7.0),
    ("Отходы",        10,  0, 5.0, 0, 10.0),
]


def _seed_cultures(conn: sqlite3.Connection) -> None:
    for name, sw, sp_min, sp_max, zp_min, zp_max in DEFAULT_CULTURES:
        conn.execute(
            "INSERT INTO cultures (name, sample_weight, sp_min, sp_max, zp_min, zp_max) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, sw, sp_min, sp_max, zp_min, zp_max),
        )
        cid = conn.execute(
            "SELECT id FROM cultures WHERE name = ?", (name,)
        ).fetchone()["id"]

        for imp in SP_IMPURITIES:
            conn.execute(
                "INSERT INTO impurity_norms (culture_id, group_name, name, min_val, max_val) "
                "VALUES (?, 'СП', ?, 0, 0)",
                (cid, imp),
            )
        for imp in ZP_IMPURITIES:
            conn.execute(
                "INSERT INTO impurity_norms (culture_id, group_name, name, min_val, max_val) "
                "VALUES (?, 'ЗП', ?, 0, 0)",
                (cid, imp),
            )


DEFAULT_BOXES = [
    ("1",  15.44), ("2",  15.42), ("3",  15.34), ("4",  15.54),
    ("5",  15.53), ("6",  15.48), ("7",  15.39), ("8",  15.48),
    ("9",  15.44), ("10", 15.51), ("11", 15.37), ("12", 15.43),
    ("13", 15.60), ("14", 15.48), ("15", 15.53), ("16", 15.40),
    ("17", 15.12), ("18", 15.50), ("19", 15.54), ("20", 15.49),
    ("21", 15.38), ("22", 15.53), ("23", 15.49),
]


def _seed_boxes(conn: sqlite3.Connection) -> None:
    for number, weight in DEFAULT_BOXES:
        conn.execute(
            "INSERT INTO boxes (number, weight) VALUES (?, ?)",
            (number, weight),
        )


def _seed_impurity_values(conn: sqlite3.Connection) -> None:
    """
    Проставляет min=0.00, max=1.50 всем примесям у которых max_val = 0.
    Выполняется один раз — флаг 'impurity_defaults_1.50' в migrations.
    """
    if _is_migration_done(conn, "impurity_defaults_1.50"):
        return
    conn.execute(
        "UPDATE impurity_norms SET min_val = 0.00, max_val = 1.50 "
        "WHERE max_val = 0"
    )
    _mark_migration_done(conn, "impurity_defaults_1.50")

# Данные силосов (импортированы из silos.db)
DEFAULT_SILOS = [
    # Демонстрационные данные для публичной версии проекта.
    ("1", "Пшеница", "3", "2025", "Пример"),
    ("2", "Ячмень", "корм.", "2025", "Пример"),
    ("3", "Кукуруза", "3", "2025", "Пример"),
    ("4", "Овёс", "корм.", "2025", "Пример"),
    ("5", "Тритикале", "3", "2025", "Пример"),
]


def _seed_silos(conn: sqlite3.Connection) -> None:
    for number, crop_name, crop_class, harvest_year, origin in DEFAULT_SILOS:
        conn.execute(
            "INSERT OR IGNORE INTO silos (number, crop_name, crop_class, harvest_year, origin) "
            "VALUES (?, ?, ?, ?, ?)",
            (number, crop_name, crop_class, harvest_year, origin),
        )


def _create_personnel_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workers (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL UNIQUE,
            position TEXT    NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS shifts (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER NOT NULL UNIQUE CHECK(number BETWEEN 1 AND 4),
            name   TEXT    NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS shift_workers (
            shift_id  INTEGER NOT NULL REFERENCES shifts(id)  ON DELETE CASCADE,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            PRIMARY KEY (shift_id, worker_id)
        );
    """)
    # Создаём 4 смены если их нет
    for n in range(1, 5):
        conn.execute(
            "INSERT OR IGNORE INTO shifts (number, name) VALUES (?, ?)",
            (n, f"Смена {n}"),
        )

    # Сидируем тестовых работников и распределение по сменам — одноразово.
    # Делаем только если таблица workers пустая, чтобы не затирать
    # реальные данные пользователя.
    if _table_is_empty(conn, "workers"):
        _seed_test_personnel(conn)


def _seed_test_personnel(conn: sqlite3.Connection) -> None:
    """
    Добавляет 12 тестовых работников и распределяет их по 4 сменам
    (по 3 человека). Вызывается только если таблица workers пуста.
    """
    shifts_workers: list[tuple[int, list[str]]] = [
        (1, ["Сотрудник 01", "Сотрудник 02", "Сотрудник 03"]),
        (2, ["Сотрудник 04", "Сотрудник 05", "Сотрудник 06"]),
        (3, ["Сотрудник 07", "Сотрудник 08", "Сотрудник 09"]),
        (4, ["Сотрудник 10", "Сотрудник 11", "Сотрудник 12"]),
    ]

    for shift_number, names in shifts_workers:
        # Получаем shift_id по номеру
        row = conn.execute(
            "SELECT id FROM shifts WHERE number=?", (shift_number,)
        ).fetchone()
        if not row:
            continue
        shift_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]

        for name in names:
            cur = conn.execute(
                "INSERT OR IGNORE INTO workers (name) VALUES (?)", (name,)
            )
            # Получаем id (если уже был — INSERT IGNORE, lastrowid = 0)
            if cur.lastrowid:
                worker_id = cur.lastrowid
            else:
                wrow = conn.execute(
                    "SELECT id FROM workers WHERE name=?", (name,)
                ).fetchone()
                worker_id = wrow["id"] if isinstance(wrow, sqlite3.Row) else wrow[0]

            conn.execute(
                "INSERT OR IGNORE INTO shift_workers (shift_id, worker_id) VALUES (?, ?)",
                (shift_id, worker_id),
            )
