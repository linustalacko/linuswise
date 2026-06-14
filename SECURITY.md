# Security Policy

## Supported versions

Linuswise is pre-1.0. Security fixes land on the latest release and `main`.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately via GitHub's
[**Report a vulnerability**](https://github.com/linustalacko/linuswise/security/advisories/new)
form (the **Security** tab → "Report a vulnerability"). I'll acknowledge your
report, work with you on a fix, and credit you if you'd like.

## Threat model

Linuswise is a local-first tool. The boundaries worth knowing about:

- **Local-only web UI.** The review app (`serve` / `app`) binds to `127.0.0.1`
  only. Do **not** expose it to a network or `0.0.0.0` — it has no authentication
  and is meant for your machine alone.
- **Data leaving your machine.** Only the **Ask** feature sends anything out:
  embeddings are computed locally, and only the handful of retrieved snippets
  (plus their notes) are sent to Groq to write an answer — never your whole
  library. If you want zero egress, point the `qa` step at a local model instead.
- **Untrusted input files.** Kindle `My Clippings.txt` and PDFs you ingest are
  parsed locally (PyMuPDF for PDFs). Treat the files you feed in as you would any
  document you open. Dependency floors are kept current for parser/security fixes
  (see `pyproject.toml`).
- **Secrets.** Your SMTP app password and Groq key live in
  `~/.config/linuswise/secrets.env` (`chmod 600`) or environment variables —
  never in the repo. `secrets.env`, `config.toml`, and `*.db` are gitignored.

If you find a way for an ingested file to execute code, for the local UI to be
reachable off-host, or for more than the retrieved snippets to be sent to Groq,
that's exactly the kind of report I want to hear about.
