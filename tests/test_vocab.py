import csv

import pytest

from dictionary import Entry
from vocab import CSV_HEADER, VocabBook


@pytest.fixture()
def book(tmp_path):
    b = VocabBook(tmp_path / "vocab.db")
    yield b
    b.close()


def entry(word="run", kk="rʌn", src="cmu", translation="v. 跑\nn. 賽跑"):
    return Entry(word, kk, None, src, translation)


def test_toggle_adds_then_removes(book):
    assert not book.contains("run")
    assert book.toggle(entry()) is True
    assert book.contains("run") and book.contains("RUN")      # 不分大小寫
    assert book.toggle(entry()) is False
    assert not book.contains("run") and book.count() == 0


def test_add_twice_keeps_one_row(book):
    book.add(entry())
    book.add(entry())
    assert book.count() == 1


def test_persists_across_reopen(tmp_path):
    path = tmp_path / "vocab.db"
    b1 = VocabBook(path)
    b1.add(entry())
    b1.close()
    b2 = VocabBook(path)
    assert b2.contains("run")
    b2.close()


def test_export_csv_format(book, tmp_path):
    book.add(entry("run"))
    book.add(entry("apple", "ˋæpl̩", "approx", "n. 蘋果"))
    out = tmp_path / "vocab.csv"
    assert book.export_csv(out) == 2

    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                      # UTF-8 BOM：Excel 才不會亂碼
    rows = list(csv.reader(out.read_text(encoding="utf-8-sig").splitlines()))
    assert rows[0] == CSV_HEADER
    by_word = {r[0]: r for r in rows[1:]}
    assert by_word["run"][1] == "[rʌn]" and by_word["run"][2] == "v. 跑 / n. 賽跑"
    assert by_word["apple"][1] == "≈[ˋæpl̩]"                     # 近似音標保留標記


def test_export_empty_book_writes_header_only(book, tmp_path):
    out = tmp_path / "empty.csv"
    assert book.export_csv(out) == 0
    assert out.read_text(encoding="utf-8-sig").strip() == ",".join(CSV_HEADER)
