# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-13

### Added

- Initial public release.
- Seed from a Readwise CSV export (your whole library) in one shot.
- Ingest Kindle highlights by parsing `My Clippings.txt` off a plugged-in device.
- Ingest highlighted PDFs from an inbox folder (PyMuPDF).
- Spaced-repetition daily email digest (Jinja2 + SMTP), schedulable via launchd.
- Review app (browser tab or native pywebview window): skip / keep / rewind /
  discard, plus a searchable library.
- "Ask your highlights" — local model2vec embeddings + cosine retrieval, with a
  Groq-written, cited answer.
- Deduplicating SQLite storage.

### Security

- Embeddings are computed locally; only retrieved snippets are sent to Groq.
- The review UI binds to `127.0.0.1` only.
- Secrets live in `secrets.env` / env vars (gitignored), never in the repo;
  dependency floors raised for parser/security fixes.

[Unreleased]: https://github.com/linustalacko/linuswise/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/linustalacko/linuswise/releases/tag/v0.1.0
