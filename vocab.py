"""生字本：以 SQLite 存放使用者收藏的單字，可匯出 CSV（UTF-8 含 BOM，Excel 可直接開啟）。"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from dictionary import Entry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vocab (
    word TEXT PRIMARY KEY,
    kk TEXT,
    translation TEXT NOT NULL,
    added_at TEXT NOT NULL
)
"""
CSV_HEADER = ["單字", "KK音標", "中文釋義", "加入時間"]


class VocabBook:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def contains(self, word: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM vocab WHERE word = ?", (word.lower(),)).fetchone()
        return row is not None

    def add(self, entry: Entry) -> None:
        kk = entry.kk and (("≈" if entry.kk_src == "approx" else "") + f"[{entry.kk}]")
        self._conn.execute(
            "INSERT OR IGNORE INTO vocab (word, kk, translation, added_at) VALUES (?,?,?,?)",
            (entry.word.lower(), kk, entry.translation, datetime.now().isoformat(timespec="seconds")))
        self._conn.commit()

    def remove(self, word: str) -> None:
        self._conn.execute("DELETE FROM vocab WHERE word = ?", (word.lower(),))
        self._conn.commit()

    def toggle(self, entry: Entry) -> bool:
        """加入或移除；回傳操作後是否已收藏。"""
        if self.contains(entry.word):
            self.remove(entry.word)
            return False
        self.add(entry)
        return True

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM vocab").fetchone()[0]

    def export_csv(self, path: Path) -> int:
        """依加入時間排序匯出；釋義中的換行改成「 / 」，回傳匯出筆數。"""
        rows = self._conn.execute(
            "SELECT word, kk, translation, added_at FROM vocab ORDER BY added_at, word").fetchall()
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
            for word, kk, translation, added_at in rows:
                writer.writerow([word, kk or "", " / ".join(translation.splitlines()), added_at])
        return len(rows)
