"""真實剪貼簿的備份 / 還原往返測試（會暫時改動你的剪貼簿，結束後還原）。"""

import ctypes
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

if sys.platform == "win32":
    import selection
    import winapi as w


def _set(items):
    assert selection._open_clipboard()
    try:
        w.user32.EmptyClipboard()
        for fmt, data in items:
            assert selection._write_format(fmt, data)
    finally:
        w.user32.CloseClipboard()


def _snapshot():
    b = selection.backup_clipboard()
    assert b is not None
    return dict(b.items)


@pytest.fixture(autouse=True)
def preserve_user_clipboard():
    original = selection.backup_clipboard()
    yield
    if original is not None:
        selection.restore_clipboard(original)


def _utf16(s):
    return s.encode("utf-16-le") + b"\x00\x00"


HTML = w.user32.RegisterClipboardFormatW("HTML Format") if sys.platform == "win32" else 0


def test_text_roundtrip():
    _set([(w.CF_UNICODETEXT, _utf16("原本的文字 abc"))])
    backup = selection.backup_clipboard()
    _set([(w.CF_UNICODETEXT, _utf16("被覆寫"))])
    assert selection.restore_clipboard(backup)
    assert _snapshot()[w.CF_UNICODETEXT] == _utf16("原本的文字 abc")


def test_text_and_html_roundtrip():
    html = b"Version:0.9\r\nStartHTML:0\r\n<b>hi</b>"
    _set([(w.CF_UNICODETEXT, _utf16("hi")), (HTML, html)])
    backup = selection.backup_clipboard()
    _set([(w.CF_UNICODETEXT, _utf16("other"))])
    selection.restore_clipboard(backup)
    snap = _snapshot()
    assert snap[w.CF_UNICODETEXT] == _utf16("hi") and snap[HTML] == html


def test_dib_roundtrip():
    header = ctypes.create_string_buffer(40)
    ctypes.memmove(header, (ctypes.c_uint32 * 1)(40), 4)          # biSize
    ctypes.memmove(ctypes.addressof(header) + 4, (ctypes.c_int32 * 2)(2, 2), 8)   # 2x2
    ctypes.memmove(ctypes.addressof(header) + 12, (ctypes.c_uint16 * 2)(1, 24), 4)
    pixels = bytes(range(16))                                      # 2 列 x 8 bytes(含 padding)
    dib = header.raw + pixels
    _set([(w.CF_DIB, dib)])
    backup = selection.backup_clipboard()
    _set([(w.CF_UNICODETEXT, _utf16("x"))])
    selection.restore_clipboard(backup)
    assert _snapshot()[w.CF_DIB] == dib


def test_hdrop_roundtrip():
    # DROPFILES(20 bytes): pFiles=20, pt=(0,0), fNC=0, fWide=1；之後是 UTF-16 檔名清單
    drop = (20).to_bytes(4, "little") + bytes(12) + (1).to_bytes(4, "little")
    drop += "C:\\a.txt".encode("utf-16-le") + b"\x00\x00\x00\x00"
    _set([(w.CF_HDROP, drop)])
    backup = selection.backup_clipboard()
    _set([(w.CF_UNICODETEXT, _utf16("x"))])
    selection.restore_clipboard(backup)
    assert _snapshot()[w.CF_HDROP] == drop


def test_empty_clipboard_stays_empty():
    _set([])
    backup = selection.backup_clipboard()
    assert backup is not None and backup.is_empty
    _set([(w.CF_UNICODETEXT, _utf16("x"))])
    selection.restore_clipboard(backup)
    assert _snapshot() == {}

