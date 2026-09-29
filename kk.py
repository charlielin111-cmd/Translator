"""KK 音標轉換：ARPAbet（CMUdict）→ KK，以及 IPA → KK 近似轉換（備援）。

純函式模組，不依賴任何外部套件，建庫工具與執行階段都可使用。
"""

from __future__ import annotations

PRIMARY = "ˋ"      # ˋ 主重音
SECONDARY = "ˏ"    # ˏ 次重音
SYLLABIC = "̩"     # 成音節子音記號（l̩ n̩ m̩ 的下方短直線）

_VOWELS = {
    "AA": "ɑ", "AE": "æ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ",
    "EY": "e", "IH": "ɪ", "IY": "i", "OW": "o", "OY": "ɔɪ", "UH": "ʊ",
    "UW": "u",
}

_CONSONANTS = {
    "CH": "tʃ", "JH": "dʒ", "DH": "ð", "TH": "θ", "HH": "h", "NG": "ŋ",
    "SH": "ʃ", "ZH": "ʒ", "Y": "j",
    "B": "b", "D": "d", "F": "f", "G": "g", "K": "k", "L": "l", "M": "m",
    "N": "n", "P": "p", "R": "r", "S": "s", "T": "t", "V": "v", "W": "w",
    "Z": "z",
}

# 合法的音節起首子音串（最大首音原則）。單一子音除了 NG 之外都合法。
_ONSET_PAIRS = {
    ("P", "L"), ("P", "R"), ("B", "L"), ("B", "R"), ("T", "R"), ("D", "R"),
    ("K", "L"), ("K", "R"), ("G", "L"), ("G", "R"), ("F", "L"), ("F", "R"),
    ("TH", "R"), ("SH", "R"),
    ("T", "W"), ("D", "W"), ("K", "W"), ("G", "W"), ("S", "W"), ("TH", "W"),
    ("S", "P"), ("S", "T"), ("S", "K"), ("S", "M"), ("S", "N"), ("S", "F"),
    ("S", "L"),
    ("P", "Y"), ("B", "Y"), ("T", "Y"), ("D", "Y"), ("K", "Y"), ("G", "Y"),
    ("F", "Y"), ("V", "Y"), ("TH", "Y"), ("S", "Y"), ("Z", "Y"), ("M", "Y"),
    ("N", "Y"), ("L", "Y"), ("HH", "Y"),
}
_ONSET_TRIPLES = {
    ("S", "P", "L"), ("S", "P", "R"), ("S", "T", "R"), ("S", "K", "R"),
    ("S", "K", "L"), ("S", "K", "W"), ("S", "P", "Y"), ("S", "T", "Y"),
    ("S", "K", "Y"),
}

# 字尾「子音 + AH0 + L/N/M」轉成成音節子音的條件（台灣 KK 慣例）
_SYLLABIC_AFTER = {
    "L": None,                          # 任何子音之後：apple、little
    "N": {"T", "D", "S", "Z"},          # button、sudden、lesson、reason
    "M": {"DH"},                        # rhythm
}


def _split_stress(phone: str) -> tuple[str, int | None]:
    """'AH0' -> ('AH', 0)；子音回傳 (phone, None)。"""
    if phone and phone[-1].isdigit():
        return phone[:-1], int(phone[-1])
    return phone, None


def _is_vowel(phone: str) -> bool:
    return bool(phone) and phone[-1].isdigit()


def _legal_onset(cluster: list[str]) -> bool:
    if len(cluster) == 1:
        return cluster[0] != "NG"
    if len(cluster) == 2:
        return tuple(cluster) in _ONSET_PAIRS
    if len(cluster) == 3:
        return tuple(cluster) in _ONSET_TRIPLES
    return False


def _vowel_kk(base: str, stress: int) -> str:
    if base == "AH":
        return "ə" if stress == 0 else "ʌ"
    if base == "ER":
        return "ɚ" if stress == 0 else "ɝ"
    return _VOWELS[base]


def arpabet_to_kk(phones: list[str]) -> str:
    """將一組 ARPAbet 音素（如 ['AH0','B','AW1','T']）轉成 KK 字串（不含方括號）。"""
    phones = [p.upper() for p in phones]

    # 1. 字尾成音節子音：C + AH0 + L/N/M -> C + 成音節 L/N/M
    syllabic_final: str | None = None
    if len(phones) >= 3 and phones[-2] == "AH0" and phones[-1] in _SYLLABIC_AFTER:
        before = phones[-3]
        allowed = _SYLLABIC_AFTER[phones[-1]]
        if not _is_vowel(before) and (allowed is None or before in allowed):
            syllabic_final = _CONSONANTS[phones[-1]] + SYLLABIC
            phones = phones[:-2]

    # 2. 找出母音位置，依最大首音原則決定每個音節的起點
    vowel_idx = [i for i, p in enumerate(phones) if _is_vowel(p)]
    starts: list[int] = []
    for n, vi in enumerate(vowel_idx):
        if n == 0:
            starts.append(0)
            continue
        prev_v = vowel_idx[n - 1]
        cons = phones[prev_v + 1:vi]
        take = 0
        for k in range(min(3, len(cons)), 0, -1):
            if _legal_onset(cons[len(cons) - k:]):
                take = k
                break
        starts.append(vi - take)

    # 3. 逐音節組字，並在音節開頭補上重音記號
    out: list[str] = []
    multi = len(vowel_idx) > 1 or (syllabic_final is not None and len(vowel_idx) >= 1)
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(phones)
        stress = _split_stress(phones[vowel_idx[n]])[1]
        if multi:
            if stress == 1:
                out.append(PRIMARY)
            elif stress == 2:
                out.append(SECONDARY)
        last_syllable = n == len(starts) - 1
        for i in range(start, end):
            base, st = _split_stress(phones[i])
            if st is None:
                out.append(_CONSONANTS[base])
            elif base == "IY" and st == 0 and last_syllable and i == len(phones) - 1:
                out.append("ɪ")     # 字尾非重讀 -y：happy [ˋhæpɪ]
            else:
                out.append(_vowel_kk(base, st))
    if syllabic_final:
        out.append(syllabic_final)
    return "".join(out)


# ---------------------------------------------------------------- IPA 近似轉換

_IPA_REPLACEMENTS = [
    ("əʊ", "o"), ("oʊ", "o"), ("eɪ", "e"), ("ɪə", "ɪr"), ("eə", "ɛr"),
    ("ʊə", "ʊr"), ("ɜː", "ɝ"), ("ɜ:", "ɝ"), ("ɑː", "ɑ"), ("ɑ:", "ɑ"),
    ("ɔː", "ɔ"), ("ɔ:", "ɔ"), ("iː", "i"), ("i:", "i"), ("uː", "u"),
    ("u:", "u"), ("ɒ", "ɑ"), ("ɜ", "ɝ"), ("ˈ", PRIMARY), ("'", PRIMARY),
    ("ˌ", SECONDARY), ("ː", ""), (":", ""), ("ɡ", "g"), ("e", "ɛ"),
]


def ipa_to_kk_approx(ipa: str) -> str:
    """把 ECDICT 的（多為英式）IPA 近似轉成 KK。結果只是近似，呼叫端應標示「≈」。"""
    s = ipa.strip().strip("[]/")
    if not s:
        return ""
    # 先保護已轉換的 e（來自 eɪ），避免被最後的 e→ɛ 再次轉換
    placeholder = "\x00"
    s = s.replace("eɪ", placeholder)
    for src, dst in _IPA_REPLACEMENTS:
        if src == "e":
            continue
        s = s.replace(src, dst)
    s = s.replace("e", "ɛ").replace(placeholder, "e")
    return s
