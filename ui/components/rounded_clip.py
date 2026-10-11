"""
RoundedClipFrame — внешняя рамка master/detail-окна со скруглёнными углами.

Состоит из двух дочерних виджетов:
  • _content — обычный QWidget, на который накладывается QRegion-маска
    со скруглёнными углами; в его layout добавляются все потомки.
  • _border  — прозрачный для мыши overlay поверх _content, который
    рисует непрерывную скруглённую границу через paintEvent.

Такая раздельная схема нужна потому, что QRegion-маска QWidget'а
обрезает в том числе пиксели его собственной CSS-границы, из-за чего
в углах рамка «разрывалась». Теперь граница рисуется отдельным виджетом
поверх и не подвержена клиппингу.

Использование:
    mw = RoundedClipFrame(radius=10)
    mw.set_layout(main)              # вместо setLayout(main)
    parent_layout.addWidget(mw)
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QRegion
from PyQt6.QtWidgets import QLayout, QWidget

from ui.theme import BORDER


class _BorderOverlay(QWidget):
    """Прозрачный для мыши виджет, рисующий скруглённую границу."""

    def __init__(self, radius: int, color: QColor, width: float,
                 parent: QWidget) -> None:
        super().__init__(parent)
        self._radius = radius
        self._color = color
        self._width = width
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color)
        pen.setWidthF(self._width)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = self._width / 2.0
        rect = QRectF(
            inset, inset,
            self.width()  - self._width,
            self.height() - self._width,
        )
        p.drawRoundedRect(rect, self._radius, self._radius)
        p.end()


class RoundedClipFrame(QWidget):
    """Виджет со скруглённой внешней границей и клиппингом содержимого."""

    def __init__(
        self,
        radius: int = 10,
        border_color: str = BORDER,
        border_width: float = 1.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._radius = radius
        self._border_width = border_width

        # Внутренний контейнер: маскируется по скруглению, в его layout
        # добавляются все дочерние виджеты пользователя.
        self._content = QWidget(self)
        self._content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._content.setStyleSheet("background: transparent; border: none;")

        # Overlay для рамки — поверх _content, прозрачен для мыши.
        self._border = _BorderOverlay(
            radius=radius,
            color=QColor(border_color),
            width=border_width,
            parent=self,
        )

    # ── Публичный API ─────────────────────────────────────────────────────────

    def content_layout(self) -> Optional[QLayout]:
        """Возвращает layout внутреннего контейнера (если он установлен)."""
        return self._content.layout()

    def set_layout(self, layout: QLayout) -> None:
        """Устанавливает layout внутреннему контейнеру.

        Используйте вместо setLayout(): нужный layout идёт на _content,
        а не на саму внешнюю обёртку.
        """
        self._content.setLayout(layout)

    # ── Раскладка дочерних виджетов и маска ──────────────────────────────────

    def resizeEvent(self, event):
        # _content и _border всегда занимают всю область виджета.
        self._content.setGeometry(0, 0, self.width(), self.height())
        self._border.setGeometry(0, 0, self.width(), self.height())
        self._border.raise_()
        self._update_mask()
        super().resizeEvent(event)

    def _update_mask(self) -> None:
        r = self._radius
        w, h = self._content.width(), self._content.height()
        if w <= 0 or h <= 0:
            return
        center = QRegion(r, 0, max(0, w - 2 * r), h, QRegion.RegionType.Rectangle)
        middle = QRegion(0, r, w, max(0, h - 2 * r), QRegion.RegionType.Rectangle)
        tl = QRegion(0,         0,         2 * r, 2 * r, QRegion.RegionType.Ellipse)
        tr = QRegion(w - 2 * r, 0,         2 * r, 2 * r, QRegion.RegionType.Ellipse)
        bl = QRegion(0,         h - 2 * r, 2 * r, 2 * r, QRegion.RegionType.Ellipse)
        br = QRegion(w - 2 * r, h - 2 * r, 2 * r, 2 * r, QRegion.RegionType.Ellipse)
        mask = center.united(middle).united(tl).united(tr).united(bl).united(br)
        self._content.setMask(mask)
