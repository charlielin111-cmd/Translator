"""以 PyInstaller 打包成單一執行檔：dist/HotkeyDict.exe，並把 data/dict.db 複製到 dist/data/。

用法：python tools/build_exe.py
字典檔不嵌入 exe（約 30MB，嵌入會讓每次啟動都得先解壓縮），放在 exe 同目錄的 data/ 資料夾。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DB = ROOT / "data" / "dict.db"

# 用不到的 Qt 模組明確排除，縮小體積
EXCLUDES = ["PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf",
            "PySide6.QtSvg", "PySide6.QtOpenGL", "PySide6.QtTest", "tkinter"]


def main() -> None:
    if not DB.exists():
        sys.exit(f"找不到 {DB}，請先執行 tools/build_db.py")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
           "--name", "HotkeyDict", "--distpath", str(DIST), "--workpath", str(ROOT / "build"),
           "--specpath", str(ROOT / "build")]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    cmd.append(str(ROOT / "main.py"))
    subprocess.run(cmd, check=True, cwd=ROOT)

    (DIST / "data").mkdir(exist_ok=True)
    shutil.copy2(DB, DIST / "data" / "dict.db")
    exe = DIST / "HotkeyDict.exe"
    print(f"\nexe: {exe} ({exe.stat().st_size / 1e6:.1f} MB)")
    print(f"db : {DIST / 'data' / 'dict.db'} ({DB.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
