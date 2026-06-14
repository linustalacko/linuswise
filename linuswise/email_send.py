"""Deliver the rendered HTML — either over SMTP or to a local file for preview."""

from __future__ import annotations

import os
import smtplib
import ssl
import tempfile
import webbrowser
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

from .config import EmailConfig


def send(cfg: EmailConfig, html: str, subject: str | None = None, open_preview: bool = True) -> str:
    """Send via the configured method. Returns a human-readable status string."""
    subject = subject or cfg.subject
    if cfg.method == "file":
        return _to_file(html, open_preview)
    if cfg.method == "smtp":
        return _via_smtp(cfg, html, subject)
    raise ValueError(f"Unknown email method: {cfg.method!r} (use 'smtp' or 'file')")


def _to_file(html: str, open_preview: bool) -> str:
    out = Path(tempfile.gettempdir()) / "linuswise-daily.html"
    out.write_text(html, encoding="utf-8")
    # The preview lives in a shared temp dir; keep it readable only by its owner.
    if os.name == "posix":
        try:
            out.chmod(0o600)
        except OSError:
            pass
    if open_preview:
        webbrowser.open(out.as_uri())
    return f"Wrote preview to {out}"


def _via_smtp(cfg: EmailConfig, html: str, subject: str) -> str:
    if not cfg.recipient:
        raise ValueError("email.recipient is not set in config")
    if not cfg.smtp_password:
        raise ValueError(
            "No SMTP password. Set LINUSWISE_SMTP_PASSWORD or email.smtp_password in config."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.sender
    msg["To"] = cfg.recipient
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(
        "This is the HTML edition of your daily review. Open in an HTML-capable client."
    )
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
        if cfg.smtp_starttls:
            server.starttls(context=context)
        if cfg.smtp_username:
            server.login(cfg.smtp_username, cfg.smtp_password)
        server.send_message(msg)
    return f"Sent to {cfg.recipient} via {cfg.smtp_host}"
