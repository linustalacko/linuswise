# Automation (launchd)

Two agents run this for you, locally, with no cron daemon:

| Agent | Trigger | Does |
|-------|---------|------|
| `com.linustalacko.linuswise.kindlesync` | any volume mounts (`WatchPaths` on `/Volumes`) | runs `ingest-kindle` — no-ops unless the mounted volume is a Kindle |
| `com.linustalacko.linuswise.daily` | every morning (`StartCalendarInterval`) | runs `ingest-pdf` on the inbox, then `daily` to send the email |

## Install

```bash
./scripts/install-launchd.sh              # daily email at 11:00
HOUR=7 MINUTE=30 ./scripts/install-launchd.sh   # custom time
```

This writes the plists into `~/Library/LaunchAgents/` and loads them. Re-run it
any time to change the schedule.

## Requirements for the daily email to actually send

- Set `method = "smtp"` in your config (the `file` method tries to open a
  browser, which is fine when you run `linuswise daily` by hand but not from an
  agent).
- Provide the SMTP password. Either put `smtp_password` in the config, or create
  `~/.config/linuswise/secrets.env` with:

  ```sh
  export LINUSWISE_SMTP_PASSWORD="your-gmail-app-password"
  ```

  `run-daily.sh` sources that file if present.

## Inspect / remove

```bash
launchctl list | grep linuswise
tail -f ~/.local/share/linuswise/agent.log

launchctl bootout gui/$(id -u)/com.linustalacko.linuswise.daily
launchctl bootout gui/$(id -u)/com.linustalacko.linuswise.kindlesync
```

> Note: the kindle-sync agent fires on every volume mount and runs a quick
> no-op when it isn't a Kindle. That's intentional — there's no event for "a
> Kindle specifically was plugged in," so we watch all mounts and let the
> ingest command decide.
