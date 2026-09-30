"""取得目前反白的文字：模擬 Ctrl+C，讀取剪貼簿，再完整還原原剪貼簿。

capture() 可在背景執行緒呼叫。流程與限制見 README / 計畫文件的「剪貼簿備份與還原」。
"""

from __future__ import annotations

import ctypes
import logging
import time
from dataclasses import dataclass, field

import winapi as w

log = logging.getLogger(__name__)

MAX_BACKUP_BYTES = 16 * 1024 * 1024
BACKUP_TIME_BUDGET = 0.100      # 秒
COPY_TIMEOUT = 0.800            # 秒（實際值由 config.copy_timeout_ms 傳入）
POLL_INTERVAL = 0.010           # 秒
RETRY_AFTER = 0.300             # 秒：這段時間沒有變化就補送一次 Ctrl+C
SETTLE_TIMEOUT = 0.250          # 序號改變後等待文字寫入的上限（秒）
OPEN_RETRIES = 10

# GDI handle 類與顯示用格式：不是 HGLOBAL，無法以 bytes 備份
_SKIP_FORMATS = {w.CF_BITMAP, w.CF_METAFILEPICT, w.CF_ENHMETAFILE, w.CF_PALETTE,
                 w.CF_OWNERDISPLAY, 0x81, 0x82, 0x83}
# 由系統依其他格式自動合成，還原時不必（也不該）重複寫入
_SYNTHESIZED = {w.CF_TEXT, w.CF_OEMTEXT, w.CF_LOCALE}
_SKIP_NAMES = {"DataObject", "OleClipboardPersistOnFlush"}   # OLE 物件，非單純記憶體區塊
_HTML_NAME, _RTF_NAME = "HTML Format", "Rich Text Format"

OK, NO_SELECTION, CLIPBOARD_BUSY = "ok", "no_selection", "clipboard_busy"


@dataclass
class CaptureResult:
    status: str
    text: str | None = None
    timings: dict[str, float] = field(default_factory=dict)


@dataclass
class ClipboardBackup:
    items: list[tuple[int, bytes]]
    partial: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.items


# ------------------------------------------------------------------ 底層剪貼簿
def _open_clipboard() -> bool:
    for _ in range(OPEN_RETRIES):
        if w.user32.OpenClipboard(w.clipboard_owner_hwnd()):
            return True
        time.sleep(0.010)
    log.warning("OpenClipboard failed after %d tries; held by %s", OPEN_RETRIES, w.clipboard_holder())
    return False


def _format_name(fmt: int) -> str:
    buf = ctypes.create_unicode_buffer(128)
    n = w.user32.GetClipboardFormatNameW(fmt, buf, 128)
    return buf.value if n else ""


def _read_handle(handle: int) -> bytes | None:
    size = w.kernel32.GlobalSize(handle)
    if not size:
        return None
    ptr = w.kernel32.GlobalLock(handle)
    if not ptr:
        return None
    try:
        return ctypes.string_at(ptr, size)
    finally:
        w.kernel32.GlobalUnlock(handle)


def _write_format(fmt: int, data: bytes) -> bool:
    h = w.kernel32.GlobalAlloc(w.GMEM_MOVEABLE, max(len(data), 1))
    if not h:
        return False
    ptr = w.kernel32.GlobalLock(h)
    if not ptr:
        w.kernel32.GlobalFree(h)
        return False
    ctypes.memmove(ptr, data, len(data))
    w.kernel32.GlobalUnlock(h)
    if not w.user32.SetClipboardData(fmt, h):
        w.kernel32.GlobalFree(h)        # 設定失敗時所有權仍在我們手上
        return False
    return True


def _priority(fmt: int, name: str) -> int:
    if fmt == w.CF_UNICODETEXT:
        return 0
    if name == _HTML_NAME:
        return 1
    if name == _RTF_NAME:
        return 2
    if fmt in (w.CF_DIB, w.CF_DIBV5):
        return 3
    if fmt == w.CF_HDROP:
        return 4
    return 5


# ------------------------------------------------------------------ 備份 / 讀取 / 還原
def backup_clipboard() -> ClipboardBackup | None:
    """備份目前剪貼簿；無法開啟剪貼簿時回傳 None。"""
    if not _open_clipboard():
        return None
    try:
        formats: list[tuple[int, str]] = []
        fmt = 0
        while True:
            fmt = w.user32.EnumClipboardFormats(fmt)
            if not fmt:
                break
            name = _format_name(fmt) if fmt >= 0xC000 else ""
            if fmt in _SKIP_FORMATS or fmt in _SYNTHESIZED or name in _SKIP_NAMES:
                continue
            if 0x300 <= fmt <= 0x3FF:           # GDI 物件範圍
                continue
            formats.append((fmt, name))
        present = {f for f, _ in formats}
        if w.CF_DIB in present:                  # DIB 與 DIBV5 可互相合成，保留較小的 DIB
            formats = [(f, n) for f, n in formats if f != w.CF_DIBV5]
        formats.sort(key=lambda fn: _priority(*fn))     # sort 穩定：同優先序維持原順序

        items: list[tuple[int, bytes]] = []
        total = 0
        partial = False
        start = time.perf_counter()
        for fmt, name in formats:
            if items and (time.perf_counter() - start > BACKUP_TIME_BUDGET
                          or total >= MAX_BACKUP_BYTES):
                partial = True
                break
            handle = w.user32.GetClipboardData(fmt)
            data = _read_handle(handle) if handle else None
            if data is None:
                continue
            if total + len(data) > MAX_BACKUP_BYTES and fmt != w.CF_UNICODETEXT:
                partial = True
                continue
            items.append((fmt, data))
            total += len(data)
        if partial:
            log.warning("clipboard backup partial: kept %d formats, %d bytes", len(items), total)
        return ClipboardBackup(items, partial)
    finally:
        w.user32.CloseClipboard()


def _read_text() -> str | None:
    if not _open_clipboard():
        return None
    try:
        handle = w.user32.GetClipboardData(w.CF_UNICODETEXT)
        data = _read_handle(handle) if handle else None
        if not data:
            return None
        return data.decode("utf-16-le", errors="replace").split("\x00", 1)[0]
    finally:
        w.user32.CloseClipboard()


def restore_clipboard(backup: ClipboardBackup) -> bool:
    if not _open_clipboard():
        log.error("clipboard restore failed: cannot open clipboard")
        return False
    try:
        w.user32.EmptyClipboard()
        ok = True
        for fmt, data in backup.items:
            ok &= _write_format(fmt, data)
        if backup.items:
            # 告知剪貼簿歷史 / 雲端同步不要記錄這次「還原」動作
            for name, payload in (("ExcludeClipboardContentFromMonitorProcessing", b"\x00\x00\x00\x00"),
                                  ("CanIncludeInClipboardHistory", b"\x00\x00\x00\x00")):
                _write_format(w.user32.RegisterClipboardFormatW(name), payload)
        if not ok:
            log.warning("clipboard restore: some formats failed")
        return ok
    finally:
        w.user32.CloseClipboard()


# ------------------------------------------------------------------ 主流程
def capture(copy_timeout: float = COPY_TIMEOUT) -> CaptureResult:
    """模擬複製並取得反白文字。任何情況下都會嘗試還原原剪貼簿。"""
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    w.wait_modifiers_released()
    timings["modifiers"] = time.perf_counter() - t0

    t = time.perf_counter()
    backup = backup_clipboard()
    timings["backup"] = time.perf_counter() - t
    if backup is None:
        return CaptureResult(CLIPBOARD_BUSY, timings=timings)

    seq0 = w.user32.GetClipboardSequenceNumber()
    changed = False
    text: str | None = None
    try:
        t = time.perf_counter()
        w.send_copy()
        deadline = time.perf_counter() + copy_timeout
        retry_at = time.perf_counter() + RETRY_AFTER
        changed_at: float | None = None
        while time.perf_counter() < deadline:
            # 目標程式開啟剪貼簿的瞬間若被別的程式（剪貼簿歷史、監聽程式）占用，會直接放棄複製；
            # 一段時間沒有變化就補送一次 Ctrl+C（重複複製同一段選取內容是無害的）
            if retry_at and time.perf_counter() >= retry_at and                     w.user32.GetClipboardSequenceNumber() == seq0:
                w.send_copy()
                retry_at = 0.0
                timings["retried"] = 1.0
            if w.user32.GetClipboardSequenceNumber() != seq0:
                changed = True
                if changed_at is None:
                    changed_at = time.perf_counter()
                # 有些程式先 EmptyClipboard（序號已增加）才寫入資料，序號一變就讀會讀到空的；
                # 讀不到文字時再等一小段，超過 SETTLE_TIMEOUT 仍沒有文字才視為非文字內容
                text = _read_text()
                if text and text.strip():
                    break
                if time.perf_counter() - changed_at > SETTLE_TIMEOUT:
                    break
            time.sleep(POLL_INTERVAL)
        timings["copy_wait"] = time.perf_counter() - t
    finally:
        if changed:
            t = time.perf_counter()
            restore_clipboard(backup)
            timings["restore"] = time.perf_counter() - t

    if not changed:
        return CaptureResult(NO_SELECTION, timings=timings)
    if not text or not text.strip():
        return CaptureResult(NO_SELECTION, timings=timings)
    return CaptureResult(OK, text, timings)
