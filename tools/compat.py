"""多程式相容性測試：對每個目標程式開一份只含單一單字的測試文件，全選後送出快捷鍵，
檢查「抓到的字、剪貼簿是否還原、前景視窗是否不變、浮窗是否出現、耗時」。

用法：
    python tools/compat.py [chrome edge word pdfx tk] [--shots DIR] [--repeat N]

安全措施：
- 每次注入按鍵前都會確認前景視窗標題含 "compat_test"，否則整個測試中止，不會把按鍵送到別的視窗。
- 收尾只對自己開啟的測試視窗送 WM_CLOSE；Chrome/Edge 使用獨立的暫存 profile，只結束自己啟動的行程樹。
- 測試期間會暫時改動剪貼簿文字內容，結束後還原（僅純文字）。
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import winapi as w  # noqa: E402

u = w.user32
u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.SetForegroundWindow.argtypes = [wintypes.HWND]
u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u.IsIconic.argtypes = [wintypes.HWND]

PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
LOG = Path(os.environ["APPDATA"]) / "HotkeyDict" / "hotkeydict.log"
MARK = "compat_test"
VK_A = 0x41

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
WORD = r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
PDFX = r"C:\Program Files\PDF-XChange\PDF Editor\PXCEditor.exe"

WORDS = {"tk": "running", "chrome": "philosophy", "edge": "resilient",
         "word": "quantum", "pdfx": "opportunity"}


def start_app(env: dict) -> subprocess.Popen:
    """啟動被測程式：預設 python main.py；設定 HOTKEYDICT_EXE 則改測打包後的 exe。"""
    exe = os.environ.get("HOTKEYDICT_EXE")
    if exe:
        if os.environ.get("HOTKEYDICT_CLEAN_ENV"):      # 只留系統目錄，確認不依賴任何 Python 安裝
            keep = ("SystemRoot", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "USERPROFILE",
                    "HOTKEYDICT_LOG_WORDS")
            env = {k: v for k, v in env.items() if k in keep}
            env["PATH"] = os.path.join(env.get("SystemRoot", r"C:\Windows"), "System32")
        return subprocess.Popen([exe], cwd=str(Path(exe).parent), env=env)
    return subprocess.Popen([PY, "main.py"], cwd=ROOT, env=env)


# ------------------------------------------------------------------ 小工具
def title_of(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def find_windows(marker: str) -> list[int]:
    found: list[int] = []

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and marker.lower() in title_of(hwnd).lower():
            found.append(hwnd)
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found


def ps(cmd: str) -> str:
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def guard() -> None:
    t = title_of(w.foreground_window())
    if MARK not in t.lower():
        raise SystemExit(f"ABORT: foreground is not a compat test window: {t!r}")


def ensure_focus(hwnd: int, attempts: int = 3) -> bool:
    """前景不是測試視窗時重新聚焦；多次失敗才中止（安全檢查，避免按鍵送錯視窗）。

    回傳是否發生過重新聚焦（重新聚焦後鍵盤焦點可能落在別的控制項，該輪結果不可靠）。
    """
    refocused = False
    for _ in range(attempts):
        if MARK in title_of(w.foreground_window()).lower():
            return refocused
        refocused = True
        focus(hwnd)
    guard()
    return refocused


def focus(hwnd: int, tries: int = 6) -> bool:
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)
    for _ in range(tries):
        w.send_menu_mask()              # 無害的輸入事件，讓本行程取得設定前景視窗的權限
        u.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        if w.foreground_window() == hwnd:
            return True
    return False


def app_visible_popups(pids: set[int]) -> bool:
    found: list[int] = []
    pid = wintypes.DWORD()

    def cb(hwnd, _):
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 50 and r.left > -10000:
                found.append(hwnd)
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return bool(found)


def tree_pids(proc: subprocess.Popen) -> set[int]:
    try:
        p = psutil.Process(proc.pid)
        return {p.pid} | {c.pid for c in p.children(recursive=True)}
    except psutil.NoSuchProcess:
        return {proc.pid}


def kill_tree(proc: subprocess.Popen) -> None:
    try:
        p = psutil.Process(proc.pid)
        for c in p.children(recursive=True):
            c.kill()
        p.kill()
    except psutil.NoSuchProcess:
        pass


def screenshot(path: str) -> None:
    ps(r"Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
       r"$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
       r"$bm=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
       r"$g=[System.Drawing.Graphics]::FromImage($bm);"
       r"$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
       rf"$bm.Save('{path}')")


def click(x: int, y: int, double: bool = False) -> None:
    u.SetCursorPos(x, y)
    for _ in range(2 if double else 1):
        ctypes.windll.user32.mouse_event(0x2, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x4, 0, 0, 0, 0)
        time.sleep(0.08)


def process_running(exe_name: str) -> bool:
    return any((p.info["name"] or "").lower() == exe_name.lower()
               for p in psutil.process_iter(["name"]))


# ------------------------------------------------------------------ 測試文件
def make_docs(dirpath: Path) -> dict[str, Path]:
    dirpath.mkdir(parents=True, exist_ok=True)
    html = dirpath / "compat_test.html"
    html.write_text("<!doctype html><meta charset=utf-8><title>compat_test</title>"
                    "<body style='margin:0;display:grid;place-items:center;height:100vh;"
                    "font:96px Segoe UI'><span id=w>{word}</span>", encoding="utf-8")
    pages = {}
    for name in ("chrome", "edge"):
        p = dirpath / f"compat_test_{name}.html"
        p.write_text(html.read_text(encoding="utf-8").format(word=WORDS[name]), encoding="utf-8")
        pages[name] = p
    rtf = dirpath / "compat_test_word.rtf"
    rtf.write_text(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Calibri;}}\fs96 " + WORDS["word"] + "}",
                   encoding="ascii")
    pages["word"] = rtf
    pages["pdfx"] = write_pdf(dirpath / "compat_test_pdfx.pdf", WORDS["pdfx"])
    return pages


def write_pdf(path: Path, word: str) -> Path:
    content = f"BT /F1 72 Tf 60 690 Td ({word}) Tj ET".encode()
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>\nstream\n" % len(content) + content + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(bytes(out))
    return path


# ------------------------------------------------------------------ 目標啟動器
class Target:
    def __init__(self, name: str, doc: Path, workdir: Path):
        self.name, self.doc, self.workdir = name, doc, workdir
        self.proc: subprocess.Popen | None = None
        self.preexisting = False

    def start(self) -> None:
        n = self.name
        if n in ("chrome", "edge"):
            prof = tempfile.mkdtemp(prefix=f"compat_{n}_")
            exe = CHROME if n == "chrome" else EDGE
            self.proc = subprocess.Popen([exe, f"--user-data-dir={prof}", "--no-first-run",
                                          "--no-default-browser-check", "--disable-extensions",
                                          "--new-window", self.doc.as_uri()])
        elif n == "word":
            self.preexisting = process_running("WINWORD.EXE")
            self.proc = subprocess.Popen([WORD, str(self.doc)])
        elif n == "pdfx":
            self.preexisting = process_running("PXCEditor.exe")
            self.proc = subprocess.Popen([PDFX, str(self.doc)])
        elif n == "tk":
            self.doc.with_suffix(".py").write_text(TK_SCRIPT, encoding="utf-8")
            self.proc = subprocess.Popen([PY, str(self.doc.with_suffix(".py")), WORDS["tk"]])

    def wait_window(self, timeout: float = 40) -> int | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            wins = find_windows(MARK)
            if wins:
                time.sleep(3 if self.name in ("word", "pdfx") else 6 if self.name in ("chrome", "edge") else 1.5)
                return wins[0]
            time.sleep(0.5)
        return None

    def close(self) -> None:
        for hwnd in find_windows(MARK):             # 只關自己的測試視窗
            u.PostMessageW(hwnd, 0x0010, 0, 0)       # WM_CLOSE
        time.sleep(1.5)
        if self.name in ("chrome", "edge", "tk") and self.proc:
            kill_tree(self.proc)
        elif self.name in ("word", "pdfx") and not self.preexisting and self.proc:
            exe = "WINWORD.EXE" if self.name == "word" else "PXCEditor.exe"
            if not find_windows(MARK):
                for p in psutil.process_iter(["name"]):
                    if (p.info["name"] or "").lower() == exe.lower():
                        try:
                            p.terminate()
                        except psutil.Error:
                            pass


TK_SCRIPT = """import sys, tkinter as tk
word = sys.argv[1]
root = tk.Tk(); root.title("compat_test_tk"); root.geometry("520x200+300+200")
t = tk.Text(root, font=("Segoe UI", 18)); t.pack(fill="both", expand=True)
t.insert("1.0", word)
t.bind("<Control-a>", lambda e: (t.tag_add("sel", "1.0", "end-1c"), "break")[1])
root.update(); root.focus_force(); t.focus_force()
root.after(600000, root.destroy); root.mainloop()
"""


# ------------------------------------------------------------------ 主流程
def run_one(name: str, docs: dict[str, Path], workdir: Path, shots: Path | None,
            repeat: int, app_pids: set[int], on_iter=None, expect_kind: str | None = None) -> dict:
    res = {"target": name, "word": WORDS[name]}
    tgt = Target(name, docs.get(name, workdir / "compat_test_tk.txt"), workdir)
    tgt.start()
    try:
        hwnd = tgt.wait_window()
        if not hwnd:
            res["error"] = "window not found"
            return res
        if not focus(hwnd):
            res["error"] = "cannot bring to foreground"
            return res
        ensure_focus(hwnd)
        if name == "pdfx":
            # 預設是手形工具：最大化視窗後點「選取工具」，再雙擊單字（座標依 1366x768 最大化版面校準）
            u.ShowWindow(hwnd, 3)
            time.sleep(1.5)
            ensure_focus(hwnd)
            click(78, 95)
            time.sleep(0.4)
            click(540, 385, double=True)
        else:
            w.send_keys([(w.VK_CONTROL, False), (VK_A, False), (VK_A, True), (w.VK_CONTROL, True)])
        time.sleep(0.5)                                 # 全選
        bt = w.vk_from_char("`")
        oks, latencies, iters = 0, [], []
        for i in range(repeat):
            refocused = ensure_focus(hwnd)
            ps("Set-Clipboard -Value 'KEEP-ME'")
            LOG.write_text("", encoding="utf-8") if i == 0 else None
            before = LOG.read_text(encoding="utf-8").count("status=")
            fg = w.foreground_window()
            w.send_keys([(w.VK_MENU, False), (bt, False), (bt, True), (w.VK_MENU, True)])
            deadline = time.time() + 3
            while time.time() < deadline:
                text = LOG.read_text(encoding="utf-8")
                if text.count("status=") > before:
                    break
                time.sleep(0.05)
            time.sleep(0.25)
            text = LOG.read_text(encoding="utf-8")
            lines = [ln for ln in text.splitlines() if "status=" in ln]
            last = lines[-1] if lines else ""
            cap = [ln for ln in text.splitlines() if "captured=" in ln]
            res["status"] = last.split("status=")[1].split()[0] if last else "no log"
            res["kind"] = last.split("kind=")[1].split()[0] if "kind=" in last else None
            res["captured"] = cap[-1].split("captured=")[1] if cap else None
            if "total=" in last:
                latencies.append(float(last.split("total=")[1].split("ms")[0]))
            res["clipboard_ok"] = ps("Get-Clipboard") == "KEEP-ME"
            res["focus_ok"] = w.foreground_window() == fg
            res["popup"] = app_visible_popups(app_pids)
            if i == 0 and shots:
                screenshot(str(shots / f"{name}.png"))
            if expect_kind:
                good = (res["kind"] == expect_kind and res["clipboard_ok"] and res["focus_ok"]
                        and res["popup"])
            else:
                good = (res["status"] == "ok" and res["clipboard_ok"] and res["focus_ok"]
                        and res["popup"] and WORDS[name] in (res["captured"] or ""))
            oks += good
            iters.append(f"{res['status']}/{latencies[-1] if latencies else '-'}ms/{res['captured']}"
                         + ("/REFOCUSED" if refocused else ""))
            w.send_keys([(w.VK_ESCAPE, False), (w.VK_ESCAPE, True)])
            time.sleep(0.3)
            if on_iter:
                on_iter(i)
        res["pass"] = f"{oks}/{repeat}"
        res["iters"] = iters
        if latencies:
            latencies.sort()
            res["latency_ms"] = f"avg={sum(latencies) / len(latencies):.0f} max={latencies[-1]:.0f}"
        return res
    finally:
        tgt.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", default=["chrome", "edge", "word", "pdfx"])
    ap.add_argument("--shots", type=Path)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--word", help="覆寫 tk 目標的文字（測試查無此字、過長等提示）")
    ap.add_argument("--expect-kind", help="預期的結果類別：entry/not_found/too_long/no_selection/busy")
    args = ap.parse_args()
    if args.word:
        WORDS["tk"] = args.word

    workdir = Path(tempfile.mkdtemp(prefix="compat_docs_"))
    docs = make_docs(workdir)
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)

    original = ps("Get-Clipboard -Raw")
    env = {**os.environ, "PYTHONUTF8": "1", "HOTKEYDICT_LOG_WORDS": "1"}
    app = start_app(env)
    time.sleep(3)
    results = []
    try:
        for name in args.targets:
            pids = tree_pids(app)
            results.append(run_one(name, docs, workdir, args.shots, args.repeat, pids,
                                   expect_kind=args.expect_kind))
    finally:
        kill_tree(app)
        if original:
            subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
                           input=original, text=True, encoding="utf-8")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
