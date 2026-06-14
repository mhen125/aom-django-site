# Match Importer on VPS

This document adds the missing ingest half of the Prostagma stats pipeline: regularly importing fresh ranked matches so the replay worker has new rows to process.

## What This Sets Up

- a repo-owned wrapper script at `scripts/run_match_importer.sh`
- a `systemd` oneshot service for importing recent matches
- a `systemd` timer that runs the importer every 5 minutes

This pairs with the replay worker documented in `docs/REPLAY_WORKER_SYSTEMD.md`.

## 1. Make the Script Executable

From the deployed repo:

```bash
cd /srv/prostagma/current
chmod +x scripts/run_match_importer.sh
```

If your real deploy path differs, use that path instead.

## 2. Add Importer Settings to `.env`

Recommended starting values:

```env
PROSTAGMA_IMPORT_MATCH_TYPE=1
PROSTAGMA_IMPORT_LEADERBOARD_PAGES=1
PROSTAGMA_IMPORT_LEADERBOARD_COUNT=25
PROSTAGMA_IMPORT_PLAYER_LIMIT=10
PROSTAGMA_IMPORT_RECENT_COUNT=5
PROSTAGMA_IMPORT_TRANSPORT=curl
PROSTAGMA_IMPORT_REFRESH=0
```

Notes:

- `MATCH_TYPE=1` keeps this focused on ranked 1v1 Supremacy.
- `PLAYER_LIMIT=10` is a conservative first production value.
- `RECENT_COUNT=5` means each seeded player contributes up to 5 recent matches per run.

## 3. Install the `systemd` Files

```bash
sudo cp config_snippets/prostagma-match-import.service /etc/systemd/system/
sudo cp config_snippets/prostagma-match-import.timer /etc/systemd/system/
```

Then edit the service file if needed:

```bash
sudo nano /etc/systemd/system/prostagma-match-import.service
```

Values to verify:

- `User`
- `Group`
- `WorkingDirectory`
- `EnvironmentFile`
- `ExecStart`

## 4. Reload and Enable

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now prostagma-match-import.timer
```

You can also trigger one run immediately:

```bash
sudo systemctl start prostagma-match-import.service
```

## 5. Verify

Check the timer:

```bash
sudo systemctl status prostagma-match-import.timer
sudo systemctl list-timers --all | grep prostagma-match-import
```

Check importer logs:

```bash
journalctl -u prostagma-match-import.service -n 50 --no-pager
```

Then inspect the queue:

```bash
python manage.py report_replay_queue --json
```

## Default Importer Behavior

The wrapper script currently runs:

```bash
python manage.py import_recent_matches \
  --match-type 1 \
  --leaderboard-pages 1 \
  --leaderboard-count 25 \
  --recent-count 5 \
  --player-limit 10 \
  --transport curl
```

## Recommended First Production Flow

Run both:

- `prostagma-match-import.timer`
- `prostagma-replay-worker.service`

That gives you:

1. scheduled import of fresh ranked matches
2. continuous replay acquisition and parsing

## If the Importer Fails

Check these first:

- `python manage.py check`
- outbound API access from the VPS
- database connectivity
- `journalctl -u prostagma-match-import.service -n 100 --no-pager`

## Suggested Next Improvement

Once importer + parser are stable together, the next useful ops layer is generating:

- aggregate snapshots
- public meta claims

on a schedule as well.
