"""進入點：系統匣常駐；快捷鍵 → 模擬複製 → 查字典 → 浮窗。"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import threading
import time

from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

import config
import selection
import winapi
import textclean
from dictionary import Dictionary
from hotkey import HotkeyManager
from popup import Popup

log = logging.getLogger("hotkeydict")


def setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(
        config.user_dir() / "hotkeydict.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def make_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#1a73e8"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, 60, 60, 14, 14)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "A")
    p.end()
    return QIcon(pix)


class Bridge(QObject):
    """背景執行緒 → 主執行緒的橋接（Signal 跨執行緒自動排入佇列）。"""
    captured = Signal(object, QPoint)


class App(QObject):
    def __init__(self, qapp: QApplication, cfg: config.Config, dictionary: Dictionary):
        super().__init__()
        self.cfg, self.dict = cfg, dictionary
        self.popup = Popup(cfg.font_size, cfg.popup_timeout_sec)
        self.hotkeys = HotkeyManager()
        self.bridge = Bridge()
        self._busy = False
        self._t_trigger = 0.0

        self.hotkeys.install(qapp)
        self.hotkeys.triggered.connect(self.on_hotkey)
        self.hotkeys.escape_pressed.connect(self.popup.hide_popup)
        self.bridge.captured.connect(self.on_captured)
        self.popup.shown.connect(lambda: self.hotkeys.set_escape_enabled(True))
        self.popup.hidden.connect(lambda: self.hotkeys.set_escape_enabled(False))

        self.tray = QSystemTrayIcon(make_icon(), qapp)
        self.tray.setToolTip("HotkeyDict")
        self._menu = QMenu()
        self.hotkey_action = self._menu.addAction("")
        self.hotkey_action.setEnabled(False)
        self._menu.addSeparator()
        self._menu.addAction("結束", qapp.quit)
        self.tray.setContextMenu(self._menu)
        self.tray.show()

        qapp.aboutToQuit.connect(self.hotkeys.unregister)
        self.popup.prewarm()
        self.register_hotkey()

    def register_hotkey(self) -> None:
        active = self.hotkeys.register(self.cfg.hotkey, self.cfg.fallback_hotkeys)
        if active is None:
            self.hotkey_action.setText("快捷鍵註冊失敗")
            self.tray.showMessage("HotkeyDict", "所有快捷鍵都無法註冊，請修改 config.json 的 hotkey。",
                                  QSystemTrayIcon.MessageIcon.Warning, 8000)
            return
        self.hotkey_action.setText(f"快捷鍵：{active}")
        if active != self.cfg.hotkey:
            self.tray.showMessage("HotkeyDict", f"{self.cfg.hotkey} 已被占用，改用 {active}",
                                  QSystemTrayIcon.MessageIcon.Information, 6000)

    # ---- 流程
    def on_hotkey(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._t_trigger = time.perf_counter()
        self.popup.hide_popup()
        cursor = QCursor.pos()
        threading.Thread(target=self._capture_worker, args=(cursor,), daemon=True).start()

    def _capture_worker(self, cursor: QPoint) -> None:
        try:
            result = selection.capture()
        except Exception:
            log.exception("capture failed")
            result = selection.CaptureResult(selection.CLIPBOARD_BUSY)
        self.bridge.captured.emit(result, cursor)

    def on_captured(self, result: selection.CaptureResult, cursor: QPoint) -> None:
        t = time.perf_counter()
        try:
            self._show_result(result, cursor)
        finally:
            result.timings["lookup+show"] = time.perf_counter() - t
            self._busy = False
            total = (time.perf_counter() - self._t_trigger) * 1000
            parts = " ".join(f"{k}={v * 1000:.0f}" for k, v in result.timings.items())
            log.info("status=%s total=%.0fms %s", result.status, total, parts)

    def _show_result(self, result: selection.CaptureResult, cursor: QPoint) -> None:
        if result.status == selection.CLIPBOARD_BUSY:
            self.popup.show_message("剪貼簿忙碌中，請再試一次", cursor)
        elif result.status != selection.OK or not result.text:
            self.popup.show_message("沒有反白文字", cursor)
        elif textclean.is_too_long(result.text):
            self.popup.show_message("選取內容過長，請只反白單字", cursor)
        else:
            t = time.perf_counter()
            entry = self.dict.lookup(result.text)
            result.timings["lookup"] = time.perf_counter() - t
            if entry:
                self.popup.show_entry(entry, cursor)
            else:
                shown = textclean.normalize(result.text) or result.text.strip()
                self.popup.show_message(f"查無此字：{shown[:40]}", cursor)


def main() -> int:
    setup_logging()
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    winapi.clipboard_owner_hwnd()       # 必須在主執行緒建立：視窗會隨建立它的執行緒一起消失
    cfg = config.load()
    try:
        dictionary = Dictionary(cfg.resolved_db_path())
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "HotkeyDict", str(exc))
        return 1
    app = App(qapp, cfg, dictionary)     # noqa: F841  保持參考
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
