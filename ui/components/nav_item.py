"""
Сайдбар v2.0 — анимированный, сворачиваемый.
"""
from __future__ import annotations
from typing import Callable, Optional

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, pyqtProperty, QTimer,
)
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import QRectF
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QStackedLayout,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QGraphicsOpacityEffect, QSizePolicy,
    QScrollArea,
)

from ui.theme import BORDER, FONT_UI, ACCENT_ICON

SB_COLLAPSED  = 48
SB_EXPANDED   = 182
ANIM_DURATION = 240

_active_item: Optional["NavItem"] = None

def _set_active(item: "NavItem") -> None:
    global _active_item
    if _active_item is not None and _active_item is not item:
        _active_item.setChecked(False)
    _active_item = item


NAV_ICONS: dict[str, str] = {
    # Шестерёнка с внутренним кружком — Настройки
    "settings": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>",
    # Открытая книга — Журналы
    "journals": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>",
    # Капля воды — Влажность
    "humidity": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>",
    # Часы — Число падения
    "fall_number": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><circle cx='12' cy='12' r='9' stroke='{c}' stroke-width='1.5'/><path d='M12 7v5l3.5 3.5' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>",
    # Колба/спираль — Клейковина
    "gluten": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M9 3h6M10 3v6.4L6 17a2 2 0 0 0 1.8 2.9h8.4A2 2 0 0 0 18 17l-4-7.6V3' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M6.5 14.5h11' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/></svg>",
    # Колба перегонки — Перегонки
    "distillation": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M9 3h6M10 3v5L6 17a2 2 0 0 0 1.89 2.7h8.22A2 2 0 0 0 18 17l-4-9V3' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><circle cx='9.5' cy='15.5' r='1' fill='{c}'/><circle cx='14' cy='17.5' r='0.75' fill='{c}'/></svg>",
    # Плюс в рамке — Создать карточку
    "cards_manual": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M14 2v6h6' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M12 11v6M9 14h6' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/></svg>",
    # Документ со строками — Просмотр карточек
    "cards_view": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M14 2v6h6' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M8 13h8M8 17h6' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/></svg>",
    # Документ с галочкой — Акты
    "acts": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M14 2v6h6' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M9 15l2 2 4-4' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>",
    # Слайдеры — Основные настройки
    "general": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M4 6h16M4 12h16M4 18h16' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/><circle cx='8' cy='6' r='2' fill='{c}' stroke='none'/><circle cx='16' cy='12' r='2' fill='{c}' stroke='none'/><circle cx='10' cy='18' r='2' fill='{c}' stroke='none'/></svg>",
    # Документ с галочкой — Нормы культур
    "crop_norms": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M9 11l3 3L22 4' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>",
    # Пробирка/колба — Бюксы
    "boxes": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M8 3h8' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/><path d='M9 3v7.4L5 18a2 2 0 0 0 1.8 2.9h10.4A2 2 0 0 0 19 18l-4-7.6V3' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M5.5 15h13' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/></svg>",
    # Башня-силос — Силоса
    "silos": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><rect x='5' y='7' width='14' height='14' rx='1.5' stroke='{c}' stroke-width='1.5'/><path d='M5 12h14M5 16.5h14' stroke='{c}' stroke-width='1.2' stroke-linecap='round'/><path d='M5 7c0-2.5 3.13-4 7-4s7 1.5 7 4' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/><path d='M10 21v0a2 2 0 0 1-2-2v-1h8v1a2 2 0 0 1-2 2v0' stroke='{c}' stroke-width='1.3' stroke-linecap='round'/></svg>",
    # Два силуэта — Персонал
    "personnel": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><circle cx='9' cy='7' r='4' stroke='{c}' stroke-width='1.5'/><path d='M23 21v-2a4 4 0 0 0-3-3.87' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M16 3.13a4 4 0 0 1 0 7.75' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>",
    # Урна с крышкой — Очистить карточки
    "clear_cards": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M10 11v6M14 11v6' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/></svg>",
    # Круг с буквой i — О программе
    "about": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><circle cx='12' cy='12' r='10' stroke='{c}' stroke-width='1.5'/><path d='M12 16v-4' stroke='{c}' stroke-width='1.8' stroke-linecap='round'/><circle cx='12' cy='8.5' r='1' fill='{c}' stroke='none'/></svg>",
    # Авто-карточка (не используется в сайдбаре, оставляем)
    "cards_auto": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M14 2v6h6' stroke='{c}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/><path d='M12 11v6M9 14h6' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/></svg>",
    "mill": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><circle cx='12' cy='12' r='3' stroke='{c}' stroke-width='1.5'/><path d='M12 2v3M12 19v3M2 12h3M19 12h3M4.93 4.93l2.12 2.12M16.95 16.95l2.12 2.12M4.93 19.07l2.12-2.12M16.95 7.05l2.12-2.12' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/></svg>",
    "livestock": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><path d='M12 22V10' stroke='{c}' stroke-width='1.5' stroke-linecap='round'/><path d='M12 10C12 10 8 8.5 6 5c3 0 6 2 6 5z' stroke='{c}' stroke-width='1.4' stroke-linejoin='round'/><path d='M12 15C12 15 16 13.5 18 10c-3 0-6 2-6 5z' stroke='{c}' stroke-width='1.4' stroke-linejoin='round'/><path d='M12 19C12 19 8 17.5 6 14c3 0 6 2 6 5z' stroke='{c}' stroke-width='1.4' stroke-linejoin='round'/></svg>",
}

def _load_svg(widget: QSvgWidget, key: str, color: str) -> None:
    if key in NAV_ICONS:
        widget.load(NAV_ICONS[key].replace("{c}", color).encode())


# ── Логотип-кнопка с анимацией вращения ──────────────────────────────────────

class _LogoButton(QWidget):
    def __init__(self, on_click: Callable, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self._angle = 0.0
        self.setFixedSize(48, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"_anim_angle")
        self._anim.setDuration(440)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuart)

    def get_anim_angle(self) -> float:
        return self._angle

    def set_anim_angle(self, v: float) -> None:
        self._angle = v
        self.update()

    _anim_angle = pyqtProperty(float, get_anim_angle, set_anim_angle)

    def mousePressEvent(self, _e):
        self._anim.stop()
        start = self._angle % 360
        self._anim.setStartValue(start)
        self._anim.setEndValue(start + 180)
        self._anim.start()
        self._on_click()

    def paintEvent(self, _e):
        from PyQt6.QtGui import QLinearGradient, QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, sz = 24, 22, 30
        p.translate(cx, cy)
        p.rotate(self._angle)
        p.translate(-sz / 2, -sz / 2)

        # Градиентный фон 135deg #6c5ce7 → #a29bfe
        grad = QLinearGradient(0, 0, sz, sz)
        grad.setColorAt(0.0, QColor("#6c5ce7"))
        grad.setColorAt(1.0, QColor("#a29bfe"))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, sz, sz), 7, 7)
        p.fillPath(path, grad)

        # 2×2 сетка квадратиков (как в макете)
        # координаты: top-left = full opacity, остальные с убывающей прозрачностью
        gap = 1.0
        inner_pad = 6.0
        inner = sz - 2 * inner_pad     # 18
        cell  = (inner - gap) / 2      # 8.5
        cells = [
            (QColor(255,255,255,255), inner_pad,             inner_pad),
            (QColor(255,255,255,128), inner_pad + cell + gap, inner_pad),
            (QColor(255,255,255,128), inner_pad,             inner_pad + cell + gap),
            (QColor(255,255,255,64),  inner_pad + cell + gap, inner_pad + cell + gap),
        ]
        p.setPen(Qt.PenStyle.NoPen)
        for color, x, y in cells:
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, y, cell, cell), 1.6, 1.6)
        p.end()


# ── Пункт навигации ───────────────────────────────────────────────────────────

class NavItem(QPushButton):
    def __init__(self, label: str, icon_key: str,
                 on_click: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self._label_text = label
        self._icon_key   = icon_key
        self._callback   = on_click

        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 0, 9, 0)
        lay.setSpacing(10)

        self._icon_wrap = QWidget()
        self._icon_wrap.setFixedSize(30, 30)
        self._icon_wrap.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._svg = QSvgWidget(self._icon_wrap)
        self._svg.setStyleSheet("background: transparent; border: none;")
        self._svg.resize(15, 15)
        self._svg.move(7, 7)
        self._svg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self._icon_wrap)

        self._lbl = QLabel(label)
        self._lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._opacity_fx = QGraphicsOpacityEffect()
        self._opacity_fx.setOpacity(0.0)
        self._lbl.setGraphicsEffect(self._opacity_fx)

        self._fade = QPropertyAnimation(self._opacity_fx, b"opacity")
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        lay.addWidget(self._lbl)

        self._refresh()
        self.toggled.connect(lambda _: self._refresh())
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        self.setChecked(True)
        _set_active(self)
        if self._callback:
            self._callback()

    def _refresh(self):
        active = self.isChecked()
        ic = ACCENT_ICON if active else "#707085"
        _load_svg(self._svg, self._icon_key, ic)

        if active:
            wrap_style = "background: rgba(108,92,231,0.18); border-radius: 7px; border: 0.5px solid rgba(108,92,231,0.35);"
            lbl_color  = ACCENT_ICON
        else:
            wrap_style = "background: transparent; border-radius: 7px; border: none;"
            lbl_color  = "#8a8a9a"

        self._icon_wrap.setStyleSheet(wrap_style)
        self._lbl.setStyleSheet(
            f"color: {lbl_color}; font-family: '{FONT_UI}', sans-serif;"
            "font-size: 12px; background: transparent; border: none;"
        )

    def enterEvent(self, e):
        if not self.isChecked():
            self._icon_wrap.setStyleSheet(
                "background: rgba(255,255,255,0.04); border-radius: 7px; border: none;"
            )
            self._svg.resize(17, 17)
            self._svg.move(6, 6)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._refresh()
        self._svg.resize(15, 15)
        self._svg.move(7, 7)
        super().leaveEvent(e)

    def show_label(self, show: bool, delay_ms: int = 0):
        self._fade.stop()
        target = 1.0 if show else 0.0
        current = self._opacity_fx.opacity()
        if abs(current - target) < 0.01:
            return
        self._fade.setStartValue(current)
        self._fade.setEndValue(target)
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, self._fade.start)
        else:
            self._fade.start()

    # совместимость со старым кодом
    def _update_icon(self):
        self._refresh()


# ── Разделитель ───────────────────────────────────────────────────────────────

class _Sep(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"background: {BORDER}; border: none; margin: 4px 9px;")


# ── Сайдбар ───────────────────────────────────────────────────────────────────

class Sidebar(QWidget):
    def __init__(self, sections, bottom_items=None, parent=None):
        super().__init__(parent)
        self._items: list[NavItem] = []
        self._expanded = True  # раскрыт по умолчанию

        self.setFixedWidth(SB_EXPANDED)
        self.setStyleSheet(
            f"QWidget {{ background: #0d0d0f; border-right: 0.5px solid {BORDER}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Logo row: кнопка + название (появляется при раскрытии)
        # Используем QStackedLayout чтобы _LogoButton занимал всю площадь logo_row
        # и был кликабелен по всей иконке, а _app_label накладывался поверх через HBox
        logo_row = QWidget()
        logo_row.setFixedHeight(44)
        logo_row.setStyleSheet("background: transparent;")

        # Слой 0 — кнопка (занимает всю ширину)
        self._logo = _LogoButton(on_click=self._toggle)

        # Слой 1 — лейаут с отступом для названия приложения
        logo_label_overlay = QWidget()
        logo_label_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        logo_label_overlay.setStyleSheet("background: transparent;")
        logo_lbl_hl = QHBoxLayout(logo_label_overlay)
        logo_lbl_hl.setContentsMargins(0, 0, 0, 0)
        logo_lbl_hl.setSpacing(0)
        logo_lbl_hl.addSpacing(48)  # сдвиг за иконку

        self._app_label = QLabel("Lab App")
        self._app_label.setStyleSheet(
            f"color: #e8e8f0; font-family: 'Segoe UI', sans-serif;"
            "font-size: 13px; font-weight: 600; background: transparent; border: none;"
            "letter-spacing: 0.02em;"
        )
        opacity_fx = QGraphicsOpacityEffect()
        opacity_fx.setOpacity(0.0)
        self._app_label.setGraphicsEffect(opacity_fx)
        self._logo_label_opacity = opacity_fx
        self._logo_label_fade = QPropertyAnimation(opacity_fx, b"opacity")
        self._logo_label_fade.setDuration(180)
        self._logo_label_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        logo_lbl_hl.addWidget(self._app_label)
        logo_lbl_hl.addStretch()

        logo_stack = QStackedLayout(logo_row)
        logo_stack.setContentsMargins(0, 0, 0, 0)
        logo_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        logo_stack.addWidget(self._logo)
        logo_stack.addWidget(logo_label_overlay)
        logo_stack.setCurrentIndex(0)

        outer.addWidget(logo_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 0px; }"
        )

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        scroll.setWidget(container)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 4, 0, 10)
        lay.setSpacing(0)

        for i, (_sec_name, items) in enumerate(sections):
            for label, icon_key, callback in items:
                item = NavItem(label, icon_key, callback)
                lay.addWidget(item)
                self._items.append(item)
            if i < len(sections) - 1:
                lay.addSpacing(6)
                lay.addWidget(_Sep())
                lay.addSpacing(6)

        lay.addStretch()

        if bottom_items:
            lay.addSpacing(6)
            lay.addWidget(_Sep())
            lay.addSpacing(6)
            for label, icon_key, callback in bottom_items:
                item = NavItem(label, icon_key, callback)
                lay.addWidget(item)
                self._items.append(item)

        outer.addWidget(scroll, 1)

        # Анимация ширины (min + max параллельно)
        self._anim_min = QPropertyAnimation(self, b"minimumWidth")
        self._anim_min.setDuration(ANIM_DURATION)
        self._anim_min.setEasingCurve(QEasingCurve.Type.InOutQuart)

        self._anim_max = QPropertyAnimation(self, b"maximumWidth")
        self._anim_max.setDuration(ANIM_DURATION)
        self._anim_max.setEasingCurve(QEasingCurve.Type.InOutQuart)

        self._grp = QParallelAnimationGroup()
        self._grp.addAnimation(self._anim_min)
        self._grp.addAnimation(self._anim_max)
        self._grp.finished.connect(self._on_done)

    def _toggle(self):
        self._expanded = not self._expanded
        cur = self.width()
        tgt = SB_EXPANDED if self._expanded else SB_COLLAPSED

        # Снять фиксацию
        self.setMinimumWidth(cur)
        self.setMaximumWidth(cur)

        self._anim_min.setStartValue(cur)
        self._anim_min.setEndValue(tgt)
        self._anim_max.setStartValue(cur)
        self._anim_max.setEndValue(tgt)
        self._grp.start()

        if self._expanded:
            # Название приложения
            self._logo_label_fade.stop()
            self._logo_label_fade.setStartValue(self._logo_label_opacity.opacity())
            self._logo_label_fade.setEndValue(1.0)
            QTimer.singleShot(60, self._logo_label_fade.start)
            # Пункты меню
            for i, item in enumerate(self._items):
                item.show_label(True, delay_ms=20 + i * 18)
        else:
            # Название приложения
            self._logo_label_fade.stop()
            self._logo_label_fade.setStartValue(self._logo_label_opacity.opacity())
            self._logo_label_fade.setEndValue(0.0)
            self._logo_label_fade.start()
            # Пункты меню
            for item in self._items:
                item.show_label(False)

    def _on_done(self):
        w = SB_EXPANDED if self._expanded else SB_COLLAPSED
        self.setFixedWidth(w)

    def _init_expanded(self):
        """Вызывается после добавления всех пунктов — показывает метки без анимации."""
        self._logo_label_opacity.setOpacity(1.0)
        for item in self._items:
            item.show_label(True, delay_ms=0)

    def activate_first(self):
        if self._items:
            self._items[0]._on_clicked()

    def activate_by_key(self, icon_key: str):
        for item in self._items:
            if item._icon_key == icon_key:
                _set_active(item)
                item.setChecked(True)
                item._refresh()
                break
