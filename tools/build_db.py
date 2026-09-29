"""將 ECDICT + CMUdict 轉成 data/dict.db（SQLite）。

用法：
    python tools/build_db.py [--ecdict data/raw/ecdict.csv] [--cmudict data/raw/cmudict.dict]
                             [--out data/dict.db] [--limit N]

需要開發用套件 opencc-python-reimplemented（僅建庫時使用，執行階段不需要）。
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import kk  # noqa: E402

csv.field_size_limit(10_000_000)

SCHEMA = """
CREATE TABLE words (
    word TEXT NOT NULL,
    word_lc TEXT NOT NULL,
    kk TEXT,
    kk_alt TEXT,
    kk_src TEXT NOT NULL,          -- cmu | approx | none
    translation TEXT NOT NULL,
    pos TEXT,
    frq INTEGER
);
CREATE TABLE forms (
    form_lc TEXT PRIMARY KEY,
    lemma TEXT NOT NULL
);
"""

_PRON_VARIANT = re.compile(r"\(\d+\)$")
_FORM_KEYS = {"p", "d", "i", "3", "r", "t", "s"}   # 過去式/過去分詞/現在分詞/三單/比較/最高/複數


def load_cmudict(path: Path) -> dict[str, list[list[str]]]:
    prons: dict[str, list[list[str]]] = {}
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";;;"):
                continue
            parts = line.split("#")[0].split()
            if len(parts) < 2:
                continue
            word = _PRON_VARIANT.sub("", parts[0]).lower()
            prons.setdefault(word, []).append(parts[1:])
    return prons


def cmu_to_kk(prons: list[list[str]]) -> tuple[str, str | None]:
    seen: list[str] = []
    for phones in prons:
        s = kk.arpabet_to_kk(phones)
        if s and s not in seen:
            seen.append(s)
    return seen[0], (seen[1] if len(seen) > 1 else None)


def parse_exchange(exchange: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in exchange.split("/"):
        if ":" in item:
            key, _, val = item.partition(":")
            out[key] = val
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecdict", default=str(ROOT / "data/raw/ecdict.csv"))
    ap.add_argument("--cmudict", default=str(ROOT / "data/raw/cmudict.dict"))
    ap.add_argument("--out", default=str(ROOT / "data/dict.db"))
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 列（除錯用）")
    args = ap.parse_args()

    from opencc import OpenCC
    s2t = OpenCC("s2twp")

    t0 = time.perf_counter()
    cmu = load_cmudict(Path(args.cmudict))
    print(f"CMUdict: {len(cmu):,} words")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.executescript(SCHEMA)

    stats = {"rows": 0, "kept": 0, "cmu": 0, "approx": 0, "none": 0}
    forms: dict[str, str] = {}
    word_rows = []

    with open(args.ecdict, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            stats["rows"] += 1
            if args.limit and stats["rows"] > args.limit:
                break
            word = (row.get("word") or "").strip()
            translation = (row.get("translation") or "").replace("\\n", "\n").strip()
            if not word or not translation or len(word.split()) > 4:
                continue
            word_lc = word.lower()
            try:
                frq = int(row.get("frq") or 0)
            except ValueError:
                frq = 0

            if word_lc in cmu:
                k1, k2 = cmu_to_kk(cmu[word_lc])
                src = "cmu"
            elif (row.get("phonetic") or "").strip():
                k1, k2, src = kk.ipa_to_kk_approx(row["phonetic"]), None, "approx"
            else:
                k1, k2, src = None, None, "none"
            if src == "none" and frq == 0:      # 無音標又不在詞頻表：多為片語/專有名詞雜訊
                continue
            stats[src] += 1

            word_rows.append((
                word, word_lc, k1, k2, src,
                s2t.convert(translation), row.get("pos") or None, frq,
            ))
            stats["kept"] += 1

            ex = parse_exchange(row.get("exchange") or "")
            if "0" in ex:                       # 本字是別的字的變化形
                forms.setdefault(word_lc, ex["0"].lower())
            for key in _FORM_KEYS:
                form = ex.get(key)
                if form and form.lower() != word_lc:
                    forms.setdefault(form.lower(), word_lc)

            if len(word_rows) >= 20000:
                db.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?)", word_rows)
                word_rows.clear()

    db.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?)", word_rows)
    db.executemany("INSERT OR IGNORE INTO forms VALUES (?,?)", forms.items())
    db.execute("CREATE INDEX idx_words_lc ON words(word_lc)")
    db.commit()
    db.execute("VACUUM")
    db.close()

    print(f"ECDICT rows: {stats['rows']:,}  kept: {stats['kept']:,}")
    print(f"KK source -> cmu: {stats['cmu']:,}  approx: {stats['approx']:,}  none: {stats['none']:,}")
    print(f"forms: {len(forms):,}")
    print(f"db size: {out.stat().st_size / 1e6:.1f} MB  time: {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
