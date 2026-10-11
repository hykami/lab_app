"""
Настройки → Персонал.
Список работников (drag source) + 4 смены (drop targets).
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, QMimeData, QByteArray
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from ui.pages.base_page import BasePage
from ui.style_helpers import card_style, input_style, label_muted_style
from ui.theme import (
    BG_CARD, BORDER, TEXT_MUTED,
    ACCENT_V, ACCENT_R, ACCENT_ICON,
    FONT_MONO, FONT_UI,
)
from logic.db_service import (
    Worker, Shift,
    get_all_workers, get_all_shifts,
    add_worker, delete_worker,
    set_shift_workers, rename_shift,
)

MIME_WORKER = "application/x-worker-id"


# ── Диалог добавления работника ───────────────────────────────────────────────

class _AddWorkerDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить работника")
        self.setFixedSize(320, 130)
        self.setStyleSheet(f"background: {BG_CARD};")
        lay = QVBoxLayout(self); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(14)

        self._name = QLineEdit(); self._name.setPlaceholderText("Фамилия И.О.")
        self._name.setFixedHeight(36); self._name.setStyleSheet(input_style(height=36, font_size=13))
        lay.addWidget(self._name)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        btns.setStyleSheet(f"""
            QPushButton {{ background: {BG_CARD}; border: 0.5px solid {BORDER};
            border-radius: 6px; color: {TEXT_MUTED};
            font-family: '{FONT_MONO}', monospace; font-size: 12px; padding: 5px 16px; min-width: 70px; }}
            QPushButton:default {{ background: rgba(108,92,231,0.15);
            border-color: rgba(108,92,231,0.4); color: {ACCENT_V}; }}
        """)
        lay.addWidget(btns)

    @property
    def worker_name(self) -> str:
        return self._name.text().strip()


# ── Перетаскиваемый чип работника ─────────────────────────────────────────────

class _WorkerChip(QFrame):
    """Чип в списке всех работников — можно перетаскивать."""

    def __init__(self, worker: Worker, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.worker = worker
        self.setStyleSheet("""
            QFrame { background: #18181c; border: none; border-radius: 6px; }
            QFrame:hover { background: #1e1e24; }
        """)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        lay = QHBoxLayout(self); lay.setContentsMargins(10, 6, 6, 6); lay.setSpacing(6)

        drag_icon = QLabel("⠿")
        drag_icon.setStyleSheet("color: #4a4a58; font-size: 12px; background: transparent; border: none;")
        lay.addWidget(drag_icon)

        name = QLabel(worker.name)
        name.setStyleSheet(f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; background: transparent; border: none;")
        lay.addWidget(name, 1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(MIME_WORKER, QByteArray(str(self.worker.id).encode()))
            mime.setText(self.worker.name)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction)


# ── Работник внутри смены ─────────────────────────────────────────────────────

class _ShiftWorkerRow(QWidget):
    """Строка работника внутри карточки смены с кнопкой удаления."""

    def __init__(self, worker: Worker, on_remove: callable,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.worker = worker
        self.setStyleSheet("background: transparent; border: none;")

        lay = QHBoxLayout(self); lay.setContentsMargins(10, 3, 6, 3); lay.setSpacing(6)

        name = QLabel(worker.name)
        name.setStyleSheet(f"color: {TEXT_MUTED}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; background: transparent; border: none;")
        lay.addWidget(name, 1)

        rm = QPushButton("✕"); rm.setFixedSize(18, 18)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: #4a4a58; font-size: 11px; border-radius: 3px; }}
            QPushButton:hover {{ color: {ACCENT_R}; background: rgba(248,113,113,0.08); }}
        """)
        rm.clicked.connect(on_remove)
        lay.addWidget(rm)


# ── Карточка смены (drop target) ──────────────────────────────────────────────

class _ShiftCard(QFrame):
    SHIFT_COLORS = [
        ("#6c5ce7", "rgba(108,92,231,0.08)", "rgba(108,92,231,0.25)"),
        ("#4ade80", "rgba(74,222,128,0.06)",  "rgba(74,222,128,0.2)"),
        ("#60a5fa", "rgba(96,165,250,0.06)",  "rgba(96,165,250,0.2)"),
        ("#facc15", "rgba(250,204,21,0.06)",  "rgba(250,204,21,0.2)"),
    ]

    def __init__(self, shift: Shift, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._shift = shift
        self._worker_ids: list[int] = [w.id for w in shift.workers]
        self._workers_map: dict[int, Worker] = {w.id: w for w in shift.workers}

        idx = (shift.number - 1) % 4
        self._color, self._bg, self._border = self.SHIFT_COLORS[idx]

        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}")

        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # Заголовок
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {self._bg}; border-radius: 10px 10px 0 0; border-bottom: 0.5px solid {BORDER};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12, 8, 12, 8)

        self._name_inp = QLineEdit(shift.name)
        self._name_inp.setFixedHeight(24)
        self._name_inp.setStyleSheet(f"""
            QLineEdit {{ background: transparent; border: none;
            border-bottom: 0.5px solid transparent;
            color: {self._color}; font-family: '{FONT_MONO}', monospace;
            font-size: 12px; letter-spacing: 0.04em; padding: 0; }}
            QLineEdit:focus {{ border-bottom-color: {self._color}; }}
        """)
        self._name_inp.editingFinished.connect(self._on_rename)
        hl.addWidget(self._name_inp, 1)

        self._count_lbl = QLabel(f"{len(shift.workers)} чел.")
        self._count_lbl.setStyleSheet(
            f"color: {self._color}; font-family: '{FONT_MONO}', monospace; font-size: 11px;"
            f"background: transparent; border: none;"
        )
        hl.addWidget(self._count_lbl)
        lay.addWidget(hdr)

        # Тело с работниками
        self._body = QWidget(); self._body.setStyleSheet("background: transparent; border: none;")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0, 4, 0, 6); self._body_lay.setSpacing(0)

        self._drop_hint = QLabel("Перетащите работника сюда")
        self._drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint.setStyleSheet(f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif; font-size: 11px; background: transparent; padding: 12px 0;")
        self._body_lay.addWidget(self._drop_hint)

        lay.addWidget(self._body)
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            if item.widget(): item.widget().setParent(None)

        if not self._worker_ids:
            self._body_lay.addWidget(self._drop_hint)
            self._drop_hint.show()
        else:
            self._drop_hint.hide()
            for wid in self._worker_ids:
                w = self._workers_map.get(wid)
                if w:
                    row = _ShiftWorkerRow(w, lambda _, i=wid: self._remove_worker(i))
                    self._body_lay.addWidget(row)

        self._count_lbl.setText(f"{len(self._worker_ids)} чел.")

    def _remove_worker(self, worker_id: int) -> None:
        if worker_id in self._worker_ids:
            self._worker_ids.remove(worker_id)
            self._workers_map.pop(worker_id, None)
            self._refresh_rows()

    def _on_rename(self) -> None:
        name = self._name_inp.text().strip()
        if name:
            rename_shift(self._shift.id, name)

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_WORKER):
            self.setStyleSheet(
                f"QFrame {{ background: {BG_CARD}; border: 1.5px solid {self._color}; border-radius: 10px; }}"
            )
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}")

    def dropEvent(self, event) -> None:
        self.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 0.5px solid {BORDER}; border-radius: 10px; }}")
        data = event.mimeData().data(MIME_WORKER)
        try:
            worker_id = int(bytes(data).decode())
        except ValueError:
            return
        if worker_id not in self._worker_ids:
            from logic.db_service import get_all_workers
            all_workers = {w.id: w for w in get_all_workers()}
            worker = all_workers.get(worker_id)
            if worker:
                self._worker_ids.append(worker_id)
                self._workers_map[worker_id] = worker
                self._refresh_rows()
        event.acceptProposedAction()

    # ── Сохранение ────────────────────────────────────────────────────────────

    def save(self) -> None:
        set_shift_workers(self._shift.id, self._worker_ids)


# ── Страница ──────────────────────────────────────────────────────────────────

class PersonnelPage(BasePage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Персонал",
            subtitle="",
            section="Настройки",
            actions=[("Сохранить", True)],
        )
        self._shift_cards: list[_ShiftCard] = []
        self._built = False
        self._action_buttons["Сохранить"].clicked.connect(self._on_save)
        self._build_ui()

    def _build_ui(self) -> None:
        self._built = True
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._shift_cards.clear()

        workers = get_all_workers()
        shifts  = get_all_shifts()

        main = QHBoxLayout(); main.setSpacing(14); main.setContentsMargins(0, 0, 0, 0)

        # ── Левая панель: список работников ───────────────────────────────────
        left = QFrame(); left.setStyleSheet(card_style()); left.setFixedWidth(230)
        ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(0)

        lhdr = QWidget()
        lhdr.setStyleSheet(f"background: rgba(108,92,231,0.05); border-radius: 10px 10px 0 0; border-bottom: 0.5px solid {BORDER};")
        lhl = QHBoxLayout(lhdr); lhl.setContentsMargins(14, 10, 10, 10)
        lt = QLabel("РАБОТНИКИ")
        lt.setStyleSheet(f"color: {ACCENT_ICON}; font-family: '{FONT_UI}', sans-serif; font-size: 12px; letter-spacing: 0.04em; background: transparent; border: none;")
        lhl.addWidget(lt); lhl.addStretch()

        add_btn = QPushButton("+ Добавить")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(24)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(108,92,231,0.1); border: 0.5px solid rgba(108,92,231,0.3);
            border-radius: 5px; color: {ACCENT_ICON};
            font-family: '{FONT_UI}', sans-serif; font-size: 11px; padding: 0 10px; }}
            QPushButton:hover {{ background: rgba(108,92,231,0.18); }}
        """)
        add_btn.clicked.connect(self._on_add_worker)
        lhl.addWidget(add_btn)
        ll.addWidget(lhdr)

        hint = QLabel("Перетащите имя в нужную смену →")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: #4a4a58; font-family: '{FONT_UI}', sans-serif; font-size: 12px; padding: 8px 14px 4px; background: transparent; border: none;")
        ll.addWidget(hint)

        self._workers_body = QWidget(); self._workers_body.setStyleSheet("background: transparent; border: none;")
        self._workers_lay  = QVBoxLayout(self._workers_body)
        self._workers_lay.setContentsMargins(8, 4, 8, 10); self._workers_lay.setSpacing(4)
        self._populate_workers(workers)
        ll.addWidget(self._workers_body)
        ll.addStretch()
        main.addWidget(left)

        # ── Правая часть: 4 смены 2×2 ─────────────────────────────────────────
        right = QWidget(); right.setStyleSheet("background: transparent;")
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)

        for row_idx in range(2):
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            row_l = QHBoxLayout(row_w); row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(10)
            for col_idx in range(2):
                s_idx = row_idx * 2 + col_idx
                if s_idx < len(shifts):
                    card = _ShiftCard(shifts[s_idx])
                    self._shift_cards.append(card)
                    row_l.addWidget(card)
            rl.addWidget(row_w)

        rl.addStretch()
        main.addWidget(right, 1)

        mw = QWidget(); mw.setStyleSheet("background: transparent;"); mw.setLayout(main)
        self._content_layout.addWidget(mw, 1)

    def _populate_workers(self, workers: list[Worker]) -> None:
        while self._workers_lay.count():
            item = self._workers_lay.takeAt(0)
            if item.widget(): item.widget().setParent(None)

        if not workers:
            ph = QLabel("Нет работников")
            ph.setStyleSheet(label_muted_style(11) + " border: none;")
            self._workers_lay.addWidget(ph)
            return

        for w in workers:
            row = QWidget(); row.setStyleSheet("background: transparent; border: none;")
            rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(4)

            chip = _WorkerChip(w)
            rl.addWidget(chip, 1)

            del_btn = QPushButton("✕"); del_btn.setFixedSize(22, 34)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; color: #4a4a58; font-size: 12px; }
                QPushButton:hover { color: #f87171; }
            """)
            del_btn.clicked.connect(lambda _, wid=w.id, wname=w.name: self._on_delete_worker(wid, wname))
            rl.addWidget(del_btn)
            self._workers_lay.addWidget(row)

    def _on_add_worker(self) -> None:
        dlg = _AddWorkerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.worker_name
            if not name:
                return
            try:
                add_worker(name)
                self._build_ui()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def _on_delete_worker(self, wid: int, name: str) -> None:
        reply = QMessageBox.question(
            self, "Удалить работника",
            f"Удалить «{name}»? Он будет удалён из всех смен.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_worker(wid)
            self._build_ui()

    def _on_save(self) -> None:
        for card in self._shift_cards:
            card.save()
        self._action_buttons["Сохранить"].flash_success("✓ Сохранено")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._built:
            self._built = True
