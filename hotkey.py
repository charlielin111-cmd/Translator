"""全域快捷鍵：RegisterHotKey + QAbstractNativeEventFilter。

不使用低階鍵盤 hook：不需常駐 hook、CPU 占用低，而且組合鍵被占用時系統會直接回報失敗。
"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

import winapi as w

log = logging.getLogger(__name__)

_HOTKEY_ID = 0x4B44
_ESC_ID = 0x4B45

_MODS = {"alt": w.MOD_ALT, "ctrl": w.MOD_CONTROL, "control": w.MOD_CONTROL,
         "shift": w.MOD_SHIFT, "win": w.MOD_WIN}
_NAMED_KEYS = {"space": 0x20, "tab": 0x09, "enter": 0x0D, "esc": 0x1B,
               **{f"f{i}": 0x6F + i for i in range(1, 13)}}


def parse_hotkey(spec: str) -> tuple[int, int]:
    """'alt+`' -> (modifiers, vk)。格式錯誤時擲出 ValueError。"""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if len(parts) < 2:
        raise ValueError(f"快捷鍵需包含修飾鍵與主鍵：{spec!r}")
    mods = 0
    for p in parts[:-1]:
        if p not in _MODS:
            raise ValueError(f"未知的修飾鍵 {p!r}：{spec!r}")
        mods |= _MODS[p]
    key = parts[-1]
    if key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    elif len(key) == 1:
        vk = w.vk_from_char(key)
        if not vk:
            raise ValueError(f"目前鍵盤配置找不到按鍵 {key!r}")
    else:
        raise ValueError(f"未知的按鍵 {key!r}：{spec!r}")
    return mods, vk


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, on_hotkey):
        super().__init__()
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", "windows_generic_MSG",
                          b"windows_dispatcher_MSG", "windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == w.WM_HOTKEY:
                self._on_hotkey(int(msg.wParam))
        return False, 0


class HotkeyManager(QObject):
    triggered = Signal()
    escape_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter = _Filter(self._dispatch)
        self.active_spec: str | None = None
        self._active_mods = 0
        self._esc_registered = False

    def install(self, app) -> None:
        app.installNativeEventFilter(self._filter)

    def register(self, primary: str, fallbacks: list[str]) -> str | None:
        """依序嘗試註冊；回傳實際註冊成功的組合（全部失敗回傳 None）。"""
        self.unregister()
        for spec in [primary, *fallbacks]:
            try:
                mods, vk = parse_hotkey(spec)
            except ValueError as exc:
                log.warning("skip hotkey: %s", exc)
                continue
            if w.user32.RegisterHotKey(None, _HOTKEY_ID, mods | w.MOD_NOREPEAT, vk):
                self.active_spec, self._active_mods = spec, mods
                log.info("hotkey registered: %s", spec)
                return spec
            log.warning("hotkey %s unavailable (error %d)", spec, ctypes.get_last_error())
        return None

    def unregister(self) -> None:
        if self.active_spec:
            w.user32.UnregisterHotKey(None, _HOTKEY_ID)
            self.active_spec = None
        self.set_escape_enabled(False)

    def set_escape_enabled(self, enabled: bool) -> None:
        """浮窗顯示期間才攔截 Esc，隱藏後立即釋放，不影響其他程式。"""
        if enabled and not self._esc_registered:
            self._esc_registered = bool(w.user32.RegisterHotKey(None, _ESC_ID, 0, w.VK_ESCAPE))
        elif not enabled and self._esc_registered:
            w.user32.UnregisterHotKey(None, _ESC_ID)
            self._esc_registered = False

    def _dispatch(self, hotkey_id: int) -> None:
        if hotkey_id == _HOTKEY_ID:
            # 放開 Alt/Win 時會觸發功能表列/開始功能表；趁修飾鍵還按著先插入一個無效按鍵
            if self._active_mods & (w.MOD_ALT | w.MOD_WIN):
                w.send_menu_mask()
            self.triggered.emit()
        elif hotkey_id == _ESC_ID:
            self.escape_pressed.emit()
