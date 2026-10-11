"""
StyledComboBox — QComboBox с гарантированно скруглённым стилизованным popup.

Работает в обоих режимах:
  • setEditable(False) — обычный popup
  • setEditable(True)  — popup через QCompleter

При переключении в editable Qt подменяет view() своим — поэтому мы
переустанавливаем кастомный QListView в showPopup() каждый раз.
"""

from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QListView
from ui.theme import BORDER, TEXT_MAIN, FONT_UI


_POPUP_STYLE_TEMPLATE = """
    QListView, QAbstractItemView {{
        background: #18181c;
        border: 0.5px solid {border};
        border-radius: 8px;
        color: {text};
        font-family: '{font}', sans-serif;
        font-size: {size}px;
        padding: 4px;
        outline: none;
    }}
    QListView::item, QAbstractItemView::item {{
        border-radius: 5px;
        padding: 4px 8px;
        min-height: 22px;
    }}
    QListView::item:selected, QAbstractItemView::item:selected {{
        background: rgba(108,92,231,0.18);
        color: #c8bfff;
    }}
    QListView::item:hover:!selected, QAbstractItemView::item:hover:!selected {{
        background: rgba(108,92,231,0.08);
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 4px 2px 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: #4a4a58;
        border-radius: 3px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #5a5a72;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
        width: 0;
        background: transparent;
        border: none;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
"""


def _apply_frameless(popup_window) -> None:
    """Делает окно popup без системной рамки и с прозрачным фоном."""
    popup_window.setWindowFlags(
        Qt.WindowType.Popup |
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.NoDropShadowWindowHint
    )
    popup_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    popup_window.setStyleSheet("background: transparent;")


class StyledComboBox(QComboBox):
    """QComboBox с кастомным скруглённым popup. Работает для editable и обычного режима."""

    def __init__(self, font_size: int = 13, parent=None):
        super().__init__(parent)
        self._popup_font_size = font_size
        self._install_styled_view()

    def _stylesheet(self) -> str:
        return _POPUP_STYLE_TEMPLATE.format(
            border=BORDER,
            text=TEXT_MAIN,
            font=FONT_UI,
            size=self._popup_font_size,
        )

    def _install_styled_view(self) -> None:
        """Создаёт и устанавливает стилизованный QListView как popup view."""
        view = QListView()
        view.setStyleSheet(self._stylesheet())
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setView(view)

    def setEditable(self, editable: bool) -> None:
        super().setEditable(editable)
        if editable:
            completer = self.completer()
            if completer is not None:
                popup = completer.popup()
                if popup is not None:
                    popup.setStyleSheet(self._stylesheet())
                    popup.setHorizontalScrollBarPolicy(
                        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                    )
        # Переустанавливаем основной view
        self._install_styled_view()

    def showPopup(self) -> None:
        # Стилизуем completer popup перед его показом (editable режим)
        if self.isEditable():
            completer = self.completer()
            if completer is not None:
                popup = completer.popup()
                if popup is not None:
                    popup.setStyleSheet(self._stylesheet())
                    popup.setHorizontalScrollBarPolicy(
                        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                    )
                    _apply_frameless(popup.window())

        super().showPopup()

        # Основной popup (нередактируемый режим)
        _apply_frameless(self.view().window())
        self.view().window().show()
