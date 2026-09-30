"""把 dist/ 的 exe、字典與 release/ 的說明檔打成單一 zip：dist/HotkeyDict-win64.zip。

用法：python tools/make_release.py
需要先執行 tools/build_exe.py。zip 內容（解壓縮後為單一資料夾 HotkeyDict/）：
    HotkeyDict/HotkeyDict.exe
    HotkeyDict/data/dict.db
    HotkeyDict/使用說明.txt
    HotkeyDict/NOTICES.txt
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
RELEASE = ROOT / "release"
OUT = DIST / "HotkeyDict-win64.zip"
FOLDER = "HotkeyDict"

FILES = [
    (DIST / "HotkeyDict.exe", "HotkeyDict.exe"),
    (DIST / "data" / "dict.db", "data/dict.db"),
    (RELEASE / "使用說明.txt", "使用說明.txt"),
    (RELEASE / "NOTICES.txt", "NOTICES.txt"),
]
# 若 release/ 下另外放了授權全文（例如 LICENSE-ECDICT.txt），一併收進去
FILES += [(p, p.name) for p in sorted(RELEASE.glob("LICENSE*.txt"))]


def main() -> None:
    missing = [str(src) for src, _ in FILES if not src.exists()]
    if missing:
        sys.exit("缺少檔案（請先執行 tools/build_exe.py）：\n  " + "\n  ".join(missing))
    OUT.unlink(missing_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for src, arcname in FILES:
            zf.write(src, f"{FOLDER}/{arcname}")
    print(f"{OUT}  ({OUT.stat().st_size / 1e6:.1f} MB)")
    with zipfile.ZipFile(OUT) as zf:
        for info in zf.infolist():
            print(f"  {info.filename:34s} {info.file_size / 1e6:7.1f} MB -> {info.compress_size / 1e6:6.1f} MB")


if __name__ == "__main__":
    main()
