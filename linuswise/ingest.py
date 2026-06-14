"""Ingestion: get highlights from a Kindle and from PDFs into the database."""

from __future__ import annotations

import shutil
from pathlib import Path

from . import db
from .config import Config
from .parsers import myclippings, pdf

# Where My Clippings.txt lives on a mounted Kindle, relative to the volume root.
_CLIPPINGS_RELPATHS = ["documents/My Clippings.txt", "My Clippings.txt"]


def _unique_dest(archive_dir: Path, name: str) -> Path:
    """A destination in archive_dir that won't clobber an existing file."""
    dest = archive_dir / name
    if not dest.exists():
        return dest
    stem, suffix = Path(name).stem, Path(name).suffix
    i = 1
    while (cand := archive_dir / f"{stem}.{i}{suffix}").exists():
        i += 1
    return cand


def find_kindle_clippings() -> Path | None:
    """Locate My Clippings.txt on any currently-mounted Kindle volume."""
    for vol in Path("/Volumes").glob("*"):
        for rel in _CLIPPINGS_RELPATHS:
            candidate = vol / rel
            if candidate.exists():
                return candidate
    return None


def ingest_kindle(conn, cfg: Config, clippings_file: Path | None = None) -> dict:
    path = clippings_file or find_kindle_clippings()
    if path is None:
        raise FileNotFoundError(
            "No Kindle found. Plug in your Kindle, or pass --file path/to/My Clippings.txt"
        )
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    highlights = myclippings.parse(text)
    inserted, updated = db.upsert(conn, highlights)
    return {
        "source": str(path),
        "parsed": len(highlights),
        "inserted": inserted,
        "updated": updated,
    }


def ingest_pdf_files(conn, cfg: Config, paths: list[Path], archive: bool = False) -> dict:
    total_parsed = total_inserted = total_updated = 0
    per_file = []
    for p in paths:
        try:
            highlights = pdf.parse(p)
        except Exception as e:  # noqa: BLE001 - keep going on one bad file
            per_file.append({"file": str(p), "error": str(e)})
            continue
        inserted, updated = db.upsert(conn, highlights)
        total_parsed += len(highlights)
        total_inserted += inserted
        total_updated += updated
        entry = {
            "file": str(p),
            "parsed": len(highlights),
            "inserted": inserted,
            "updated": updated,
        }
        per_file.append(entry)
        # Only archive files we actually got highlights from, so a file that
        # parsed empty stays in the inbox to retry rather than vanishing.
        if archive and inserted + updated > 0:
            cfg.archive_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(p), str(_unique_dest(cfg.archive_dir, Path(p).name)))
            except OSError as e:
                entry["archive_error"] = str(e)
    return {
        "files": per_file,
        "parsed": total_parsed,
        "inserted": total_inserted,
        "updated": total_updated,
    }


def ingest_inbox(conn, cfg: Config) -> dict:
    """Scan the inbox folder for PDFs and ingest them, then archive."""
    cfg.inbox_dir.mkdir(parents=True, exist_ok=True)
    # Skip symlinks so a planted link in a shared inbox can't redirect the parser.
    pdfs = [p for p in cfg.inbox_dir.glob("*.pdf") if p.is_file() and not p.is_symlink()]
    return ingest_pdf_files(conn, cfg, pdfs, archive=True)
