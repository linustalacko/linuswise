from pathlib import Path

from linuswise.parsers import myclippings

SAMPLE = (Path(__file__).parent / "sample_clippings.txt").read_text(encoding="utf-8")


def test_parses_highlights_and_skips_bookmarks():
    hs = myclippings.parse(SAMPLE)
    # 3 highlights; the bookmark and the standalone note are not their own rows.
    assert len(hs) == 3
    texts = [h.text for h in hs]
    assert any("engine of all progress" in t for t in texts)
    assert any("Personal documents and PDFs" in t for t in texts)
    assert any("Nothing in life is as important" in t for t in texts)


def test_title_author_split():
    hs = myclippings.parse(SAMPLE)
    deutsch = next(h for h in hs if "engine of all progress" in h.text)
    assert deutsch.source_title == "The Beginning of Infinity"
    assert deutsch.source_author == "David Deutsch"


def test_note_attached_to_matching_highlight():
    hs = myclippings.parse(SAMPLE)
    deutsch = next(h for h in hs if "engine of all progress" in h.text)
    assert deutsch.note == "Connects to the idea of error-correction."


def test_added_at_parsed():
    hs = myclippings.parse(SAMPLE)
    deutsch = next(h for h in hs if "engine of all progress" in h.text)
    assert deutsch.added_at is not None and deutsch.added_at.startswith("2026-06-01")


def test_pdf_personal_doc_location():
    hs = myclippings.parse(SAMPLE)
    pdf = next(h for h in hs if "Personal documents" in h.text)
    assert pdf.source_title == "Some Sideloaded Paper.pdf"
    assert pdf.location == "page 5"


def test_dedup_hash_stable():
    hs = myclippings.parse(SAMPLE)
    again = myclippings.parse(SAMPLE)
    assert {h.hash() for h in hs} == {h.hash() for h in again}
