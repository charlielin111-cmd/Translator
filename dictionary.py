"""SQLite 字典查詢（唯讀）。查詢順序：字面 → 小寫 → 詞形還原後的原形。"""

from __future__ import annotations

import re
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
    frq: int = 0                    # ECDICT 詞頻排名（0 = 不在詞頻表）


_SELECT = ("SELECT word, kk, kk_alt, kk_src, translation, frq FROM words "
           "WHERE word_lc = ? ORDER BY (frq = 0), frq LIMIT 1")


# 詞條內容只是「某字的過去式／複數…」的注記（沒有自己的字義），例如 went =「go的過去式」
_INFLECTION_NOTE = re.compile(r"的(過去式|過去分詞|複數|比較級|最高級|現在分詞|第三人稱單數)")


def _prefers_lemma(entry: Entry) -> bool:
    """字面詞條沒有自己的字義時，改顯示原形詞條：
    - 每一行都只是變化形注記（went →「go的過去式」）
    - 不在詞頻表的縮寫雜訊（cats → 縮寫「高階電視研究中心」，實為 cat 的複數）
    只要有任何一行是真實字義（saw 的「n. 鋸子」、running 的「n. 賽跑」）就保留字面詞條。
    """
    lines = [ln for ln in entry.translation.splitlines() if ln.strip()]
    if not lines:
        return False
    if all(_INFLECTION_NOTE.search(ln) for ln in lines):
        return True
    return entry.frq == 0 and lines[0].lstrip().startswith("abbr.")


# 規則式還原的猜測只接受常用字，避免 "thi"、"ca" 之類的雜訊詞條
_SELECT_COMMON = _SELECT.replace("WHERE word_lc = ?", "WHERE word_lc = ? AND frq > 0")


class Dictionary:
    def __init__(self, db_path: Path):
        if not Path(db_path).exists():
            raise FileNotFoundError(f"找不到字典檔：{db_path}（請先執行 tools/build_db.py）")
        self._conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)

    def close(self) -> None:
        self._conn.close()

    def _get(self, word_lc: str, common_only: bool = False) -> Entry | None:
        sql = _SELECT_COMMON if common_only else _SELECT
        row = self._conn.execute(sql, (word_lc,)).fetchone()
        return Entry(*row[:5], frq=row[5]) if row else None

    def lookup(self, raw: str) -> Entry | None:
        for cand in textclean.candidates(raw):
            lc = cand.lower()
            direct = self._get(lc)
            base = lemma_mod.lemma_of(self._conn, lc)
            base_entry = self._get(base) if base else None
            if direct and not (base_entry and _prefers_lemma(direct)):
                return direct
            if base_entry:
                base_entry.lemma_from = cand
                return base_entry
        for cand in textclean.candidates(raw):      # forms 表也查不到：規則式備援
            for base in lemma_mod.rule_candidates(cand):
                entry = self._get(base, common_only=True)
                if entry:
                    entry.lemma_from = cand
                    return entry
        return None
