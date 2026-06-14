#!/bin/sh
# Fires when a volume mounts (launchd WatchPaths on /Volumes). Tries to ingest a
# Kindle; harmlessly no-ops when the mounted volume isn't a Kindle.
set -u

DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

LOG="$HOME/.local/share/linuswise/agent.log"
mkdir -p "$(dirname "$LOG")"

cd "$DIR"
{
  echo "=== kindle-sync $(date) ==="
  uv run linuswise ingest-kindle || echo "(no Kindle mounted)"
} >> "$LOG" 2>&1
