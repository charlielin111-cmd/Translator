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
    ]
    db.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?)", rows)
    db.executemany("INSERT INTO forms VALUES (?,?)",
                   [("running", "run"), ("studies", "study"), ("ran", "run"), ("run", "run")])
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
