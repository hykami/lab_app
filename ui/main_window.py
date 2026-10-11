"""
Главное окно приложения.
Содержит titlebar, сайдбар (вариант 2 — всё раскрыто) и QStackedWidget.
"""

from __future__ import annotations


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QStackedWidget, QVBoxLayout, QWidget,
)

from ui.theme import BG, BORDER
from ui.components.nav_item import Sidebar

# Страницы
from ui.pages.journals.journals_page  import JournalsPage
from ui.pages.distillations.distillation_page import DistillationPage
from ui.pages.acts.acts_page          import ActsPage
from ui.pages.cards.auto              import CardsAutoPage
from ui.pages.cards.manual            import CardsManualPage
from ui.pages.cards.view              import CardsViewPage
from ui.pages.settings.settings_page  import SettingsPage
from ui.pages.settings.clear_cards    import ClearCardsPage
from ui.pages.settings.about          import AboutPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lab App")
        self.setMinimumSize(1120, 680)
        self.resize(1120, 680)
        self.setStyleSheet(f"QMainWindow {{ background: {BG}; }}")

        central = QWidget()
        central.setStyleSheet(f"background: {BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_content(), 1)
        root.addLayout(body, 1)

        # Открываем первую страницу
        self._sidebar._init_expanded()
        self._sidebar.activate_first()

        # ── Глобальные горячие клавиши ────────────────────────────────────────
        self._setup_shortcuts()

    # ── Titlebar ──────────────────────────────────────────────────────────────

    def _build_titlebar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(42)
        bar.setStyleSheet(f"""
            QFrame {{
                background: {BG_TITLEBAR};
                border-bottom: 0.5px solid {BORDER};
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(0)

        title = QLabel("LAB APP")
        title.setStyleSheet(
            f"color: {TEXT_DIM}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent;"
        )
        lay.addWidget(title)
        lay.addStretch()

        # Дата
        date_lbl = QLabel(QDate.currentDate().toString("d MMM yyyy"))
        date_lbl.setStyleSheet(
            f"color: #333; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 11px; background: transparent; margin-right: 14px;"
        )
        lay.addWidget(date_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> Sidebar:
        self._sidebar = Sidebar(  # ширина управляется самим Sidebar
            sections=[
                ("Акты", [
                    ("Акты",        "acts",         lambda: self._show("acts")),
                    ("Журналы",     "journals",     lambda: self._show("journals")),
                    ("Перегонки",   "distillation", lambda: self._show("distillation")),
                ]),
                ("Карточки", [
                    ("Создать",   "cards_manual",  lambda: self._show("cards_manual")),
                    ("Просмотр",  "cards_view",    lambda: self._show("cards_view")),
                ]),
            ],
            bottom_items=[
                ("Настройки",   "settings", lambda: self._show("settings")),
                ("О программе", "about",    lambda: self._show("about")),
            ],
        )
        return self._sidebar

    # ── Content ───────────────────────────────────────────────────────────────

    def _build_content(self) -> QStackedWidget:
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {BG};")
        self._pages: dict[str, QWidget] = {}
        self._page_factories = {
            "journals":     JournalsPage,
            "distillation": DistillationPage,
            "cards_auto":   CardsAutoPage,
            "cards_manual": CardsManualPage,
            "cards_view":   CardsViewPage,
            "acts":         ActsPage,
            "settings":     SettingsPage,
            "clear_cards":  ClearCardsPage,
            "about":        AboutPage,
        }
        return self._stack

    def _setup_shortcuts(self) -> None:
        """Регистрирует все глобальные горячие клавиши приложения."""

        def _sc(seq: str, fn) -> None:
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.ShortcutContext.ApplicationShortcut)
            s.activated.connect(fn)

        # ── Навигация по страницам ────────────────────────────────────────────
        nav_keys = [
            ("Ctrl+1", "journals"),
            ("Ctrl+2", "distillation"),
            ("Ctrl+3", "cards_manual"),
            ("Ctrl+4", "cards_view"),
            ("Ctrl+5", "acts"),
        ]
        for seq, page_key in nav_keys:
            _sc(seq, lambda k=page_key: self._navigate_to(k))

        # ── Карточки ──────────────────────────────────────────────────────────
        _sc("Ctrl+N", self._shortcut_new_card)
        _sc("Ctrl+S", self._shortcut_save_card)
        _sc("Ctrl+F", self._shortcut_focus_search)

        # ── Интерфейс ─────────────────────────────────────────────────────────
        _sc("Escape",  self._shortcut_escape)

    def _navigate_to(self, key: str) -> None:
        """Переход на страницу по горячей клавише — также активирует пункт в сайдбаре."""
        self._show(key)
        self._sidebar.activate_by_key(key)

    def _shortcut_new_card(self) -> None:
        """Ctrl+N — перейти на Создать и сфокусироваться на поле № пробы."""
        self._navigate_to("cards_manual")
        page = self._pages.get("cards_manual")
        if page and hasattr(page, "_probe_field"):
            page._probe_field.input.setFocus()

    def _shortcut_save_card(self) -> None:
        """Ctrl+S — сохранить карточку если активна страница Создать."""
        page = self._stack.currentWidget()
        if page and hasattr(page, "_on_create_and_save"):
            page._on_create_and_save()

    def _shortcut_focus_search(self) -> None:
        """Ctrl+F — фокус на поиск если активна страница Просмотр, иначе перейти на неё."""
        from ui.pages.cards.view import CardsViewPage
        page = self._stack.currentWidget()
        if not isinstance(page, CardsViewPage):
            self._navigate_to("cards_view")
            page = self._pages.get("cards_view")
        if page and hasattr(page, "_probe_search"):
            page._probe_search.setFocus()
            page._probe_search.selectAll()

    def _open_probe_in_view(self, card) -> None:
        """Переход на страницу Просмотр и открытие конкретной пробы."""
        self._navigate_to("cards_view")
        from ui.pages.cards.view import CardsViewPage
        page = self._pages.get("cards_view")
        if isinstance(page, CardsViewPage):
            page.open_probe(card)

    def _shortcut_escape(self) -> None:
        """Esc — закрыть детали/сбросить выбор на текущей странице."""
        from ui.pages.cards.view import CardsViewPage
        page = self._stack.currentWidget()
        if isinstance(page, CardsViewPage):
            if hasattr(page, "_detail"):
                page._detail.clear()
            if hasattr(page, "_selected_item") and page._selected_item:
                page._selected_item.set_selected(False)
                page._selected_item = None

    def _show(self, key: str) -> None:
        if key not in self._pages:
            factory = self._page_factories.get(key)
            if not factory:
                return
            page = factory()
            self._pages[key] = page
            self._stack.addWidget(page)
            if key == "acts":
                page.open_probe_requested.connect(self._open_probe_in_view)
        self._stack.setCurrentWidget(self._pages[key])
