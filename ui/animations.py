"""
Утилиты анимаций для UI Lab App.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import (
    QPropertyAnimation, QEasingCurve, QTimer,
    QSequentialAnimationGroup, QParallelAnimationGroup,
    pyqtProperty, Qt,
)
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PyQt6.QtGui import QColor


# ── 1. Fade-in виджета ────────────────────────────────────────────────────────

def fade_in(widget: QWidget, duration: int = 180, start: float = 0.0) -> None:
    """Снимает любой графический эффект и просто показывает виджет.
    QGraphicsOpacityEffect отключён намеренно — провоцирует конфликты QPainter
    при сложной иерархии виджетов."""
    if widget.graphicsEffect() is not None:
        widget.setGraphicsEffect(None)
    widget.setVisible(True)


def fade_out(widget: QWidget, duration: int = 140, on_done=None) -> None:
    """Скрывает виджет без анимации (см. fade_in)."""
    if widget.graphicsEffect() is not None:
        widget.setGraphicsEffect(None)
    widget.setVisible(False)
    if on_done:
        on_done()


# ── 2. Анимация значений (число съезжает сверху) ─────────────────────────────

def animate_label_value(label, new_text: str, duration: int = 220) -> None:
    """Меняет текст QLabel. Без graphics-эффектов — чтобы избежать
    конфликтов QPainter с offscreen-рендерингом QGraphicsOpacityEffect."""
    # Снимаем любой остаточный graphics effect (мог остаться от прежних версий)
    if label.graphicsEffect() is not None:
        label.setGraphicsEffect(None)
    label.setText(new_text)


# ── 3. Staggered fade-in для списка виджетов ─────────────────────────────────

def stagger_fade_in(widgets: list[QWidget],
                    duration: int = 160,
                    step_ms: int = 35,
                    start_delay: int = 0) -> None:
    """Показывает виджеты сразу. Анимация отключена намеренно (см. fade_in)."""
    for widget in widgets:
        if widget.graphicsEffect() is not None:
            widget.setGraphicsEffect(None)
        widget.setVisible(True)


# ── 4. Fade для прогресс-бара (появление/исчезновение) ───────────────────────

def fade_in_progress(widget: QWidget, duration: int = 200) -> None:
    if widget.graphicsEffect() is not None:
        widget.setGraphicsEffect(None)
    widget.setVisible(True)


def fade_out_progress(widget: QWidget, duration: int = 300) -> None:
    if widget.graphicsEffect() is not None:
        widget.setGraphicsEffect(None)
    widget.setVisible(False)
