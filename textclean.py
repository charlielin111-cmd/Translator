"""清理選取文字，產生查詢候選字串。"""

from __future__ import annotations

import re

MAX_CHARS = 80
MAX_WORDS = 4

_EDGE = " \t\r\n\"'`.,;:!?()[]{}<>“”‘’«»…—–-_*/\\|#@$%^&+=~"
_SOFT_HYPHEN = re.compile("[­​‌‍﻿]")
_LINEBREAK_HYPHEN = re.compile(r"(?<=[A-Za-z])[-‐‑]\s*[\r\n]+\s*(?=[A-Za-z])")


def is_too_long(raw: str) -> bool:
    text = raw.strip()
    return len(text) > MAX_CHARS or len(text.split()) > MAX_WORDS


def normalize(raw: str) -> str:
    text = _SOFT_HYPHEN.sub("", raw).replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip(_EDGE)


def candidates(raw: str) -> list[str]:
    """依優先順序回傳要查詢的字串（已去重）。

    - 版面斷行連字號（infor-⏎mation）：先試接合版本，再試保留連字號的版本
    - 所有格 's / s'：附帶去除後的版本
    """
    variants = [raw]
    if _LINEBREAK_HYPHEN.search(raw):
        variants.insert(0, _LINEBREAK_HYPHEN.sub("", raw))
        variants[1] = _LINEBREAK_HYPHEN.sub("-", raw)

    out: list[str] = []
    for v in variants:
        text = normalize(v)
        if not text or not any(c.isalpha() for c in text):
            continue
        out.append(text)
        if re.search(r"'s$", text, re.I):
            out.append(text[:-2])
        elif text.endswith("s'"):
            out.append(text[:-1])
    seen: set[str] = set()
    return [c for c in out if c and not (c.lower() in seen or seen.add(c.lower()))]
