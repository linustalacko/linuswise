"""Parse a Kindle ``My Clippings.txt`` file.

This is the file that lives on the Kindle itself (``documents/My Clippings.txt``
when you plug it in over USB). Crucially it contains highlights from *everything*
you read on the device — including side-loaded PDFs and personal documents,
which the read.amazon.com cloud export does NOT cover. That's why it's the right
source for a PDF-heavy reader.

Format: records separated by a line of ten '=' characters. Each record is::

    Title (Author)
    - Your Highlight on page 12 | Location 145-146 | Added on Monday, June 1, 2026 9:41:00 AM

    The actual highlighted text.

The metadata line varies across Kindle firmware ("page" vs "Page", with or
without a Location, etc.), and records may be Highlights, Notes, or Bookmarks.
We parse defensively and merge a Note onto the Highlight at the same location.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..models import Highlight

SEPARATOR = "=========="

_KIND_RE = re.compile(r"-\s*Your\s+(Highlight|Note|Bookmark)", re.IGNORECASE)
_PAGE_RE = re.compile(r"page\s+([\w-]+)", re.IGNORECASE)
_LOC_RE = re.compile(r"location\s+([\w-]+)", re.IGNORECASE)
_ADDED_RE = re.compile(r"Added on\s+(.+)$", re.IGNORECASE)
# Title line: "Some Title (Last, First)" — author is the final parenthetical.
_TITLE_AUTHOR_RE = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")


def _parse_added(meta: str) -> str | None:
    m = _ADDED_RE.search(meta)
    if not m:
        return None
    raw = m.group(1).strip()
    # e.g. "Monday, June 1, 2026 9:41:00 AM"
    for fmt in ("%A, %B %d, %Y %I:%M:%S %p", "%A, %d %B %Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue
    return None


def _split_title_author(line: str) -> tuple[str, str | None]:
    line = line.lstrip("﻿").strip()
    m = _TITLE_AUTHOR_RE.match(line)
    if m:
        return m.group(1).strip(), m.group(2).strip() or None
    return line, None


def _location_label(meta: str) -> str | None:
    loc = _LOC_RE.search(meta)
    page = _PAGE_RE.search(meta)
    parts = []
    if page:
        parts.append(f"page {page.group(1)}")
    if loc:
        parts.append(f"location {loc.group(1)}")
    return " · ".join(parts) or None


def _loc_key(meta: str) -> str | None:
    """A coarse key (page or location number) used to attach notes to highlights."""
    loc = _LOC_RE.search(meta)
    if loc:
        return f"loc:{loc.group(1).split('-')[0]}"
    page = _PAGE_RE.search(meta)
    if page:
        return f"page:{page.group(1)}"
    return None


def parse(text: str) -> list[Highlight]:
    highlights: list[Highlight] = []
    # (title, loc_key) -> note text, so we can fold notes into their highlight.
    pending_notes: dict[tuple[str, str | None], str] = {}

    records = text.replace("\r\n", "\n").split(SEPARATOR)
    for record in records:
        lines = [ln.rstrip() for ln in record.split("\n")]
        # Drop leading blank lines but keep internal structure.
        while lines and not lines[0].strip():
            lines.pop(0)
        if len(lines) < 2:
            continue

        title, author = _split_title_author(lines[0])
        meta = lines[1]
        kind_m = _KIND_RE.search(meta)
        if not kind_m:
            continue
        kind = kind_m.group(1).lower()

        body = "\n".join(lines[2:]).strip()
        if kind == "bookmark" or not body:
            continue

        key = (title, _loc_key(meta))
        if kind == "note":
            pending_notes[key] = body
            continue

        highlights.append(
            Highlight(
                text=body,
                source_title=title,
                source_author=author,
                source_type="kindle",
                location=_location_label(meta),
                added_at=_parse_added(meta),
            )
        )

    # Second pass: attach any note that shares a (title, location) with a highlight.
    # Both the highlight's stored location label and the note's metadata line run
    # through _loc_key, so the keys line up.
    for h in highlights:
        if not h.location:
            continue
        note_key = (h.source_title, _loc_key(h.location))
        if note_key in pending_notes:
            h.note = pending_notes[note_key]

    return highlights
