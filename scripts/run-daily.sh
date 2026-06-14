#!/bin/sh
# Daily job: ingest any PDFs sitting in the inbox, then send the review email.
# Invoked by the launchd "daily" agent. For automation, set email.method = "smtp"
# in your config (method = "file" would try to pop a browser).
set -eu

DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# Optional secrets file: e.g. export LINUSWISE_SMTP_PASSWORD=...
[ -f "$HOME/.config/linuswise/secrets.env" ] && . "$HOME/.config/linuswise/secrets.env"

LOG="$HOME/.local/share/linuswise/agent.log"
mkdir -p "$(dirname "$LOG")"

cd "$DIR"
{
  echo "=== daily $(date) ==="
  uv run linuswise ingest-pdf || true
  uv run linuswise daily
} >> "$LOG" 2>&1
