"""詞形還原：查 SQLite 的 forms 表（由 ECDICT exchange 欄位建立，含不規則變化）。"""

from __future__ import annotations

import sqlite3


def lemma_of(conn: sqlite3.Connection, word: str) -> str | None:
    """回傳原形；沒有對照或原形就是自己時回傳 None。"""
    row = conn.execute("SELECT lemma FROM forms WHERE form_lc = ?", (word.lower(),)).fetchone()
    if row and row[0] != word.lower():
        return row[0]
    return None
