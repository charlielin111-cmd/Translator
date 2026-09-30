import sqlite3

import pytest

import textclean
from dictionary import Dictionary
from popup import compute_popup_pos


# ------------------------------------------------------------------ textclean
@pytest.mark.parametrize("raw, first", [
    ("  Hello,  ", "Hello"),
    ("“quoted”", "quoted"),
    ("world.", "world"),
    ("don’t", "don't"),
    ("(apple)", "apple"),
    ("co­operate", "cooperate"),
])
def test_candidates_first(raw, first):
    assert textclean.candidates(raw)[0] == first


def test_possessive_variants():
    assert textclean.candidates("dog's") == ["dog's", "dog"]
    assert textclean.candidates("dogs'") == ["dogs'", "dogs"] or textclean.candidates("dogs'")[-1] == "dogs"


def test_linebreak_hyphen_tries_joined_then_hyphenated():
    assert textclean.candidates("infor-\nmation") == ["information", "infor-mation"]


def test_no_letters_yields_nothing():
    assert textclean.candidates("  123 !!") == []


def test_too_long():
    assert textclean.is_too_long("one two three four five")
    assert textclean.is_too_long("x" * 81)
    assert not textclean.is_too_long("running")


# ------------------------------------------------------------------ dictionary
@pytest.fixture()
def dictionary(tmp_path):
    path = tmp_path / "dict.db"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE words (word TEXT, word_lc TEXT, kk TEXT, kk_alt TEXT, kk_src TEXT,
                            translation TEXT, pos TEXT, frq INTEGER);
        CREATE TABLE forms (form_lc TEXT PRIMARY KEY, lemma TEXT);
        CREATE INDEX idx ON words(word_lc);
    """)
    rows = [
        ("run", "run", "rʌn", None, "cmu", "v. 跑", None, 300),
        ("study", "study", "ˋstʌdɪ", None, "cmu", "n. 學習", None, 500),
        ("Apple", "apple", "ˋæpl̩", None, "cmu", "n. 蘋果公司", None, 0),
        ("apple", "apple", "ˋæpl̩", None, "cmu", "n. 蘋果", None, 900),
        ("dog", "dog", "dɔg", None, "cmu", "n. 狗", None, 700),
        ("walk", "walk", "wɔk", None, "cmu", "v. 走", None, 400),
        ("stop", "stop", "stɑp", None, "cmu", "v. 停止", None, 350),
        ("die", "die", "daɪ", None, "cmu", "v. 死", None, 450),
        ("went", "went", None, None, "none", "go的過去式", None, 0),
        ("go", "go", "go", None, "cmu", "v. 去", None, 900),
        ("saw", "saw", "sɔ", None, "cmu", "n. 鋸子\nv. 看見（see的過去式）", None, 300),
        ("see", "see", "si", None, "cmu", "v. 看見", None, 950),
        ("cats", "cats", None, None, "none", "abbr. 高階電視研究中心", None, 0),
        ("cat", "cat", "kæt", None, "cmu", "n. 貓", None, 800),
        ("jogging", "jogging", "ˋdʒɑgɪŋ", None, "cmu", "n. 慢跑", None, 100),
        ("jog", "jog", "dʒɑg", None, "cmu", "v. 慢跑", None, 600),
        ("thi", "thi", None, None, "none", "雜訊詞條", None, 0),     # 不常用：規則式還原不可採用
    ]
    db.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?)", rows)
    db.executemany("INSERT INTO forms VALUES (?,?)",
                   [("running", "run"), ("studies", "study"), ("ran", "run"), ("run", "run"),
                    ("went", "go"), ("saw", "see"), ("cats", "cat"), ("jogging", "jog")])
    db.commit()
    db.close()
    d = Dictionary(path)
    yield d
    d.close()


def test_direct_hit(dictionary):
    assert dictionary.lookup("run").translation == "v. 跑"


def test_lemmatized_hit_records_original(dictionary):
    entry = dictionary.lookup("Running.")
    assert entry.word == "run" and entry.lemma_from == "Running"


def test_irregular_form(dictionary):
    assert dictionary.lookup("ran").word == "run"


def test_prefers_common_entry_over_capitalized_homograph(dictionary):
    assert dictionary.lookup("Apple").translation == "n. 蘋果"


def test_possessive(dictionary):
    assert dictionary.lookup("dog's").word == "dog"


@pytest.mark.parametrize("raw, base", [
    ("walked", "walk"), ("Walking", "walk"), ("stopped", "stop"),
    ("dogs", "dog"), ("dying", "die"),
])
def test_rule_based_fallback_when_forms_table_misses(dictionary, raw, base):
    entry = dictionary.lookup(raw)
    assert entry.word == base and entry.lemma_from == raw.strip()


def test_rule_based_fallback_ignores_uncommon_entries(dictionary):
    assert dictionary.lookup("this") is None        # "this" → "thi" 是 frq=0 的雜訊詞條


def test_inflection_note_only_entry_shows_lemma_instead(dictionary):
    entry = dictionary.lookup("went")
    assert entry.word == "go" and entry.lemma_from == "went"


def test_abbreviation_noise_entry_shows_lemma_instead(dictionary):
    assert dictionary.lookup("cats").word == "cat"


def test_entry_with_real_meaning_is_kept_even_if_it_is_a_form(dictionary):
    assert dictionary.lookup("saw").word == "saw"          # 有「n. 鋸子」的真實字義
    assert dictionary.lookup("jogging").word == "jogging"  # 有「n. 慢跑」的真實字義


def test_not_found(dictionary):
    assert dictionary.lookup("zzzzqx") is None


def test_missing_db_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Dictionary(tmp_path / "nope.db")


# ------------------------------------------------------------------ popup position
AVAIL = (0, 0, 1920, 1080)


def test_pos_default_bottom_right_of_cursor():
    assert compute_popup_pos((100, 100), (300, 120), AVAIL) == (112, 118)


def test_pos_flips_left_near_right_edge():
    x, y = compute_popup_pos((1900, 100), (300, 120), AVAIL)
    assert x == 1900 - 12 - 300 and y == 118


def test_pos_flips_up_near_bottom_edge():
    x, y = compute_popup_pos((100, 1070), (300, 120), AVAIL)
    assert x == 112 and y == 1070 - 18 - 120


def test_pos_clamped_inside_screen_corner():
    x, y = compute_popup_pos((1915, 1075), (300, 120), AVAIL)
    assert 0 <= x <= 1920 - 300 and 0 <= y <= 1080 - 120


def test_pos_respects_secondary_monitor_offset():
    avail = (-1920, 0, 0, 1080)       # 位於主螢幕左側的副螢幕
    x, y = compute_popup_pos((-10, 50), (300, 120), avail)
    assert x == -10 - 12 - 300


def test_pos_larger_than_screen_pins_top_left():
    assert compute_popup_pos((50, 50), (3000, 2000), AVAIL) == (0, 0)


# ------------------------------------------------------------------ lemma rules
@pytest.mark.parametrize("word, expected", [
    ("walked", "walk"), ("stopped", "stop"), ("running", "run"), ("making", "make"),
    ("carried", "carry"), ("studies", "study"), ("boxes", "box"), ("wolves", "wolf"),
    ("dying", "die"), ("bigger", "big"), ("happier", "happy"), ("larger", "large"),
    ("liked", "like"), ("cats", "cat"),
])
def test_rule_candidates_contains_base(word, expected):
    import lemma
    assert expected in lemma.rule_candidates(word)


@pytest.mark.parametrize("word", ["this", "glass", "was", "bus", "the"])
def test_rule_candidates_skip_non_inflections(word):
    import lemma
    assert lemma.rule_candidates(word) == []
