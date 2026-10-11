"""
Базовая страница перегонки (Мукомолка / КРС/Свинки).
"""

from __future__ import annotations
import os
from typing import Optional, Callable

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.style_helpers import (
    card_style, input_style, scroll_style,
    label_field_style, label_muted_style, combo_style,
)
from ui.components.styled_combo import StyledComboBox
from ui.theme import (
    BG, BG_CARD, BORDER,
    TEXT_MAIN, TEXT_MUTED, ACCENT_G,
    ACCENT_ICON, FONT_MONO, FONT_UI,
)
from logic.db_service import Card, get_all_cards, get_all_silos
from logic.excel_writer import ExportRow
from config import config


# ── Поток экспорта ────────────────────────────────────────────────────────────

class _ExportThread(QThread):
    progress = pyqtSignal(int, int)   # (текущий шаг, всего шагов)
    finished = pyqtSignal(int)        # кол-во записанных строк
    error    = pyqtSignal(str)        # сообщение об ошибке

    def __init__(self, export_fn: Callable, excel_path: str,
                 rows: list[ExportRow]) -> None:
        super().__init__()
        self._fn         = export_fn
        self._excel_path = excel_path
        self._rows       = rows

    def run(self) -> None:
        try:
            count = self._fn(
                self._excel_path,
                self._rows,
                progress_cb=lambda step, total: self.progress.emit(step, total),
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


# ── Элемент карточки в списке ─────────────────────────────────────────────────

class _CardCheckItem(QFrame):
    def __init__(self, card: Card, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.card = card
        self.setStyleSheet(f"""
            QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 8px; }}
            QFrame:hover {{ border-color: #5a5a72; }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        self._cb = QCheckBox()
        self._cb.setStyleSheet("""
            QCheckBox { background: transparent; border: none; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 0.5px solid #5a5a72; background: #111114; }
            QCheckBox::indicator:checked { background: rgba(108,92,231,0.4); border-color: rgba(108,92,231,0.7); }
        """)
        lay.addWidget(self._cb)

        num = QLabel(f"# {card.probe_number}")
        num.setStyleSheet(
            f"color: {ACCENT_ICON}; background: rgba(108,92,231,0.1);"
            f"border: 0.5px solid rgba(108,92,231,0.25); border-radius: 5px;"
            f"font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 2px 8px;"
        )
        num.setFixedWidth(75)
        lay.addWidget(num)

        cult = QLabel(card.culture_name)
        cult.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif; font-size: 13px; background: transparent; border: none;"
        )
        lay.addWidget(cult, 1)

        hints = []
        if card.humidity is not None: hints.append(f"W={card.humidity}")
        if card.sp_total: hints.append(f"СП={card.sp_total:.2f}")
        if card.zp_total: hints.append(f"ЗП={card.zp_total:.2f}")
        if hints:
            hint = QLabel("  ".join(hints))
            hint.setStyleSheet(
                f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif; font-size: 12px; background: transparent; border: none;"
            )
            lay.addWidget(hint)

        self.mousePressEvent = lambda e: self._cb.setChecked(not self._cb.isChecked())

    @property
    def is_checked(self) -> bool:
        return self._cb.isChecked()


# ── Поле ввода с меткой ───────────────────────────────────────────────────────

class _Field(QWidget):
    def __init__(self, label: str, placeholder: str = "", required: bool = True,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lbl_row = QWidget(); lbl_row.setStyleSheet("background: transparent;")
        lbl_lay = QHBoxLayout(lbl_row); lbl_lay.setContentsMargins(0, 0, 0, 0); lbl_lay.setSpacing(3)
        lbl = QLabel(label); lbl.setStyleSheet(label_field_style())
        lbl_lay.addWidget(lbl)
        if required:
            star = QLabel("*")
            star.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 500; background: transparent;")
            lbl_lay.addWidget(star)
        lbl_lay.addStretch()
        lay.addWidget(lbl_row)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setFixedHeight(36)
        self.input.setStyleSheet(input_style())
        lay.addWidget(self.input)

    @property
    def value(self) -> str:
        return self.input.text().strip()


# ── Базовая страница ──────────────────────────────────────────────────────────

class BaseDistillationPage(BasePage):

    # Подкласс может переопределить какие поля показывать
    SHOW_TANK = False   # Номер ёмкости — для МКМЦ и КРС/Свинки
    DISTILLATION_PLACES: frozenset[str] = frozenset()  # пустой = все карточки

    def __init__(
        self,
        title: str,
        section: str,
        export_fn: Callable,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            title=title, subtitle="", section=section,
            actions=[("Экспорт в Excel", True)],
        )
        self._export_fn = export_fn
        self._card_items: list[_CardCheckItem] = []
        self._action_buttons["Экспорт в Excel"].clicked.connect(self._on_export)
        self._build_ui()

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # Прогресс-бар (скрыт по умолчанию)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {BORDER};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT_G};
                border-radius: 2px;
            }}
        """)
        self._progress_bar.setVisible(False)
        self._content_layout.addWidget(self._progress_bar)

        # Загружаем все силосы для поиска по silo_id из карточки
        self._all_silos = get_all_silos()

        # ── Основной layout ───────────────────────────────────────────────────
        main = QHBoxLayout(); main.setSpacing(14); main.setContentsMargins(0, 0, 0, 0)

        # Список карточек
        list_frame = QFrame(); list_frame.setStyleSheet(card_style())
        lf_lay = QVBoxLayout(list_frame); lf_lay.setContentsMargins(0, 0, 0, 0); lf_lay.setSpacing(0)

        lf_hdr = QWidget()
        lf_hdr.setStyleSheet(f"background: rgba(108,92,231,0.05); border-radius: 10px 10px 0 0; border-bottom: 0.5px solid {BORDER};")
        lh = QHBoxLayout(lf_hdr); lh.setContentsMargins(14, 9, 14, 9)
        lh.addStretch()
        t = QLabel("КАРТОЧКИ")
        t.setStyleSheet(f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;")
        lh.addWidget(t); lh.addStretch()

        for label, checked in [("Все", True), ("Сбросить", False)]:
            b = QPushButton(label); b.setFixedHeight(22)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: 0.5px solid {BORDER};
                border-radius: 4px; color: #5a5a72; font-family: '{FONT_UI}', sans-serif;
                font-size: 11px; padding: 0 8px; }}
                QPushButton:hover {{ color: {TEXT_MUTED}; border-color: #5a5a72; }}
            """)
            b.clicked.connect(lambda _, c=checked: self._select_all(c))
            lh.addSpacing(4); lh.addWidget(b)
        lf_lay.addWidget(lf_hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setStyleSheet(scroll_style())
        self._list_inner = QWidget(); self._list_inner.setStyleSheet(f"background: {BG};")
        self._list_lay = QVBoxLayout(self._list_inner)
        self._list_lay.setContentsMargins(10, 10, 10, 10); self._list_lay.setSpacing(6)
        self._list_lay.addStretch()
        scroll.setWidget(self._list_inner); lf_lay.addWidget(scroll)
        main.addWidget(list_frame, 3)

        # Правая панель — поля ввода
        right = QFrame(); right.setStyleSheet(card_style()); right.setFixedWidth(290)
        rl = QVBoxLayout(right); rl.setContentsMargins(16, 14, 16, 16); rl.setSpacing(12)

        rh = QLabel("ДАННЫЕ ОТГРУЗКИ")
        rh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rh.setStyleSheet(f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;")
        rl.addWidget(rh)

        # Вес (необязательный)
        self._weight_f = _Field("Вес, кг", "например 50000", required=False)
        rl.addWidget(self._weight_f)

        # Номер ёмкости (обязательный для обоих листов)
        self._tank_f = None
        if self.SHOW_TANK:
            self._tank_f = _Field("Номер ёмкости", "например 4")
            rl.addWidget(self._tank_f)

        # Исполнитель — комбо из работников + ручной ввод
        exec_w = QWidget(); exec_w.setStyleSheet("background: transparent; border: none;")
        el = QVBoxLayout(exec_w); el.setContentsMargins(0, 0, 0, 0); el.setSpacing(5)
        exec_lbl_row = QWidget(); exec_lbl_row.setStyleSheet("background: transparent;")
        exec_lbl_lay = QHBoxLayout(exec_lbl_row); exec_lbl_lay.setContentsMargins(0,0,0,0); exec_lbl_lay.setSpacing(3)
        exec_lbl = QLabel("Исполнитель"); exec_lbl.setStyleSheet(label_field_style())
        exec_lbl_lay.addWidget(exec_lbl)
        exec_star = QLabel("*"); exec_star.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 500; background: transparent;")
        exec_lbl_lay.addWidget(exec_star); exec_lbl_lay.addStretch()
        el.addWidget(exec_lbl_row)
        self._executor_combo = StyledComboBox(font_size=12)
        self._executor_combo.setFixedHeight(36)
        self._executor_combo.setEditable(True)
        self._executor_combo.lineEdit().setPlaceholderText("Фамилия И.О.")
        self._executor_combo.setStyleSheet(combo_style(font_size=12))
        self._executor_combo.lineEdit().setStyleSheet(
            f"background: transparent; border: none; color: {TEXT_MAIN}; "
            f"font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 0 4px;"
        )
        el.addWidget(self._executor_combo)
        rl.addWidget(exec_w)
        self._reload_executors()

        rl.addStretch()
        main.addWidget(right)

        mw = QWidget(); mw.setStyleSheet("background: transparent;"); mw.setLayout(main)
        self._content_layout.addWidget(mw, 1)
        self._load_cards()

    def _reload_executors(self) -> None:
        """Загружает список работников в комбо исполнителя."""
        from logic.db_service import get_all_workers
        current = self._executor_combo.currentText()
        self._executor_combo.blockSignals(True)
        self._executor_combo.clear()
        self._executor_combo.addItem("")
        for w in get_all_workers():
            self._executor_combo.addItem(w.name)
        # Восстанавливаем ранее введённое значение
        idx = self._executor_combo.findText(current)
        if idx >= 0:
            self._executor_combo.setCurrentIndex(idx)
        else:
            self._executor_combo.setEditText(current)
        self._executor_combo.blockSignals(False)

    def _load_cards(self) -> None:
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget(): item.widget().setParent(None)
        self._card_items.clear()

        cards = [
            c for c in get_all_cards()
            if getattr(c, 'card_type', '') == 'Перегонка'
            and (
                not self.DISTILLATION_PLACES
                or getattr(c, 'distillation_place', '') in self.DISTILLATION_PLACES
            )
        ]
        if not cards:
            ph = QLabel("Нет сохранённых карточек")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setStyleSheet(label_muted_style() + " border: none;")
            self._list_lay.addWidget(ph)
        else:
            for card in cards:
                item = _CardCheckItem(card)
                self._list_lay.addWidget(item)
                self._card_items.append(item)
        self._list_lay.addStretch()

    def _select_all(self, checked: bool) -> None:
        for item in self._card_items:
            item._cb.setChecked(checked)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reload_executors()
        self._all_silos = get_all_silos()
        self._load_cards()

    def _on_export(self) -> None:
        excel_path = config.excel_path
        if not excel_path:
            QMessageBox.warning(self, "Ошибка",
                "Путь к Excel-файлу не указан.\n"
                "Задайте его в Настройки → Основные."); return
        if not os.path.exists(excel_path):
            QMessageBox.warning(self, "Ошибка",
                f"Файл не найден:\n{excel_path}\n\n"
                "Проверьте путь в Настройки → Основные."); return

        selected = [item.card for item in self._card_items if item.is_checked]
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну карточку."); return

        executor = self._executor_combo.currentText().strip()
        if not executor:
            QMessageBox.warning(self, "Ошибка", "Укажите исполнителя."); return

        tank = self._tank_f.value if self._tank_f else ""
        if self.SHOW_TANK and not tank:
            QMessageBox.warning(self, "Ошибка", "Укажите номер ёмкости."); return

        # Силос берём из карточки по silo_id
        silo_map = {s.id: s for s in self._all_silos}
        rows = [
            ExportRow(
                card=c,
                silo=silo_map.get(c.silo_id) if getattr(c, 'silo_id', None) else None,
                weight_kg=self._weight_f.value,
                executor=executor,
                tank_number=tank,
                workshop=getattr(c, 'distillation_place', '') or '',
            )
            for c in selected
        ]

        btn = self._action_buttons["Экспорт в Excel"]
        btn.setEnabled(False)
        btn.setText("Экспортируется...")
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        self._export_thread = _ExportThread(self._export_fn, excel_path, rows)

        def _on_progress(step: int, total: int) -> None:
            pct = int(step / total * 100) if total > 0 else 0
            self._progress_bar.setValue(pct)

        def _on_done(count: int) -> None:
            self._progress_bar.setValue(100)
            QTimer.singleShot(600, lambda: self._progress_bar.setVisible(False))
            btn.flash_success(f"✓ Записано {count} строк", duration_ms=3000)
            self._select_all(False)

        def _on_error(msg: str) -> None:
            self._progress_bar.setVisible(False)
            btn.flash_error("✗ Ошибка записи", duration_ms=3000)
            import glob
            directory = os.path.dirname(os.path.abspath(excel_path))
            name = os.path.splitext(os.path.basename(excel_path))[0]
            backups = sorted(glob.glob(os.path.join(directory, f"{name}.backup_*.xlsx")))
            full_msg = f"Не удалось записать в Excel:\n{msg}"
            if backups:
                full_msg += f"\n\nРезервная копия сохранена:\n{os.path.basename(backups[-1])}"
            QMessageBox.critical(self, "Ошибка записи", full_msg)

        self._export_thread.progress.connect(_on_progress)
        self._export_thread.finished.connect(_on_done)
        self._export_thread.error.connect(_on_error)
        self._export_thread.start()
