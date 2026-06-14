"""Shared data types."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def clean_title(raw: str) -> str:
    """Turn a sideloaded filename into a readable book title.

    Handles the messy real-world sources these come from:
      - Anna's Archive / Calibre: "Title -- Author -- year -- Publisher -- ..."
      - z-lib / libgen slugs:     "the-mom-test-en", "The+Anthology+of+Balaji"
    Keep the part before the first ' -- ', strip extensions and source junk, and
    turn separator-slugs back into spaced (and title-cased) words.
    """
    t = (raw or "").strip()
    if not t:
        return t
    t = re.split(r"\s+--\s+", t, maxsplit=1)[0]  # drop "-- Author -- ..."
    t = re.sub(r"\.(pdf|epub|mobi|azw3?|txt|docx?)$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"[\[\]]", " ", t)  # bracket fragments like "[pbk"

    # Normalise separators to spaces FIRST so junk-token boundaries work (an
    # underscore is a word char, so "\bcompressed\b" can't see "Chouinard_compressed").
    slug = bool(re.search(r"[-_+]", t)) and t.count(" ") <= 1
    was_lower = t == t.lower()
    t = re.sub(r"[-_+]+" if slug else r"[_+]+", " ", t)  # slug: also split hyphens

    # Strip source/format junk now that everything is space-delimited.
    t = re.sub(
        r"\boceanofpdf(?:\.?com)?\b|\blibgen(?:\.\w+)?\b|\bz[ ]?lib(?:rary)?\b"
        r"|\banna'?s archive\b|\bcompressed\b|\bpbk\b|\bretail\b|\ben$",
        "",
        t,
        flags=re.IGNORECASE,
    )

    t = re.sub(r"\s+", " ", t).strip(" -_")
    if slug and was_lower:
        t = t.title()
    return t or (raw or "").strip()


_JUNK_AUTHORS = {"unknown", "unknown author", "anonymous", "n/a", "na", "none", "author"}


def clean_author(raw: str | None) -> str | None:
    """Drop placeholder authors ("Unknown", "1", bare dates) so they don't render."""
    a = (raw or "").strip()
    if not a or a.lower() in _JUNK_AUTHORS:
        return None
    if re.fullmatch(r"[\d\s,.\-]+", a):  # "1", "1918-1988"
        return None
    return a


@dataclass
class Highlight:
    text: str
    source_title: str
    source_author: str | None = None
    source_type: str = "kindle"  # "kindle" | "pdf"
    note: str | None = None
    location: str | None = None
    added_at: str | None = None  # ISO timestamp of when it was highlighted, if known

    def hash(self) -> str:
        """Stable identity for de-duplication.

        Based only on the highlight text + book title, so re-importing the same
        clippings file (or re-dropping the same PDF) is idempotent. A later note
        added to the same highlight updates the existing row rather than making
        a new one.
        """
        key = f"{_normalize(self.text)}|{_normalize(self.source_title)}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()
