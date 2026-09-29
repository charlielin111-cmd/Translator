"""浮窗 UI：無邊框、置頂、不搶焦點；點擊外部或 Esc 關閉。"""

from __future__ import annotations

import html
import re

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

import winapi as w
from dictionary import Entry

CURSOR_OFFSET = (12, 18)
MAX_WIDTH = 420
MAX_LINES = 6

# 繁中 Windows 的預設 UI 字型（微軟正黑體）把重音符號 ˋ ˏ 畫得很寬，音標與英文單字改用 Segoe UI
_LATIN_FONT = "font-family:'Segoe UI','Arial'"

_POS_PREFIX = re.compile(r"^([A-Za-z]+\.)\s*")


def compute_popup_pos(cursor: tuple[int, int], size: tuple[int, int],
                      avail: tuple[int, int, int, int],
                      offset: tuple[int, int] = CURSOR_OFFSET) -> tuple[int, int]:
    """游標右下方優先；右/下超出可用區域就翻到左/上，最後夾回螢幕內。avail=(left, top, right, bottom)。"""
    cx, cy = cursor
    width, height = size
    left, top, right, bottom = avail
    x = cx + offset[0]
    if x + width > right:
        x = cx - offset[0] - width
    y = cy + offset[1]
    if y + height > bottom:
        y = cy - offset[1] - height
    x = max(left, min(x, right - width))
    y = max(top, min(y, bottom - height))
    return x, y


def entry_html(entry: Entry) -> tuple[str, str]:
    """回傳 (標題 HTML, 內文 HTML)。"""
    head = f'<span style="{_LATIN_FONT};font-size:1.45em;font-weight:600">{html.escape(entry.word)}</span>'
    if entry.lemma_from and entry.lemma_from.lower() != entry.word.lower():
        head = f'<span style="{_LATIN_FONT};color:#9aa0a6">{html.escape(entry.lemma_from)} → </span>' + head
    if entry.kk:
        approx = "≈" if entry.kk_src == "approx" else ""
        kk = f"{approx}[{html.escape(entry.kk)}]"
        if entry.kk_alt:
            kk += f" / [{html.escape(entry.kk_alt)}]"
        head += f'&nbsp;&nbsp;<span style="{_LATIN_FONT};color:#8ab4f8">{kk}</span>'

    lines = [ln.strip() for ln in entry.translation.splitlines() if ln.strip()]
    body = []
    for ln in lines[:MAX_LINES]:
        m = _POS_PREFIX.match(ln)
        if m:
            body.append(f'<b style="color:#fdd663">{html.escape(m.group(1))}</b> '
                        f'{html.escape(ln[m.end():])}')
        else:
            body.append(f'<span style="color:#9aa0a6">{html.escape(ln)}</span>')
    if len(lines) > MAX_LINES:
        body.append('<span style="color:#9aa0a6">…</span>')
    return head, "<br>".join(body)


class Popup(QWidget):
    shown = Signal()
    hidden = Signal()

    def __init__(self, font_size: int = 14, timeout_sec: int = 0):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._timeout_ms = max(0, timeout_sec) * 1000
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_popup)
        self._hook = w.MouseClickHook(self._on_global_click)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            "#card{background:#202124;border:1px solid #5f6368;border-radius:10px;}"
            f"QLabel{{color:#e8eaed;font-size:{font_size}pt;background:transparent;}}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(14, 10, 14, 12)
        inner.setSpacing(6)
        self._head = QLabel()
        self._head.setTextFormat(Qt.TextFormat.RichText)
        self._body = QLabel()
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setWordWrap(True)
        self._body.setMaximumWidth(MAX_WIDTH)
        inner.addWidget(self._head)
        inner.addWidget(self._body)
        self.winId()        # 先建立原生視窗，才能設定擴充樣式

    # ---- 顯示內容
    def show_entry(self, entry: Entry, cursor: QPoint) -> None:
        head, body = entry_html(entry)
        self._present(head, body, cursor)

    def show_message(self, text: str, cursor: QPoint) -> None:
        self._present(f'<span style="color:#e8eaed">{html.escape(text)}</span>', "", cursor)

    def _present(self, head: str, body: str, cursor: QPoint) -> None:
        self._head.setText(head)
        self._body.setText(body)
        self._body.setVisible(bool(body))
        self.adjustSize()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        a = screen.availableGeometry()
        x, y = compute_popup_pos((cursor.x(), cursor.y()), (self.width(), self.height()),
                                 (a.left(), a.top(), a.right() + 1, a.bottom() + 1))
        self.move(x, y)
        self.show()
        hwnd = int(self.winId())
        w.make_noactivate_topmost(hwnd)
        w.raise_topmost_noactivate(hwnd)
        self._hook.install()
        if self._timeout_ms:
            self._hide_timer.start(self._timeout_ms)
        self.shown.emit()

    def prewarm(self) -> None:
        """啟動時在螢幕外繪製一次，讓字型、樣式與圖層視窗的一次性成本不落在第一次查字。"""
        self._head.setText("warm [ˋwɔrm]")
        self._body.setText("n. 暖身<br>v. 預熱")
        self.adjustSize()
        self.move(-32000, -32000)
        self.show()
        QApplication.processEvents()
        self.hide()

    # ---- 關閉
    def hide_popup(self) -> None:
        if self.isVisible():
            self.hide()

    def hideEvent(self, event) -> None:
        self._hook.uninstall()
        self._hide_timer.stop()
        self.hidden.emit()
        super().hideEvent(event)

    def _on_global_click(self, x: int, y: int) -> None:
        if not w.cursor_in_window(int(self.winId()), x, y):
            QTimer.singleShot(0, self.hide_popup)      # 不在 hook 回呼內做 UI 操作
