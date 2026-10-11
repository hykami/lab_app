"""
Загрузка и регистрация шрифтов.
JetBrains Mono — шапка, цифры, бейджи, метки разделов.
Inter          — меню, названия, подписи, поля ввода.

При недоступности сети приложение запускается со стандартными шрифтами
без каких-либо сообщений об ошибках.
"""

from __future__ import annotations

import io
import logging
import os
import urllib.request
import zipfile

from PyQt6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)

FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "fonts",
)

# Семейства шрифтов: URL архива → имена TTF-файлов внутри архива.
# Для каждого шрифта перечислены несколько URL — используется первый рабочий.
_FONT_SOURCES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (
        # JetBrains Mono — пробуем разные версии
        (
            "https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip",
            "https://github.com/JetBrains/JetBrainsMono/releases/download/v2.242/JetBrainsMono-2.242.zip",
        ),
        (
            "JetBrainsMono-Regular.ttf",
            "JetBrainsMono-Light.ttf",
            "JetBrainsMono-Medium.ttf",
        ),
    ),
    (
        # Inter — поставляется локально, URL не нужен (файлы уже в assets/fonts)
        (),
        (
            "Inter_18pt-Regular.ttf",
            "Inter_18pt-Medium.ttf",
            "Inter_18pt-SemiBold.ttf",
            "Inter_18pt-Bold.ttf",
            "Inter_18pt-Light.ttf",
        ),
    ),
]

_DOWNLOAD_TIMEOUT_S = 8


def _try_download(url: str) -> bytes | None:
    """Пытается скачать URL. При любой ошибке возвращает None (без исключений)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_S) as resp:
            return resp.read()
    except Exception:
        return None


def _extract_fonts(data: bytes, files_to_extract: list[str]) -> bool:
    """
    Извлекает шрифты из zip-архива в FONTS_DIR.
    Ищет файлы по basename — не важно в какой подпапке они лежат.
    Возвращает True если хотя бы один файл извлечён.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            extracted = 0
            for fname in files_to_extract:
                match = next((n for n in names if os.path.basename(n) == fname), None)
                if not match:
                    continue
                dest = os.path.join(FONTS_DIR, fname)
                with zf.open(match) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                extracted += 1
            return extracted > 0
    except Exception:
        return False


def download_fonts() -> None:
    """
    Скачивает шрифты в assets/fonts/ если их ещё нет.
    Работает только при первом запуске. При недоступности сети — тихо пропускает.
    Шрифты без URL (Inter) поставляются локально — скачивание пропускается.
    """
    os.makedirs(FONTS_DIR, exist_ok=True)

    for urls, font_files in _FONT_SOURCES:
        if not urls:
            # Шрифт поставляется локально — скачивание не требуется
            continue
        missing = [f for f in font_files if not os.path.exists(os.path.join(FONTS_DIR, f))]
        if not missing:
            continue

        for url in urls:
            data = _try_download(url)
            if data is None:
                continue
            if _extract_fonts(data, list(missing)):
                break
            # Данные скачались, но извлечь не удалось — пробуем следующий URL


def register_fonts() -> None:
    """Регистрирует все .ttf из assets/fonts/ в Qt."""
    if not os.path.isdir(FONTS_DIR):
        return
    for fname in os.listdir(FONTS_DIR):
        if fname.lower().endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(FONTS_DIR, fname))
