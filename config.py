"""
Конфигурация приложения.
Настройки хранятся в config.json рядом с main.py и
загружаются/сохраняются через класс AppConfig.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS: dict[str, Any] = {
    "excel_path": "",          # путь к Excel-файлу (задаётся в Настройках)
    "theme": "dark",           # зарезервировано на будущее
}


class AppConfig:
    """Простое хранилище настроек с автосохранением в JSON."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {**DEFAULTS}
        self._load()

    # ── Публичный интерфейс ───────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    # ── Быстрые свойства ─────────────────────────────────────────────────────

    @property
    def excel_path(self) -> str:
        return self._data.get("excel_path", "")

    @excel_path.setter
    def excel_path(self, path: str) -> None:
        self.set("excel_path", path)

    # ── Внутренние методы ────────────────────────────────────────────────────

    def _load(self) -> None:
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self._data.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            logger.warning(
                "Не удалось прочитать %s, используем дефолты", CONFIG_PATH,
                exc_info=True,
            )

    def _save(self) -> None:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            # Запись не удалась — настройки не сохранятся между запусками.
            logger.warning("Не удалось сохранить %s", CONFIG_PATH, exc_info=True)


# Глобальный синглтон — импортируется во всех модулях
config = AppConfig()
