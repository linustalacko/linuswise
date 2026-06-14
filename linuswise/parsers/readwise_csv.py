"""Import a Readwise CSV export (readwise.io/export → "Export to CSV").

This is the fastest way to seed your entire existing library at once — every
Kindle book, PDF, article, everything Readwise already holds. The export has a
header row; columns have shifted across Readwise versions, so we match by name
(case-insensitively) rather than by position.

Typical columns:
    Highlight, Book Title, Book Author, Amazon Book ID, Note, Color, Tags,
    Location Type, Location, Highlighted at, Document tags, Document URL
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from ..models import Highlight, clean_author, clean_title


def _get(row: dict, *names: str) -> str:
    for n in names:
        for key, val in row.items():
            if key and key.strip().lower() == n.lower():
                return (val or "").strip()
    return ""


def _parse_dt(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).isoformat()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue
    return None


def _location(row: dict) -> str | None:
    loc_type = _get(row, "Location Type")
    loc = _get(row, "Location")
    if loc and loc_type:
        return f"{loc_type} {loc}"
    return loc or loc_type or None


def parse(path: str | Path) -> list[Highlight]:
    path = Path(path)
    out: list[Highlight] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            text = _get(row, "Highlight")
            title = _get(row, "Book Title", "Title")
            if not text or not title:
                continue
            amazon_id = _get(row, "Amazon Book ID")
            out.append(
                Highlight(
                    text=text,
                    source_title=clean_title(title),
                    source_author=clean_author(_get(row, "Book Author", "Author")),
                    # Books with an Amazon id came from Kindle; the rest are PDFs/articles.
                    source_type="kindle" if amazon_id else "pdf",
                    note=_get(row, "Note") or None,
                    location=_location(row),
                    added_at=_parse_dt(_get(row, "Highlighted at", "Highlighted At")),
                )
            )
    return out
