from pathlib import Path

import pytest

from kk import PRIMARY, arpabet_to_kk, ipa_to_kk_approx

ROOT = Path(__file__).resolve().parent.parent
CMUDICT = ROOT / "data" / "raw" / "cmudict.dict"
GOLDEN = Path(__file__).parent / "data" / "kk_golden.tsv"


@pytest.mark.parametrize("arpa, expected", [
    ("AH0 B AW1 T", "əˋbaʊt"),
    ("AE1 P AH0 L", "ˋæpl̩"),                # 成音節 l
    ("B AH1 T AH0 N", "ˋbʌtn̩"),             # t 之後的 n 成音節
    ("OW1 P AH0 N", "ˋopən"),                # p 之後的 n 不成音節
    ("HH AE1 P IY0", "ˋhæpɪ"),               # 字尾 -y
    ("K R IY0 EY1 T", "kriˋet"),             # 詞中 IY0 維持 i
    ("K AE1 T", "kæt"),                      # 單音節不標重音
    ("K Y UW1 T", "kjut"),
    ("AH2 N D ER0 S T AE1 N D", "ˏʌndɚˋstænd"),
    ("HH M", "hm"),                          # 無母音
])
def test_arpabet_to_kk(arpa, expected):
    assert arpabet_to_kk(arpa.split()) == expected


def test_single_syllable_has_no_stress_mark():
    assert PRIMARY not in arpabet_to_kk("K AA1 R".split())


@pytest.mark.parametrize("ipa, expected", [
    ("ˈsɪti", "ˋsɪti"),
    ("bɪˈli:v", "bɪˋliv"),
    ("ˈəʊpən", "ˋopən"),
    ("kɑ:", "kɑ"),
])
def test_ipa_to_kk_approx(ipa, expected):
    assert ipa_to_kk_approx(ipa) == expected


def _golden():
    rows = []
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            word, kk = line.split("\t")
            rows.append((word, kk))
    return rows


@pytest.mark.skipif(not CMUDICT.exists(), reason="data/raw/cmudict.dict 不存在")
def test_golden_match_rate():
    from tools.build_db import cmu_to_kk, load_cmudict

    cmu = load_cmudict(CMUDICT)
    rows = _golden()
    bad = []
    for word, expected in rows:
        got = cmu_to_kk(cmu[word])
        if expected not in got:      # 第一或第二發音符合即算對
            bad.append((word, expected, got))
    rate = 1 - len(bad) / len(rows)
    print(f"golden match {rate:.1%}  mismatches: {bad}")
    assert rate >= 0.95, bad
