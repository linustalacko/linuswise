# Contributing to Linuswise

Thanks for your interest in improving Linuswise! This guide covers how to get set
up and what to expect.

## Development setup

Requires [uv](https://github.com/astral-sh/uv) and Python 3.12+.

```bash
uv sync --group dev            # core + dev tools (ruff, pytest)
uv run linuswise init          # set up a local database to test against
```

## Checks before you open a PR

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # formatting
uv run python -m pytest        # tests
```

`uv run ruff format .` will fix formatting for you. The same checks run in CI on
every pull request.

## Code style

- Formatting and linting are handled by [Ruff](https://docs.astral.sh/ruff/)
  (config in `pyproject.toml`). Run `uv run ruff format .` before committing.
- Match the surrounding style; editor defaults are captured in
  [`.editorconfig`](.editorconfig).
- Keep changes focused — one logical change per PR makes review easier.

## A note on the parsers

The trickiest code is in `linuswise/parsers/` (Readwise CSV, Kindle clippings,
PDF highlights). Real-world inputs vary a lot, so if you fix a parsing edge case,
a small sample (sanitized — no personal highlights) added to `tests/` is hugely
appreciated.

## Reporting bugs and requesting features

Use the [issue templates](https://github.com/linustalacko/linuswise/issues/new/choose).
For anything security-sensitive, follow [SECURITY.md](SECURITY.md) instead of
opening a public issue.

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
