<div align="center">

<img src="linuswise/static/logo.svg" width="72" height="72" alt="Linuswise logo" />

# Linuswise

**A tiny, self-hosted Readwise that runs locally on your Mac.**

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![CI](https://github.com/linustalacko/linuswise/actions/workflows/ci.yml/badge.svg)](https://github.com/linustalacko/linuswise/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/packaged%20with-uv-DE5FE9.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

<!-- Drop a screenshot or short GIF of the review app / daily email here, e.g.:
<p align="center"><img src="docs/screenshot.png" width="720" alt="Linuswise review app" /></p>
-->

Linuswise keeps your reading highlights — Kindle, PDFs, and your existing
Readwise library — in one local SQLite database, and brings them back to you with
a spaced-repetition daily email and a small review app. No accounts, no cloud
storage. Every pixel of UI is on a 4px grid.

1. **Seed from Readwise** — import your existing [Readwise](https://readwise.io)
   CSV export (your whole library) in one shot.
2. **Sync your Kindle** — parses `My Clippings.txt` off the device when you plug
   it in. Captures *everything*, including side-loaded PDFs and personal docs
   that the read.amazon.com cloud export misses.
3. **Ingest highlighted PDFs** — drop a PDF you highlighted anywhere (Preview,
   Skim, …) into an inbox folder and it pulls the highlights out.
4. **Spaced-repetition daily email** — an HTML digest, every morning.
5. **Desktop review app** — skip / keep / rewind through the day's highlights,
   browse your whole library.
6. **Ask your highlights** — semantic search + a Groq-written answer with
   citations. Embeddings are computed locally; only the retrieved snippets leave
   your Mac.

## Setup

Requires [uv](https://github.com/astral-sh/uv) and Python 3.12+.

**Quickest way to try it** (no clone needed, just [uv](https://github.com/astral-sh/uv)): `uvx --from git+https://github.com/linustalacko/linuswise linuswise --help`

Or install it from source:

```bash
git clone https://github.com/linustalacko/linuswise.git
cd linuswise

uv sync                                                   # core
uv sync --extra desktop                                   # + native window (pywebview)
cp config.example.toml ~/.config/linuswise/config.toml    # then edit
cp secrets.env.example ~/.config/linuswise/secrets.env    # app password + Groq key
chmod 600 ~/.config/linuswise/secrets.env
uv run linuswise init
```

## Seed everything you have

```bash
# Readwise → readwise.io/export → "Export to CSV", then:
uv run linuswise import-readwise ~/Downloads/readwise-export.csv   # also builds embeddings
uv run linuswise stats
```

## Daily use

```bash
uv run linuswise ingest-kindle           # plug in Kindle, auto-detects the volume
uv run linuswise ingest-pdf              # ingest PDFs from the inbox folder
uv run linuswise daily --preview         # see today's email in the browser
uv run linuswise daily                   # build + send it (and pin today's batch)

uv run linuswise app                     # native review window (or `serve` for a browser tab)
uv run linuswise ask "what have I read about decision-making?"
```

In the app: **★ Keep** (favorite), **Skip**, **↶ Rewind**, 🗑 discard. Keyboard:
`k`/→ keep, `s` skip, `←` rewind, `d` discard. The **Library** tab has search,
a favorites filter, and the **Ask** box.

## Email (Gmail at 11am)

`method = "smtp"` in config, a Gmail App Password in `secrets.env`, then:

```bash
./scripts/install-launchd.sh            # daily email 11:00 + Kindle plug-in sync
HOUR=7 MINUTE=30 ./scripts/install-launchd.sh
```

See [launchd/README.md](launchd/README.md).

## How it fits together

```
Readwise CSV ─┐
Kindle file  ─┼─► parse ─► SQLite (dedup) ─┬─► spaced-rep pick ─► HTML email
PDFs         ─┘                            ├─► review app (skip/keep/rewind, library)
                                           └─► local embeddings ─► retrieve ─► Groq ─► cited answer
```

- `linuswise/parsers/` — Readwise CSV, Kindle clippings, PDF highlights
- `linuswise/db.py` — storage, review selection, daily batch, favorites
- `linuswise/embeddings.py` — local model2vec vectors + cosine search
- `linuswise/qa.py` — retrieval + Groq answer
- `linuswise/web.py` — Flask app + the 4px-grid UI; `linuswise/app.py` — native window
- `linuswise/email_render.py` / `email_send.py` — the email

> There's also an experimental Tauri desktop wrapper in
> [`linuswise-desktop/`](linuswise-desktop/) — see its README. For most people
> `uv run linuswise app` (the pywebview window) is the simplest native UI.

## Privacy & security

Linuswise is local-first by design. The review UI binds to `127.0.0.1` only and
should **not** be exposed to a network without adding authentication. The **Ask**
feature is the only thing that sends data off your machine: embeddings are
computed locally, and only the handful of retrieved snippets (and their notes)
are sent to Groq to write the answer — never your whole library. Treat the files
you ingest (Kindle clippings, PDFs) as trusted input. See
[SECURITY.md](SECURITY.md) for details and how to report a vulnerability.

## Known limits

- Kindle Store books sync via the file only when you plug in (no official Amazon
  API; over-the-air cloud sync omits personal docs anyway).
- PDF extraction needs real highlight annotations + a text layer (OCR scans
  first).
- Ask sends the retrieved highlights to Groq at query time. For zero data leaving
  the machine, point `qa` at a local Ollama instead.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports
and feature requests go in
[Issues](https://github.com/linustalacko/linuswise/issues).

## License

[MIT](LICENSE) © Linus Talacko

> Not affiliated with or endorsed by Readwise. "Readwise" and "Kindle" are
> trademarks of their respective owners; Linuswise simply reads their exports.


## linuswise vs Readwise

linuswise is a self-hosted, open-source **alternative to Readwise** for people who want to own their highlights locally instead of paying a subscription. An honest comparison:

| | linuswise | Readwise |
| --- | --- | --- |
| License | MIT, open source | Proprietary |
| Price | Free (self-hosted) | Paid subscription |
| Where your data lives | Local SQLite on your Mac | Readwise cloud |
| Kindle highlights | Pulled off the device (`My Clippings.txt`) — catches side-loaded PDFs & personal docs | Cloud sync (misses side-loaded/personal docs) |
| PDF highlights | Ingests annotated PDFs from a folder | Supported |
| Import existing Readwise library | Yes — CSV export | n/a |
| Daily review | Spaced-repetition daily email | Daily email / app |
| Search | Local semantic "ask your library" (embeddings local; snippets to Groq, or local Ollama) | Cloud search / AI |
| Account required | No | Yes |
| Apps | Local review app (macOS) | iOS, Android, web |
| Setup | Command line (`uv`); macOS-centric | Polished, zero-setup |

**Choose linuswise** if you want to own your highlights in a local file with no subscription and no cloud, and you're comfortable with a little command-line setup on a Mac.

**Stick with Readwise** if you want a polished, cross-device, zero-setup product with mobile apps and official integrations.

## FAQ

**Is this affiliated with Readwise?** No — linuswise is an independent, open-source tool that reads your own exports. "Readwise" and "Kindle" are trademarks of their owners.

**Does my data leave my machine?** Only the optional "ask your library" feature, and only the few retrieved snippets, are sent to Groq to write an answer — embeddings are computed locally. Point it at a local Ollama for zero data leaving your Mac. Everything else is local SQLite.

**Why read `My Clippings.txt` instead of Amazon's export?** Amazon's cloud export omits side-loaded PDFs and personal documents; reading the device file captures everything you've highlighted.

**Is it free?** Yes — MIT-licensed and free to self-host.

**Does it run on Windows or Linux?** It's macOS-centric today (Kindle mounting, launchd scheduling). The core is Python, so other platforms may partly work but aren't supported yet.
