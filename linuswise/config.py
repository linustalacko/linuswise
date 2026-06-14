"""Configuration loading.

Config is a single TOML file. We look for it in this order:
  1. $LINUSWISE_CONFIG (if set)
  2. ./config.toml            (handy during development)
  3. ~/.config/linuswise/config.toml

Anything not specified falls back to the defaults below. Secrets (the SMTP
password in particular) can be kept out of the file and supplied via the
environment variable LINUSWISE_SMTP_PASSWORD instead.
"""

from __future__ import annotations

import os
import stat
import sys
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p)))


def _warn_if_loose_perms(path: Path, data: dict) -> None:
    """If the config file holds a secret yet is readable by other local users,
    nudge the user to lock it down (mirrors how ssh warns on key permissions)."""
    has_secret = bool(
        data.get("email", {}).get("smtp_password") or data.get("qa", {}).get("groq_api_key")
    )
    if not has_secret or os.name != "posix":
        return
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        print(
            f"warning: {path} contains a secret but is readable by other users. "
            f"Run: chmod 600 {path}",
            file=sys.stderr,
        )


@dataclass(frozen=True)
class EmailConfig:
    # "smtp" sends a real email; "file" just writes the HTML to disk and opens
    # it (no credentials needed) — great for previewing the layout.
    method: str = "file"
    sender: str = "linuswise@localhost"
    recipient: str = ""
    subject: str = "Your Daily Linuswise"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""  # prefer the LINUSWISE_SMTP_PASSWORD env var
    smtp_starttls: bool = True


@dataclass(frozen=True)
class QAConfig:
    groq_api_key: str = ""  # prefer the GROQ_API_KEY env var
    groq_model: str = "llama-3.3-70b-versatile"
    embed_model: str = "minishlab/potion-base-8M"
    retrieve_k: int = 10


@dataclass(frozen=True)
class Config:
    db_path: Path = field(default_factory=lambda: _expand("~/.local/share/linuswise/linuswise.db"))
    inbox_dir: Path = field(default_factory=lambda: _expand("~/linuswise-inbox"))
    # Defaults to <inbox_dir>/_ingested unless set explicitly (see load()).
    archive_dir: Path = field(default_factory=lambda: _expand("~/linuswise-inbox/_ingested"))
    review_count: int = 5
    min_highlight_chars: int = 20  # skip trivially short snippets in reviews
    web_port: int = 8765
    email: EmailConfig = field(default_factory=EmailConfig)
    qa: QAConfig = field(default_factory=QAConfig)


def _config_path() -> Path | None:
    env = os.environ.get("LINUSWISE_CONFIG")
    if env:
        return _expand(env)
    candidates = [Path("config.toml"), _expand("~/.config/linuswise/config.toml")]
    return next((c for c in candidates if c.exists()), None)


def load() -> Config:
    cfg = Config()
    path = _config_path()
    data: dict = {}
    if path and path.exists():
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        _warn_if_loose_perms(path, data)

    email_data = data.get("email", {})
    email = EmailConfig(
        method=email_data.get("method", cfg.email.method),
        sender=email_data.get("sender", cfg.email.sender),
        recipient=email_data.get("recipient", cfg.email.recipient),
        subject=email_data.get("subject", cfg.email.subject),
        smtp_host=email_data.get("smtp_host", cfg.email.smtp_host),
        smtp_port=int(email_data.get("smtp_port", cfg.email.smtp_port)),
        smtp_username=email_data.get("smtp_username", cfg.email.smtp_username),
        smtp_password=os.environ.get(
            "LINUSWISE_SMTP_PASSWORD", email_data.get("smtp_password", cfg.email.smtp_password)
        ),
        smtp_starttls=bool(email_data.get("smtp_starttls", cfg.email.smtp_starttls)),
    )

    qa_data = data.get("qa", {})
    qa = QAConfig(
        groq_api_key=os.environ.get(
            "GROQ_API_KEY", qa_data.get("groq_api_key", cfg.qa.groq_api_key)
        ),
        groq_model=qa_data.get("groq_model", cfg.qa.groq_model),
        embed_model=qa_data.get("embed_model", cfg.qa.embed_model),
        retrieve_k=int(qa_data.get("retrieve_k", cfg.qa.retrieve_k)),
    )

    inbox_dir = _expand(data["inbox_dir"]) if "inbox_dir" in data else cfg.inbox_dir
    # Archive lives under the inbox by default, so overriding inbox_dir alone
    # keeps ingested files alongside it rather than at the home-dir default.
    archive_dir = _expand(data["archive_dir"]) if "archive_dir" in data else inbox_dir / "_ingested"

    return replace(
        cfg,
        db_path=_expand(data["db_path"]) if "db_path" in data else cfg.db_path,
        inbox_dir=inbox_dir,
        archive_dir=archive_dir,
        review_count=int(data.get("review_count", cfg.review_count)),
        min_highlight_chars=int(data.get("min_highlight_chars", cfg.min_highlight_chars)),
        web_port=int(data.get("web_port", cfg.web_port)),
        email=email,
        qa=qa,
    )
