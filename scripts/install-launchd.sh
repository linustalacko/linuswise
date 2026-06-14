#!/bin/sh
# Generate and load the two launchd agents:
#   - com.linustalacko.linuswise.kindlesync : ingest a Kindle whenever a volume mounts
#   - com.linustalacko.linuswise.daily      : send the review email every morning
#
# Re-run this any time to update them (it unloads then reloads). Override the
# email time with HOUR=7 MINUTE=30 ./scripts/install-launchd.sh
set -eu

DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
HOUR="${HOUR:-11}"
MINUTE="${MINUTE:-0}"
UID_NUM="$(id -u)"
mkdir -p "$AGENTS"
chmod +x "$DIR/scripts/run-daily.sh" "$DIR/scripts/run-kindle-sync.sh"

daily_plist="$AGENTS/com.linustalacko.linuswise.daily.plist"
kindle_plist="$AGENTS/com.linustalacko.linuswise.kindlesync.plist"

cat > "$kindle_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.linustalacko.linuswise.kindlesync</string>
  <key>ProgramArguments</key>
  <array><string>$DIR/scripts/run-kindle-sync.sh</string></array>
  <key>WatchPaths</key>
  <array><string>/Volumes</string></array>
  <key>StandardErrorPath</key><string>$HOME/.local/share/linuswise/agent.err</string>
</dict>
</plist>
EOF

cat > "$daily_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.linustalacko.linuswise.daily</string>
  <key>ProgramArguments</key>
  <array><string>$DIR/scripts/run-daily.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>StandardErrorPath</key><string>$HOME/.local/share/linuswise/agent.err</string>
</dict>
</plist>
EOF

for label in com.linustalacko.linuswise.kindlesync com.linustalacko.linuswise.daily; do
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
done
launchctl bootstrap "gui/$UID_NUM" "$kindle_plist"
launchctl bootstrap "gui/$UID_NUM" "$daily_plist"

echo "Installed:"
echo "  $kindle_plist  (on volume mount)"
echo "  $daily_plist   (daily at ${HOUR}:$(printf '%02d' "$MINUTE"))"
echo "Logs: ~/.local/share/linuswise/agent.log"
