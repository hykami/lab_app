"""
Настройки → Основные.
Пути к файлам и резервное копирование БД.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.theme import (
    BG_CARD, BORDER, TEXT_MUTED, TEXT_BRIGHT,
    ACCENT_G, ACCENT_R, ACCENT_ICON, FONT_MONO, FONT_UI,
)
from config import config
from logic.db_service import get_setting, set_setting, delete_all_cards, get_all_cards
from data.database import DB_PATH

logger = logging.getLogger(__name__)


# ── Вспомогательный виджет: строка настройки с меткой, полем и кнопкой ──────

class _PathRow(QWidget):
    """Строка: метка + поле ввода пути + кнопка Обзор."""

    def __init__(self, label: str, placeholder: str,
                 value: str = "", file_mode: bool = False,
                 file_filter: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._file_mode = file_mode      # True = файл, False = папка
        self._file_filter = file_filter
        self.setStyleSheet("background: transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: #707085; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; font-weight: 500; background: transparent; border: none;"
        )
        lay.addWidget(lbl)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._inp = QLineEdit(value)
        self._inp.setPlaceholderText(placeholder)
        self._inp.setFixedHeight(30)
        self._inp.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_CARD}; border: 0.5px solid {BORDER};
                border-radius: 7px; color: {TEXT_MUTED};
                font-family: '{FONT_MONO}', monospace; font-size: 12px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{ border-color: rgba(108,92,231,0.5); }}
        """)
        row.addWidget(self._inp, 1)

        browse = QPushButton("Обзор…")
        browse.setFixedHeight(30)
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD}; border: 0.5px solid {BORDER};
                border-radius: 7px; color: {TEXT_MUTED};
                font-family: '{FONT_UI}', sans-serif; font-size: 12px;
                padding: 0 14px;
            }}
            QPushButton:hover {{ border-color: rgba(108,92,231,0.4); }}
        """)
        browse.clicked.connect(self._on_browse)
        row.addWidget(browse)

        lay.addLayout(row)

    def _on_browse(self) -> None:
        current = self._inp.text() or os.path.expanduser("~")
        if self._file_mode:
            path, _ = QFileDialog.getOpenFileName(
                self, "Выберите файл", current, self._file_filter,
            )
        else:
            path = QFileDialog.getExistingDirectory(
                self, "Выберите папку", current,
            )
        if path:
            self._inp.setText(path)

    @property
    def value(self) -> str:
        return self._inp.text().strip()

    def set_value(self, v: str) -> None:
        self._inp.setText(v)


# ── Страница ──────────────────────────────────────────────────────────────────

class GeneralSettingsPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Основные",
            subtitle="",
            section="Настройки",
            actions=[("Сохранить", True)],
        )
        self._build_ui()

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # ── Пути к файлам ─────────────────────────────────────────────────────
        self._section_label("ПУТИ К ФАЙЛАМ")

        paths_card = self._card()
        cl = QVBoxLayout(paths_card)
        cl.setContentsMargins(16, 14, 16, 16)
        cl.setSpacing(12)

        self._excel_row = _PathRow(
            label="Excel-файл (для КРС/Свинки и Мукомолки)",
            placeholder="Путь к .xlsx файлу",
            value=config.excel_path,
            file_mode=True,
            file_filter="Excel файлы (*.xlsx *.xls)",
        )
        cl.addWidget(self._excel_row)

        self._acts_row = _PathRow(
            label="Папка для актов",
            placeholder="Путь к папке сохранения актов",
            value=get_setting("acts_dir"),
            file_mode=False,
        )
        cl.addWidget(self._acts_row)

        self._content_layout.addWidget(paths_card)

        # ── Резервные копии Excel ─────────────────────────────────────────────
        self._section_label("РЕЗЕРВНЫЕ КОПИИ EXCEL")

        excel_bk_card = self._card()
        ebl = QVBoxLayout(excel_bk_card)
        ebl.setContentsMargins(16, 14, 16, 16)
        ebl.setSpacing(12)

        self._excel_backup_row = _PathRow(
            label="Папка для резервных копий Excel",
            placeholder="Путь к папке для хранения копий",
            value=get_setting("excel_backup_dir"),
            file_mode=False,
        )
        ebl.addWidget(self._excel_backup_row)

        # Описание
        hint = QLabel("Копия Excel-файла создаётся автоматически при каждом добавлении пробы.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: #5a5a72; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        ebl.addWidget(hint)

        # Кнопка очистки
        ebtn_row = QHBoxLayout()
        ebtn_row.setContentsMargins(0, 0, 0, 0)
        ebtn_row.setSpacing(12)

        self._excel_backup_clear_btn = QPushButton("Очистить папку с копиями")
        self._excel_backup_clear_btn.setFixedHeight(32)
        self._excel_backup_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._excel_backup_clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(248,113,113,0.07);
                border: 0.5px solid rgba(248,113,113,0.3);
                border-radius: 7px; color: #f87171;
                font-family: '{FONT_UI}', sans-serif; font-size: 12px;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background: rgba(248,113,113,0.14); border-color: rgba(248,113,113,0.5); }}
            QPushButton:disabled {{ opacity: 0.35; }}
        """)
        self._excel_backup_clear_btn.clicked.connect(self._on_clear_excel_backups)
        ebtn_row.addWidget(self._excel_backup_clear_btn)

        self._excel_backup_status = QLabel("")
        self._excel_backup_status.setStyleSheet(
            f"color: #5a5a72; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; border: none;"
        )
        ebtn_row.addWidget(self._excel_backup_status, 1)
        ebl.addLayout(ebtn_row)

        self._content_layout.addWidget(excel_bk_card)
        self._refresh_excel_backup_status()

        # ── Резервная копия БД ────────────────────────────────────────────────
        self._section_label("РЕЗЕРВНАЯ КОПИЯ БАЗЫ ДАННЫХ")

        backup_card = self._card()
        bl = QVBoxLayout(backup_card)
        bl.setContentsMargins(16, 14, 16, 16)
        bl.setSpacing(12)

        # Папка для резервных копий
        self._backup_row = _PathRow(
            label="Папка для резервных копий",
            placeholder="Путь к папке для хранения копий",
            value=get_setting("backup_dir"),
            file_mode=False,
        )
        bl.addWidget(self._backup_row)

        # Кнопка + статус последней копии
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(12)

        self._backup_btn = QPushButton("Создать резервную копию")
        self._backup_btn.setFixedHeight(32)
        self._backup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._backup_btn.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD}; border: 0.5px solid {BORDER};
                border-radius: 7px; color: {TEXT_MUTED};
                font-family: '{FONT_UI}', sans-serif; font-size: 13px;
                padding: 0 18px;
            }}
            QPushButton:hover {{ border-color: rgba(108,92,231,0.4); color: {TEXT_BRIGHT}; }}
        """)
        self._backup_btn.clicked.connect(self._on_backup)
        btn_row.addWidget(self._backup_btn)

        self._backup_status = QLabel("")
        self._backup_status.setStyleSheet(
            f"color: #5a5a72; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent;"
        )
        btn_row.addWidget(self._backup_status, 1)
        bl.addLayout(btn_row)

        # Показываем время последней копии если есть
        last = get_setting("last_backup")
        if last:
            self._backup_status.setText(f"Последняя копия: {last}")

        self._content_layout.addWidget(backup_card)

        # ── Очистить карточки ─────────────────────────────────────────────────
        self._section_label("ОЧИСТИТЬ КАРТОЧКИ")

        clear_card = self._card()
        clear_card.setMaximumWidth(10000)
        ccl = QVBoxLayout(clear_card)
        ccl.setContentsMargins(16, 14, 16, 16)
        ccl.setSpacing(10)

        # Статистика
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        stats_row.setContentsMargins(0, 0, 0, 0)

        def _stat_cell(label: str, value: str, colored: bool = False) -> QFrame:
            cell = QFrame()
            cell.setStyleSheet(
                "QFrame { background: #111114; border: 0.5px solid #1e1e22; border-radius: 8px; }"
            )
            lay = QVBoxLayout(cell)
            lay.setContentsMargins(14, 10, 14, 12)
            lay.setSpacing(3)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent; border: none;"
            )
            lay.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(
                f"color: {ACCENT_ICON if colored else TEXT_MUTED};"
                f"font-family: '{FONT_UI}', sans-serif;"
                "font-size: 22px; font-weight: 300; background: transparent; border: none;"
            )
            lay.addWidget(val)
            cell._value_lbl = val
            return cell

        self._cc_stat_count    = _stat_cell("КАРТОЧЕК", "0", colored=True)
        self._cc_stat_cultures = _stat_cell("КУЛЬТУР", "0")
        self._cc_stat_last     = _stat_cell("ПОСЛЕДНЯЯ", "—")
        stats_row.addWidget(self._cc_stat_count)
        stats_row.addWidget(self._cc_stat_cultures)
        stats_row.addWidget(self._cc_stat_last)
        stats_w = QWidget()
        stats_w.setStyleSheet("background: transparent; border: none;")
        stats_w.setLayout(stats_row)
        ccl.addWidget(stats_w)

        # Подтверждение + кнопка
        confirm = QWidget()
        confirm.setStyleSheet(
            "background: rgba(248,113,113,0.04);"
            "border: 0.5px solid rgba(248,113,113,0.15);"
            "border-radius: 8px;"
        )
        conf_lay = QHBoxLayout(confirm)
        conf_lay.setContentsMargins(14, 10, 10, 10)
        conf_lay.setSpacing(12)

        self._cc_confirm_lbl = QLabel("Нет карточек для удаления.")
        self._cc_confirm_lbl.setWordWrap(True)
        self._cc_confirm_lbl.setStyleSheet(
            "color: rgba(248,113,113,0.5); font-family: '"
            f"{FONT_UI}', sans-serif; font-size: 12px;"
            "background: transparent; border: none; line-height: 1.5;"
        )
        conf_lay.addWidget(self._cc_confirm_lbl, 1)

        self._cc_btn = QPushButton("Удалить все")
        self._cc_btn.setFixedHeight(34)
        self._cc_btn.setFixedWidth(120)
        self._cc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cc_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(248,113,113,0.1);
                border: 0.5px solid rgba(248,113,113,0.4);
                border-radius: 7px;
                color: #f87171;
                font-family: '{FONT_UI}', sans-serif;
                font-size: 12px;
                letter-spacing: 0.04em;
            }}
            QPushButton:hover {{ background: rgba(248,113,113,0.18); }}
            QPushButton:disabled {{ opacity: 0.3; }}
        """)
        self._cc_btn.clicked.connect(self._on_clear_cards)
        conf_lay.addWidget(self._cc_btn)
        ccl.addWidget(confirm)

        self._content_layout.addWidget(clear_card)
        self._cc_refresh()

        # Кнопка Сохранить — в actions хедера
        self._save_btn = self._action_buttons["Сохранить"]
        self._save_btn.clicked.connect(self._on_save)

        self._content_layout.addStretch()

    def _section_label(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; background: transparent;"
        )
        self._content_layout.addWidget(lbl)

    def _card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}"
        )
        return f

    def _on_save(self) -> None:
        config.excel_path = self._excel_row.value
        set_setting("acts_dir", self._acts_row.value)
        set_setting("excel_backup_dir", self._excel_backup_row.value)
        set_setting("backup_dir", self._backup_row.value)
        self._refresh_excel_backup_status()
        self._save_btn.flash_success()

    def _on_backup(self) -> None:
        backup_dir = self._backup_row.value
        if not backup_dir:
            self._backup_status.setText("⚠ Укажите папку для резервных копий")
            self._backup_status.setStyleSheet(
                f"color: #f87171; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent;"
            )
            return

        if not os.path.isdir(backup_dir):
            try:
                os.makedirs(backup_dir, exist_ok=True)
            except OSError as e:
                self._backup_status.setText(f"⚠ Не удалось создать папку: {e}")
                return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        dest = os.path.join(backup_dir, f"lab_app_backup_{timestamp}.db")

        try:
            shutil.copy2(DB_PATH, dest)
            now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
            set_setting("last_backup", now_str)
            self._backup_status.setText(f"✓ Сохранено: {os.path.basename(dest)}")
            self._backup_status.setStyleSheet(
                f"color: {ACCENT_G}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent;"
            )
            logger.info("Резервная копия создана: %s", dest)
        except Exception:
            logger.exception("Ошибка создания резервной копии")
            self._backup_status.setText("⚠ Ошибка при создании копии")
            self._backup_status.setStyleSheet(
                f"color: {ACCENT_R}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent;"
            )

    def _refresh_excel_backup_status(self) -> None:
        d = get_setting("excel_backup_dir") or ""
        if not d or not os.path.isdir(d):
            self._excel_backup_status.setText("")
            return
        files = [f for f in os.listdir(d) if f.endswith((".xlsx", ".xls"))]
        if files:
            self._excel_backup_status.setText(f"{len(files)} файл(ов) в папке")
        else:
            self._excel_backup_status.setText("Папка пуста")

    def _on_clear_excel_backups(self) -> None:
        d = get_setting("excel_backup_dir") or ""
        if not d or not os.path.isdir(d):
            self._excel_backup_status.setText("Папка не задана или не найдена")
            return
        files = [f for f in os.listdir(d) if f.endswith((".xlsx", ".xls"))]
        if not files:
            self._excel_backup_status.setText("Папка уже пуста")
            return
        deleted = 0
        for f in files:
            try:
                os.remove(os.path.join(d, f))
                deleted += 1
            except Exception:
                pass
        self._excel_backup_status.setText(f"Удалено {deleted} файл(ов)")
        self._excel_backup_clear_btn.setText("✓ Очищено")
        QTimer.singleShot(3000, lambda: (
            self._excel_backup_clear_btn.setText("Очистить папку с копиями"),
            self._refresh_excel_backup_status(),
        ))

    def _cc_refresh(self) -> None:
        cards = get_all_cards()
        count = len(cards)
        self._cc_stat_count._value_lbl.setText(str(count))
        cultures = len({c.culture_name for c in cards})
        self._cc_stat_cultures._value_lbl.setText(str(cultures))
        if cards:
            last = sorted(cards, key=lambda c: c.created_at or "")[-1]
            self._cc_stat_last._value_lbl.setText((last.created_at or "")[:10] or "—")
        else:
            self._cc_stat_last._value_lbl.setText("—")
        if count == 0:
            self._cc_confirm_lbl.setText("Нет карточек для удаления.")
            self._cc_btn.setEnabled(False)
        else:
            noun = "карточку" if count == 1 else ("карточки" if 2 <= count <= 4 else "карточек")
            self._cc_confirm_lbl.setText(
                f"Удалить все {count} {noun}? Действие необратимо — восстановление невозможно."
            )
            self._cc_btn.setEnabled(True)

    def _on_clear_cards(self) -> None:
        deleted = delete_all_cards()
        self._cc_refresh()
        self._cc_btn.setEnabled(False)
        self._cc_btn.setText(f"✓ {deleted} удалено")
        self._cc_btn.setStyleSheet(self._cc_btn.styleSheet()
            .replace("rgba(248,113,113,0.1)", "rgba(74,222,128,0.08)")
            .replace("rgba(248,113,113,0.4)", "rgba(74,222,128,0.3)")
            .replace("rgba(248,113,113,0.18)", "rgba(74,222,128,0.12)")
            .replace("#f87171", ACCENT_G)
        )
        QTimer.singleShot(3000, lambda: (
            self._cc_btn.setText("Удалить все"),
            self._cc_btn.setStyleSheet(self._cc_btn.styleSheet()
                .replace("rgba(74,222,128,0.08)", "rgba(248,113,113,0.1)")
                .replace("rgba(74,222,128,0.3)", "rgba(248,113,113,0.4)")
                .replace("rgba(74,222,128,0.12)", "rgba(248,113,113,0.18)")
                .replace(ACCENT_G, "#f87171")
            ),
        ))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._excel_row.set_value(config.excel_path)
        self._acts_row.set_value(get_setting("acts_dir"))
        self._excel_backup_row.set_value(get_setting("excel_backup_dir"))
        self._backup_row.set_value(get_setting("backup_dir"))
        self._cc_refresh()
        self._refresh_excel_backup_status()
