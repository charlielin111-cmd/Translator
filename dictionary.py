"""SQLite 字典查詢（唯讀）。查詢順序：字面 → 小寫 → 詞形還原後的原形。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import lemma as lemma_mod
import textclean


@dataclass
class Entry:
    word: str
    kk: str | None
    kk_alt: str | None
    kk_src: str                 # cmu | approx | none
    translation: str
    lemma_from: str | None = None   # 使用者選取的原字（經還原才查到時）


_SELECT = ("SELECT word, kk, kk_alt, kk_src, translation FROM words "
           "WHERE word_lc = ? ORDER BY (frq = 0), frq LIMIT 1")


class Dictionary:
    def __init__(self, db_path: Path):
        if not Path(db_path).exists():
            raise FileNotFoundError(f"找不到字典檔：{db_path}（請先執行 tools/build_db.py）")
        self._conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)

    def close(self) -> None:
        self._conn.close()

    def _get(self, word_lc: str) -> Entry | None:
        row = self._conn.execute(_SELECT, (word_lc,)).fetchone()
        return Entry(*row) if row else None

    def lookup(self, raw: str) -> Entry | None:
        for cand in textclean.candidates(raw):
            lc = cand.lower()
            entry = self._get(lc)
            if entry:
                return entry
            base = lemma_mod.lemma_of(self._conn, lc)
            if base:
                entry = self._get(base)
                if entry:
                    entry.lemma_from = cand
                    return entry
        return None
