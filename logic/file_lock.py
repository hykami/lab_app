"""
Проверка доступности файла для записи.

Используется перед записью в Excel (.xlsx) и Word (.docx),
чтобы сообщить пользователю о занятом файле до начала операции.
"""

from __future__ import annotations

import os


class FileLockError(Exception):
    """Файл заблокирован или недоступен для записи."""


def check_file_writable(path: str) -> None:
    """
    Проверяет, что файл существует и доступен для записи прямо сейчас.

    Алгоритм:
      1. Файл существует?
      2. Флаг «~$» (временный lock-файл Office) рядом с файлом?
      3. Файл можно открыть на запись (os.open с O_WRONLY | O_EXCL не нужен —
         достаточно попытки open(..., 'r+b') без чтения)?

    Если что-то не так — бросает FileLockError с понятным сообщением.
    """
    if not path:
        raise FileLockError("Путь к файлу не указан.")

    if not os.path.exists(path):
        raise FileLockError(
            f"Файл не найден:\n{path}\n\n"
            "Проверьте путь в настройках."
        )

    # Проверка lock-файла Office (~$имяфайла)
    directory = os.path.dirname(os.path.abspath(path))
    basename  = os.path.basename(path)
    lock_name = "~$" + basename
    lock_path = os.path.join(directory, lock_name)
    if os.path.exists(lock_path):
        raise FileLockError(
            f"Файл открыт в другой программе или на другом компьютере:\n{path}\n\n"
            "Закройте файл и повторите операцию."
        )

    # Попытка открыть файл на запись (без изменений)
    try:
        fh = open(path, "r+b")
        fh.close()
    except PermissionError:
        raise FileLockError(
            f"Нет доступа к файлу для записи:\n{path}\n\n"
            "Возможно, файл открыт на другом компьютере или защищён от записи.\n"
            "Закройте файл и повторите операцию."
        )
    except OSError as exc:
        raise FileLockError(
            f"Не удалось получить доступ к файлу:\n{path}\n\n"
            f"Системная ошибка: {exc}"
        )
