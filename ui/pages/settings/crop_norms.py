"""
Нормы культур — страница настроек.
Виджеты вынесены в crop_norms_widgets.py.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.theme import (
    BG, BORDER, TEXT_MUTED,
    ACCENT_V, ACCENT_ICON, FONT_UI,
)
from ui.pages.settings.crop_norms_widgets import (
    AddCultureDialog, CultureEditor,
)
from logic.db_service import (
    get_all_cultures, get_culture_with_norms,
    add_culture,
)


class CropNormsPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Нормы культур",
            subtitle="",
            section="Настройки",
            actions=[("Сохранить", True)],
        )
        self._current_culture_id: Optional[int] = None
        self._culture_buttons: dict[int, QPushButton] = {}
        self._culture_cache = {}

        self._action_buttons["Сохранить"].clicked.connect(self._on_save)

        self._build_two_column()
        self._load_culture_list()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_two_column(self) -> None:
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        container = QWidget(); container.setStyleSheet(f"background: {BG};")
        h_lay = QHBoxLayout(container)
        h_lay.setContentsMargins(0, 0, 0, 0); h_lay.setSpacing(0)

        # Левая панель
        self._left_panel = QWidget()
        self._left_panel.setFixedWidth(170)
        self._left_panel.setStyleSheet(f"background: {BG}; border-right: 0.5px solid {BORDER};")
        self._left_lay = QVBoxLayout(self._left_panel)
        self._left_lay.setContentsMargins(0, 10, 0, 10); self._left_lay.setSpacing(1)

        cult_lbl = QLabel("КУЛЬТУРЫ")
        cult_lbl.setStyleSheet(
            f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; letter-spacing: 0.04em; padding: 0 12px 6px; background: transparent;"
        )
        self._left_lay.addWidget(cult_lbl)

        self._btn_container = QWidget(); self._btn_container.setStyleSheet("background: transparent;")
        self._btn_lay = QVBoxLayout(self._btn_container)
        self._btn_lay.setContentsMargins(0, 0, 0, 0); self._btn_lay.setSpacing(1)
        self._left_lay.addWidget(self._btn_container)
        self._left_lay.addStretch()

        add_btn = QPushButton("+ Добавить культуру")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(32)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; color: #5a5a72;
                font-family: '{FONT_UI}', sans-serif; font-size: 12px;
                letter-spacing: 1px; text-align: left; padding: 0 12px;
            }}
            QPushButton:hover {{ color: {ACCENT_V}; }}
        """)
        add_btn.clicked.connect(self._on_add_culture)
        self._left_lay.addWidget(add_btn)
        h_lay.addWidget(self._left_panel)

        # Правая панель
        self._editor = CultureEditor()
        self._editor._on_delete_callback = self._on_culture_deleted
        h_lay.addWidget(self._editor, 1)

        self._content_layout.addWidget(container, 1)

    # ── Список культур ────────────────────────────────────────────────────────

    def _load_culture_list(self) -> None:
        while self._btn_lay.count():
            item = self._btn_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._culture_buttons.clear()
        self._culture_cache.clear()

        cultures = get_all_cultures()
        for culture in cultures:
            full = get_culture_with_norms(culture.id)
            if full:
                self._culture_cache[culture.id] = full
            btn = self._make_culture_btn(culture.id, culture.name)
            self._btn_lay.addWidget(btn)
            self._culture_buttons[culture.id] = btn

        if cultures:
            self._select_culture(cultures[0].id)

    def _make_culture_btn(self, cid: int, name: str) -> QPushButton:
        btn = QPushButton(name)
        btn.setCheckable(True)
        btn.setFixedHeight(34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._select_culture(cid))
        self._apply_btn_style(btn, False)
        return btn

    def _apply_btn_style(self, btn: QPushButton, active: bool) -> None:
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(108,92,231,0.08); border: none;
                    border-right: 2px solid {ACCENT_V}; color: {ACCENT_ICON};
                    font-family: '{FONT_UI}', sans-serif; font-size: 12.5px;
                    font-weight: 500; text-align: left; padding: 0 12px;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    border-right: 2px solid transparent; color: {TEXT_MUTED};
                    font-family: '{FONT_UI}', sans-serif; font-size: 12.5px;
                    font-weight: 400; text-align: left; padding: 0 12px;
                }}
                QPushButton:hover {{ color: #9a9aa8; background: rgba(255,255,255,0.02); }}
            """)

    def _select_culture(self, cid: int) -> None:
        self._current_culture_id = cid
        for bid, btn in self._culture_buttons.items():
            self._apply_btn_style(btn, bid == cid)
        culture = self._culture_cache.get(cid) or get_culture_with_norms(cid)
        if culture:
            self._editor.load_culture(culture)

    # ── Действия ──────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        if self._editor.collect_and_save():
            if self._current_culture_id:
                updated = get_culture_with_norms(self._current_culture_id)
                if updated:
                    self._culture_cache[self._current_culture_id] = updated
            self._action_buttons["Сохранить"].flash_success()
        else:
            self._action_buttons["Сохранить"].flash_error()

    def _on_reset(self) -> None:
        if self._current_culture_id:
            self._select_culture(self._current_culture_id)

    def _on_add_culture(self) -> None:
        dlg = AddCultureDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.culture_name
            if not name:
                return
            try:
                add_culture(name, dlg.sample_weight)
                self._load_culture_list()
                cultures = get_all_cultures()
                if cultures:
                    self._select_culture(cultures[-1].id)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def _on_culture_deleted(self) -> None:
        self._load_culture_list()
