"""Command-line entry point.

linuswise init                       set up the database
linuswise import-readwise FILE.csv   seed from a Readwise CSV export (your whole library)
linuswise ingest-kindle [--file P]   pull highlights off a plugged-in Kindle
linuswise ingest-pdf [PATH...]       ingest highlighted PDFs (default: the inbox folder)
linuswise embed                      compute local embeddings for Q&A
linuswise daily [--count N]          send today's spaced-repetition review email
          [--preview]               ...render without sending or marking reviewed
linuswise ask "question"             ask your library a question (Groq)
linuswise serve / app                open the review UI (browser / native window)
linuswise stats                      show library counts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import db, email_render, email_send, embeddings, ingest, qa
from .config import load
from .parsers import readwise_csv


def _connect(cfg):
    return db.connect(cfg.db_path)


def _auto_embed(cfg, conn) -> None:
    """Embed any new highlights so Q&A works without a manual step."""
    try:
        n = embeddings.embed_missing(conn, cfg.qa.embed_model)
        if n:
            print(f"  embedded {n} new highlight(s) for search")
    except Exception as e:  # noqa: BLE001 — never let embedding failure break ingest
        print(f"  (embeddings skipped: {e})", file=sys.stderr)


def cmd_init(cfg, args) -> int:
    _connect(cfg).close()
    print(f"Initialized database at {cfg.db_path}")
    return 0


def cmd_import_readwise(cfg, args) -> int:
    conn = _connect(cfg)
    highlights = readwise_csv.parse(args.file)
    inserted, updated = db.upsert(conn, highlights)
    print(f"Readwise import: {len(highlights)} parsed  →  {inserted} new, {updated} updated")
    if not args.no_embed:
        _auto_embed(cfg, conn)
    return 0


def cmd_ingest_kindle(cfg, args) -> int:
    conn = _connect(cfg)
    try:
        result = ingest.ingest_kindle(conn, cfg, Path(args.file) if args.file else None)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"Kindle: {result['source']}")
    print(f"  parsed {result['parsed']}  →  {result['inserted']} new, {result['updated']} updated")
    if not args.no_embed:
        _auto_embed(cfg, conn)
    return 0


def cmd_ingest_pdf(cfg, args) -> int:
    conn = _connect(cfg)
    if args.paths:
        result = ingest.ingest_pdf_files(
            conn, cfg, [Path(p) for p in args.paths], archive=args.archive
        )
    else:
        result = ingest.ingest_inbox(conn, cfg)
    for f in result["files"]:
        if "error" in f:
            print(f"  ! {f['file']}: {f['error']}", file=sys.stderr)
        else:
            print(
                f"  {Path(f['file']).name}: {f['parsed']} parsed, {f['inserted']} new, {f['updated']} updated"
            )
    print(f"PDF total: {result['inserted']} new, {result['updated']} updated")
    if not args.no_embed:
        _auto_embed(cfg, conn)
    return 0


def cmd_embed(cfg, args) -> int:
    conn = _connect(cfg)
    print(f"Embedding with {cfg.qa.embed_model} (first run downloads the model)…")
    n = embeddings.embed_missing(conn, cfg.qa.embed_model)
    print(f"Embedded {n} highlight(s). {db.stats(conn)['embedded']} total embedded.")
    return 0


def cmd_daily(cfg, args) -> int:
    conn = _connect(cfg)
    count = args.count if args.count is not None else cfg.review_count

    if args.preview:
        rows = db.pick_for_review(conn, count, cfg.min_highlight_chars)
        if not rows:
            print("No highlights to review yet. Seed some first.", file=sys.stderr)
            return 1
        html = email_render.render(rows, total_known=db.stats(conn)["total"])
        print(email_send._to_file(html, open_preview=True) + "  (preview — not marked reviewed)")
        return 0

    # The persisted daily batch is shared with the desktop app's "Today" view.
    rows = db.get_or_create_today(conn, count, cfg.min_highlight_chars)
    if not rows:
        print("No highlights to review yet. Seed some first.", file=sys.stderr)
        return 1
    html = email_render.render(rows, total_known=db.stats(conn)["total"])
    status = email_send.send(cfg.email, html, open_preview=True)
    print(status)
    return 0


def cmd_ask(cfg, args) -> int:
    conn = _connect(cfg)
    try:
        ans = qa.ask(
            conn,
            args.question,
            k=args.k or cfg.qa.retrieve_k,
            model=cfg.qa.groq_model,
            api_key=cfg.qa.groq_api_key,
            embed_model=cfg.qa.embed_model,
        )
    except Exception as e:  # noqa: BLE001
        print(str(e), file=sys.stderr)
        return 1
    print(ans.text + "\n")
    for i, r in enumerate(ans.sources, 1):
        print(f"  [{i}] {r['text'][:90]}…  — {r['source_title']}")
    return 0


def cmd_serve(cfg, args) -> int:
    from . import web

    web.serve(cfg, open_browser=not args.no_browser)
    return 0


def cmd_app(cfg, args) -> int:
    from . import app

    app.run(cfg)
    return 0


def cmd_stats(cfg, args) -> int:
    s = db.stats(_connect(cfg))
    print(f"Library: {s['total']} highlights across {s['books']} sources")
    print(f"  by type: {s['by_type']}")
    print(f"  reviewed: {s['reviewed']}   favorites: {s['favorites']}   embedded: {s['embedded']}")
    return 0


def main(argv=None) -> int:
    cfg = load()
    parser = argparse.ArgumentParser(prog="linuswise", description="A tiny self-hosted Readwise.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the database")

    p_r = sub.add_parser("import-readwise", help="seed from a Readwise CSV export")
    p_r.add_argument("file", help="path to the Readwise export .csv")
    p_r.add_argument("--no-embed", action="store_true", help="skip building embeddings")

    p_k = sub.add_parser("ingest-kindle", help="ingest from a plugged-in Kindle")
    p_k.add_argument("--file", help="path to a My Clippings.txt instead of auto-detecting")
    p_k.add_argument("--no-embed", action="store_true")

    p_p = sub.add_parser("ingest-pdf", help="ingest highlighted PDFs")
    p_p.add_argument("paths", nargs="*", help="PDF files (default: scan the inbox folder)")
    p_p.add_argument(
        "--archive", action="store_true", help="move ingested files to the archive dir"
    )
    p_p.add_argument("--no-embed", action="store_true")

    sub.add_parser("embed", help="compute local embeddings for Q&A")

    p_d = sub.add_parser("daily", help="send today's review email")
    p_d.add_argument("--count", type=int, default=None, help="number of highlights")
    p_d.add_argument(
        "--preview", action="store_true", help="render without sending or marking reviewed"
    )

    p_a = sub.add_parser("ask", help="ask your highlights a question")
    p_a.add_argument("question")
    p_a.add_argument("-k", type=int, default=None, help="number of highlights to retrieve")

    p_s = sub.add_parser("serve", help="open the review UI in your browser")
    p_s.add_argument("--no-browser", action="store_true")

    sub.add_parser("app", help="open the review UI in a native window")
    sub.add_parser("stats", help="show library counts")

    args = parser.parse_args(argv)
    handler = {
        "init": cmd_init,
        "import-readwise": cmd_import_readwise,
        "ingest-kindle": cmd_ingest_kindle,
        "ingest-pdf": cmd_ingest_pdf,
        "embed": cmd_embed,
        "daily": cmd_daily,
        "ask": cmd_ask,
        "serve": cmd_serve,
        "app": cmd_app,
        "stats": cmd_stats,
    }[args.cmd]
    return handler(cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
