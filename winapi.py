"""Win32 API 的 ctypes 包裝：按鍵注入、剪貼簿、視窗樣式、低階滑鼠 hook。

只在 Windows 上可匯入。所有函式都明確設定 argtypes/restype，確保 64 位元下 handle 不被截斷。
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

# ------------------------------------------------------------------ 常數
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL = 0xA0, 0xA1, 0xA2, 0xA3
VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN = 0xA4, 0xA5, 0x5B, 0x5C
VK_ESCAPE, VK_C, VK_UNASSIGNED = 0x1B, 0x43, 0xE8

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2

CF_TEXT, CF_BITMAP, CF_METAFILEPICT, CF_OEMTEXT = 1, 2, 3, 7
CF_PALETTE, CF_UNICODETEXT, CF_ENHMETAFILE, CF_DIB = 9, 13, 14, 8
CF_LOCALE, CF_DIBV5, CF_HDROP, CF_OWNERDISPLAY = 16, 17, 15, 0x80
GMEM_MOVEABLE = 0x2

GWL_EXSTYLE = -20
WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x8, 0x80, 0x08000000
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x2, 0x10, 0x40

WH_MOUSE_LL = 14
WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN = 0x201, 0x204, 0x207, 0x20B
HWND_MESSAGE = -3


# ------------------------------------------------------------------ 結構
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]   # 需含 mi，sizeof(INPUT) 才正確


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# ------------------------------------------------------------------ 函式原型
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_void_p]
user32.CreateWindowExW.restype = ctypes.c_void_p

user32.OpenClipboard.argtypes = [ctypes.c_void_p]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
user32.EnumClipboardFormats.restype = wintypes.UINT
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.GetOpenClipboardWindow.restype = wintypes.HWND
user32.GetClipboardFormatNameW.argtypes = [wintypes.UINT, wintypes.LPWSTR, ctypes.c_int]
user32.GetClipboardFormatNameW.restype = ctypes.c_int
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wintypes.UINT

kernel32.GetCurrentProcessId.restype = wintypes.DWORD
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.restype = ctypes.c_void_p
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


# ------------------------------------------------------------------ 按鍵注入
_EXTENDED = {VK_RMENU, VK_RCONTROL, VK_LWIN, VK_RWIN}
_MODIFIER_KEYS = (VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL,
                  VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN)


def _key_input(vk: int, up: bool, extended: bool = False) -> INPUT:
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return inp


def send_keys(events: list[tuple[int, bool]]) -> int:
    """以單一 SendInput 呼叫送出一串 (vk, is_key_up)，確保序列不被其他輸入插入。"""
    arr = (INPUT * len(events))(*[_key_input(vk, up, vk in _EXTENDED) for vk, up in events])
    return user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def is_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def held_modifiers() -> list[int]:
    return [vk for vk in _MODIFIER_KEYS if is_down(vk)]


def send_copy() -> None:
    send_keys([(VK_CONTROL, False), (VK_C, False), (VK_C, True), (VK_CONTROL, True)])


def send_menu_mask() -> None:
    """按下再放開一個未指派的虛擬鍵，避免放開 Alt/Win 時觸發功能表列或開始功能表。"""
    send_keys([(VK_UNASSIGNED, False), (VK_UNASSIGNED, True)])


def wait_modifiers_released(timeout: float = 0.15, poll: float = 0.005) -> bool:
    """等使用者放開修飾鍵；逾時則對仍按著的鍵送出 key-up。回傳是否自然放開。"""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if not held_modifiers():
            return True
        time.sleep(poll)
    still = held_modifiers()
    if still:
        send_keys([(vk, True) for vk in still])
    return not still


def vk_from_char(ch: str) -> int:
    """目前鍵盤配置下，字元對應的虛擬鍵碼（例如 '`' -> 0xC0）；找不到回傳 0。"""
    res = user32.VkKeyScanW(ch)
    return 0 if res == -1 else res & 0xFF


# ------------------------------------------------------------------ 視窗
def cursor_in_window(hwnd: int, x: int, y: int) -> bool:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    return rect.left <= x < rect.right and rect.top <= y < rect.bottom


def make_noactivate_topmost(hwnd: int) -> None:
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)


def raise_topmost_noactivate(hwnd: int) -> None:
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)


def foreground_window() -> int:
    return user32.GetForegroundWindow() or 0


_owner_hwnd: int | None = None


def clipboard_owner_hwnd() -> int:
    """剪貼簿擁有者視窗（隱藏的 message-only 視窗）。

    OpenClipboard(NULL) 之後 EmptyClipboard 會使 SetClipboardData 失敗，所以需要真實 hwnd。
    視窗隨建立它的執行緒結束而被銷毀，因此必須在長壽的主執行緒（程式啟動時）先呼叫一次；
    之後若發現視窗已失效會重建，避免所有剪貼簿操作永久失敗。
    """
    global _owner_hwnd
    if not _owner_hwnd or not user32.IsWindow(_owner_hwnd):
        _owner_hwnd = user32.CreateWindowExW(
            0, "STATIC", None, 0, 0, 0, 0, 0, HWND_MESSAGE, None, None, None) or 0
    return _owner_hwnd


def clipboard_holder() -> str:
    """診斷用：目前開啟著剪貼簿的視窗（行程 id 與標題）。"""
    hwnd = user32.GetOpenClipboardWindow()
    if not hwnd:
        return "unknown (no window)"
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    buf = ctypes.create_unicode_buffer(128)
    user32.GetWindowTextW(hwnd, buf, 128)
    return f"pid={pid.value} title={buf.value!r} self={pid.value == kernel32.GetCurrentProcessId()}"


# ------------------------------------------------------------------ 低階滑鼠 hook
class MouseClickHook:
    """WH_MOUSE_LL：任何滑鼠按下事件都回呼 on_click(x, y)（實體像素座標）。

    回呼一律放行事件（CallNextHookEx），不吞掉使用者的點擊。必須在有訊息迴圈的執行緒安裝。
    """

    def __init__(self, on_click):
        self._on_click = on_click
        self._hook: int | None = None
        self._proc = HOOKPROC(self._callback)   # 需保留參考，避免被回收

    def _callback(self, n_code, w_param, l_param):
        if n_code >= 0 and w_param in (WM_LBUTTONDOWN, WM_RBUTTONDOWN,
                                       WM_MBUTTONDOWN, WM_XBUTTONDOWN):
            info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            try:
                self._on_click(info.pt.x, info.pt.y)
            except Exception:       # hook 內例外不可外洩
                pass
        return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

    def install(self) -> None:
        if self._hook is None:
            self._hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL, self._proc, kernel32.GetModuleHandleW(None), 0)

    def uninstall(self) -> None:
        if self._hook is not None:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
