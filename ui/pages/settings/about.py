"""
О программе — версия, библиотеки, инструкция.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QScrollArea, QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.style_helpers import card_style, scroll_style
from ui.theme import (
    BG, BORDER, TEXT_MAIN,
    TEXT_MUTED,
    FONT_UI,
)

# ── Инструкция ────────────────────────────────────────────────────────────────

GUIDE_SECTIONS = [
    ("Карточки", "#a89cff", [
        ("Создать карточку",
         "Перейдите в Карточки → Создать. Введите № пробы и выберите культуру. "
         "СП и ЗП можно ввести вручную или оставить пустыми — будут сгенерированы автоматически. "
         "Показатели (влажность, натура и др.) также генерируются автоматически по культуре. "
         "Нажмите «Создать и сохранить»."),
        ("Входной контроль",
         "Включите переключатель «Вх. контроль» перед созданием. "
         "Программа автоматически рассчитает допускаемое расхождение по ГОСТ и добавит его к СП и ЗП. "
         "В блоках примесей отобразится базовое и итоговое значение."),
        ("Просмотр карточек",
         "В разделе Карточки → Просмотр отображаются все сохранённые карточки. "
         "Нажмите на карточку в списке слева чтобы увидеть полные данные. "
         "Удаление — кнопка ✕ рядом с карточкой в списке."),
    ]),
    ("Журналы", "#4ade80", [
        ("Влажность",
         "Выберите пробу из списка или введите данные вручную. "
         "Укажите влажность и выберите две бюксы."),
        ("Число падения",
         "Выберите пробу, введите ЧП и влажность. "
         "Результат показывает допустимый диапазон для двух навесок."),
        ("Клейковина",
         "Введите значение клейковины и ИДК. "
         "Расчёт ведётся по двум параллельным определениям с допусками по ГОСТ."),
    ]),
    ("Перегонки", "#60a5fa", [
        ("Мукомолка (МКМЦ)",
         "Укажите путь к Excel-файлу в поле вверху страницы — он сохранится. "
         "Выберите силос и введите вес и исполнителя. "
         "Отметьте нужные карточки в списке и нажмите «Экспорт в Excel». "
         "Данные запишутся на лист «МКМЦ» файла."),
        ("КРС / Свинки",
         "Работает аналогично Мукомолке, но записывает данные "
         "на лист «Производства АПП»."),
    ]),
    ("Настройки", "#facc15", [
        ("Нормы культур",
         "Здесь задаются диапазоны СП/ЗП и норм примесей для каждой культуры. "
         "Выберите культуру слева, отредактируйте значения и нажмите «Сохранить». "
         "Нормы используются при генерации карточек."),
        ("Силоса",
         "Таблица всех 35 силосов с культурой, классом, годом урожая и происхождением. "
         "Данные берутся при экспорте в Excel (колонки D–H)."),
        ("Персонал",
         "Добавляйте работников через кнопку «+ Добавить». "
         "Перетащите имя работника в нужную карточку смены чтобы закрепить его. "
         "Нажмите «Сохранить смены» — состав запишется в базу данных."),
        ("Бюксы",
         "Список бюкс с их массами. Используются в журнале Влажности. "
         "Можно добавлять и редактировать."),
        ("Очистить карточки",
         "Удаляет все сохранённые карточки из базы данных безвозвратно. "
         "На странице отображается статистика: количество карточек, число уникальных культур "
         "и дата последней созданной карточки. Действие необратимо — используйте с осторожностью."),
    ]),
]



# ── Горячие клавиши ───────────────────────────────────────────────────────────

SHORTCUTS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("Навигация", "#a89cff", [
        ("Ctrl+1",  "Влажность"),
        ("Ctrl+2",  "Число падения"),
        ("Ctrl+3",  "Клейковина"),
        ("Ctrl+4",  "Перегонки (Мукомолка + КРС/Свинки)"),
        ("Ctrl+5",  "Создать карточку"),
        ("Ctrl+6",  "Просмотр карточек"),
        ("Ctrl+7",  "Акты"),
        ("Ctrl+N",  "Новая карточка — фокус на поле № пробы"),
    ]),
    ("Карточки", "#4ade80", [
        ("Ctrl+S",   "Сохранить карточку (на странице Создать)"),
        ("Ctrl+F",   "Фокус на поиск / перейти в Просмотр"),
        ("Escape",   "Закрыть детали и снять выделение (в Просмотре)"),
    ]),
]

# ── Вспомогательные виджеты ───────────────────────────────────────────────────

def _section_label(text: str, color: str = "#4a4a58", size: int = 8) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{FONT_UI}', sans-serif; "
        f"font-size: {size}px; letter-spacing: 0.1em; background: transparent; border: none;"
    )
    return lbl


def _text_label(text: str, muted: bool = False, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    color = TEXT_MUTED if muted else TEXT_MAIN
    weight = "500" if bold else "400"
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{FONT_UI}', sans-serif; "
        f"font-size: 12px; font-weight: {weight}; background: transparent; border: none;"
    )
    return lbl




# ── Страница ──────────────────────────────────────────────────────────────────

class AboutPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="О программе",
            subtitle="",
            section="Настройки",
            actions=[],
        )
        self._build_ui()

    def _build_ui(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_style())
        inner = QWidget(); inner.setStyleSheet(f"background: {BG};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 16, 16)
        lay.setSpacing(14)

        # ── Горячие клавиши ───────────────────────────────────────────────────
        kb_hdr = QWidget(); kb_hdr.setStyleSheet("background: transparent;")
        kbh = QHBoxLayout(kb_hdr); kbh.setContentsMargins(0, 0, 0, 2)
        kbh.addWidget(_section_label("ГОРЯЧИЕ КЛАВИШИ")); kbh.addStretch()
        lay.addWidget(kb_hdr)

        for sc_section, sc_color, sc_items in SHORTCUTS:
            sc_card = QFrame(); sc_card.setStyleSheet(card_style())
            scl = QVBoxLayout(sc_card); scl.setContentsMargins(0, 0, 0, 0); scl.setSpacing(0)
            sc_hdr = QWidget()
            sc_hdr.setStyleSheet(
                f"background: transparent; border-radius: 10px 10px 0 0;"
                f"border-bottom: 0.5px solid {BORDER};"
            )
            schl = QHBoxLayout(sc_hdr); schl.setContentsMargins(18, 10, 18, 10)
            dot2 = QWidget(); dot2.setFixedSize(6, 6)
            dot2.setStyleSheet(f"background: {sc_color}; border-radius: 3px; border: none;")
            t2 = QLabel(sc_section)
            t2.setStyleSheet(
                f"color: {sc_color}; font-family: '{FONT_UI}', sans-serif;"
                "font-size: 11px; background: transparent; border: none;"
            )
            schl.addWidget(dot2); schl.addSpacing(8); schl.addWidget(t2); schl.addStretch()
            scl.addWidget(sc_hdr)
            for j, (keys, desc) in enumerate(sc_items):
                row_w = QWidget()
                row_w.setStyleSheet(
                    "background: transparent; border: none;" +
                    ("" if j == len(sc_items) - 1 else "border-bottom: 0.5px solid #111114;")
                )
                rl = QHBoxLayout(row_w); rl.setContentsMargins(18, 9, 18, 9); rl.setSpacing(14)
                key_lbl = QLabel(keys)
                key_lbl.setFixedWidth(120)
                key_lbl.setStyleSheet(
                    f"color: {sc_color}; background: transparent;"
                    f" font-family: '{FONT_UI}', sans-serif; font-size: 11px; border: none;"
                )
                desc_lbl = QLabel(desc)
                desc_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; background: transparent;"
                    f" font-family: '{FONT_UI}', sans-serif; font-size: 12px; border: none;"
                )
                rl.addWidget(key_lbl); rl.addWidget(desc_lbl, 1)
                scl.addWidget(row_w)
            lay.addWidget(sc_card)

        # ── Инструкция ────────────────────────────────────────────────────────
        guide_hdr = QWidget(); guide_hdr.setStyleSheet("background: transparent;")
        gh = QHBoxLayout(guide_hdr); gh.setContentsMargins(0, 0, 0, 2)
        gh.addWidget(_section_label("ИНСТРУКЦИЯ"))
        gh.addStretch()
        lay.addWidget(guide_hdr)

        for section_title, color, items in GUIDE_SECTIONS:
            sec_card = QFrame(); sec_card.setStyleSheet(card_style())
            sl = QVBoxLayout(sec_card); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)

            sec_hdr = QWidget()
            sec_hdr.setStyleSheet(
                f"background: transparent; border-radius: 10px 10px 0 0; "
                f"border-bottom: 0.5px solid {BORDER};"
            )
            shl = QHBoxLayout(sec_hdr); shl.setContentsMargins(18, 12, 18, 12)
            dot = QWidget(); dot.setFixedSize(6, 6)
            dot.setStyleSheet(f"background: {color}; border-radius: 3px; border: none;")
            t = QLabel(section_title)
            t.setStyleSheet(
                f"color: {color}; font-family: '{FONT_UI}', sans-serif; "
                "font-size: 11px; background: transparent; border: none;"
            )
            shl.addWidget(dot); shl.addSpacing(8); shl.addWidget(t); shl.addStretch()
            sl.addWidget(sec_hdr)

            for i, (step_title, step_text) in enumerate(items):
                item_w = QWidget()
                item_w.setStyleSheet(
                    "background: transparent; border: none;" +
                    ("" if i == len(items) - 1 else "border-bottom: 0.5px solid #111114;")
                )
                ilay = QHBoxLayout(item_w); ilay.setContentsMargins(18, 12, 18, 12); ilay.setSpacing(14)

                num = QLabel(str(i + 1))
                num.setFixedSize(20, 20)
                num.setAlignment(Qt.AlignmentFlag.AlignCenter)
                num.setStyleSheet(
                    f"color: {color}; background: transparent; "
                    f"border: 0.5px solid {color}4d; "
                    "border-radius: 10px; "
                    f"font-family: '{FONT_UI}', sans-serif; font-size: 11px;"
                )
                ilay.addWidget(num)

                text_col = QVBoxLayout(); text_col.setSpacing(3); text_col.setContentsMargins(0,0,0,0)
                text_col.addWidget(_text_label(step_title, bold=True))
                text_col.addWidget(_text_label(step_text, muted=True))
                ilay.addLayout(text_col, 1)
                sl.addWidget(item_w)

            lay.addWidget(sec_card)

        lay.addStretch()
        scroll.setWidget(inner)
        self._content_layout.addWidget(scroll)
