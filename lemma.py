"""詞形還原。

1. `lemma_of`：查 SQLite 的 forms 表（由 ECDICT exchange 欄位建立，含 ran→run、mice→mouse 等不規則變化）
2. `rule_candidates`：forms 表查不到時的規則式備援（-ies、-ed、-ing、雙寫子音…），零外部依賴。
   不使用 lemminflect：它依賴 numpy，打包後會多出數十 MB，而 forms 表已涵蓋不規則變化。
"""

from __future__ import annotations

import sqlite3

_VOWELS = "aeiou"


def lemma_of(conn: sqlite3.Connection, word: str) -> str | None:
    """回傳原形；沒有對照或原形就是自己時回傳 None。"""
    row = conn.execute("SELECT lemma FROM forms WHERE form_lc = ?", (word.lower(),)).fetchone()
    if row and row[0] != word.lower():
        return row[0]
    return None


def _undouble(stem: str) -> str | None:
    """stopp → stop、bigg → big；只處理字尾為雙寫子音的情況。"""
    if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in _VOWELS and stem[-1] not in "lsz":
        return stem[:-1]
    return None


def rule_candidates(word: str) -> list[str]:
    """依可能性由高到低回傳可能的原形（不保證存在於字典，需由呼叫端驗證）。"""
    w = word.lower()
    out: list[str] = []

    def add(c: str | None) -> None:
        if c and len(c) >= 2 and c != w and c not in out:
            out.append(c)

    if w.endswith("ies") and len(w) > 4:
        add(w[:-3] + "y")                       # studies → study
    if w.endswith("ves") and len(w) > 4:
        add(w[:-3] + "f")                       # wolves → wolf
        add(w[:-3] + "fe")                      # knives → knife
    if w.endswith("es") and len(w) > 3:
        add(w[:-2])                             # boxes → box
        add(w[:-1])                             # makes → make
    if w.endswith("s") and not w.endswith(("ss", "us", "is")) and len(w) > 3:
        add(w[:-1])                             # cats → cat

    if w.endswith("ied") and len(w) > 4:
        add(w[:-3] + "y")                       # carried → carry
    if w.endswith("ed") and len(w) > 4:
        stem = w[:-2]
        add(stem)                               # walked → walk
        add(_undouble(stem))                    # stopped → stop
        add(w[:-1])                             # liked → like

    if w.endswith("ying") and len(w) >= 5:
        add(w[:-4] + "ie")                      # dying → die
    if w.endswith("ing") and len(w) > 5:
        stem = w[:-3]
        add(stem)                               # walking → walk
        add(_undouble(stem))                    # running → run
        add(stem + "e")                         # making → make

    if w.endswith("ier") or w.endswith("iest"):
        cut = 3 if w.endswith("ier") else 4
        add(w[:-cut] + "y")                     # happier → happy
    for suffix in ("er", "est"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            stem = w[:-len(suffix)]
            add(_undouble(stem))                # bigger → big
            add(stem + "e")                     # larger → large
            add(stem)
    return out
