# Replay Worker on VPS

This document shows one clean way to run the Prostagma replay pipeline continuously on an Ubuntu VPS with `systemd`.

## What This Sets Up

- a repo-owned wrapper script at `scripts/run_replay_worker.sh`
- a `systemd` service for the replay worker
- a simple boot timer so the worker starts automatically after reboot

The worker runs the conservative replay pipeline we already built:

- ranked only
- `match_type_id=1` by default
- 1v1 only
- recent matches only
- replay URL backfill enabled
- live recent-history replay lookup enabled
- optional supported-build gating

## 1. Confirm the Project Layout

These snippets assume the deployed app lives here:

```text
/srv/prostagma/current
```

If your VPS uses a different path, update the `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` values in the service file.

## 2. Make the Worker Script Executable

From the deployed repo:

```bash
cd /srv/prostagma/current
chmod +x scripts/run_replay_worker.sh
```

## 3. Add Replay Worker Settings to `.env`

At minimum:

```env
RESTORATION_BINARY_PATH=/absolute/path/to/restoration-linux-amd64
REPLAY_SUPPORTED_BUILDS=602822
REPLAY_ALLOW_UNKNOWN_BUILDS=true
```

Optional worker-specific overrides:

```env
PROSTAGMA_REPLAY_MATCH_TYPE=1
PROSTAGMA_REPLAY_SINCE_DAYS=7
PROSTAGMA_REPLAY_LIMIT=10
PROSTAGMA_REPLAY_POLL_SECONDS=300
PROSTAGMA_REPLAY_SKIP_UNKNOWN_BUILDS=0
PROSTAGMA_REPLAY_SUPPORTED_BUILDS=602822
```

Notes:

- `PROSTAGMA_REPLAY_SUPPORTED_BUILDS` overrides `REPLAY_SUPPORTED_BUILDS` for the worker script.
- `PROSTAGMA_REPLAY_SKIP_UNKNOWN_BUILDS=1` is stricter. I would leave this off at first.
- `300` seconds means the loop wakes every 5 minutes.

## 4. Install the `systemd` Files

Copy the templates:

```bash
sudo cp config_snippets/prostagma-replay-worker.service /etc/systemd/system/
sudo cp config_snippets/prostagma-replay-worker.timer /etc/systemd/system/
```

If your VPS user or deploy path is not `mark` and `/srv/prostagma/current`, edit the service file first:

```bash
sudo nano /etc/systemd/system/prostagma-replay-worker.service
```

Values to verify:

- `User`
- `Group`
- `WorkingDirectory`
- `EnvironmentFile`
- `ExecStart`

## 5. Reload and Enable

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now prostagma-replay-worker.service
```

The timer file is included mainly as a boot-start companion. Because the worker itself runs in loop mode, the service is the important piece.

If you want the timer enabled too:

```bash
sudo systemctl enable --now prostagma-replay-worker.timer
```

## 6. Verify the Worker

Check status:

```bash
sudo systemctl status prostagma-replay-worker.service
```

Follow logs:

```bash
journalctl -u prostagma-replay-worker.service -f
```

You should see replay pipeline summaries such as created queue rows, attached sources, parsed rows, failed rows, and skipped rows.

## 7. Helpful Manual Commands

Dry run:

```bash
python manage.py run_replay_pipeline --dry-run --json --ranked-only --match-type 1 --1v1-only --since-days 7
```

Queue report:

```bash
python manage.py report_replay_queue --json
```

## Default Worker Behavior

The wrapper script currently runs:

```bash
python manage.py run_replay_pipeline \
  --ranked-only \
  --match-type 1 \
  --1v1-only \
  --since-days 7 \
  --missing-url-only \
  --live-history \
  --limit 10 \
  --loop \
  --poll-seconds 300
```

It also adds `--supported-build ...` flags if supported builds are configured.

## Recommended First Production Settings

Start conservative:

```env
PROSTAGMA_REPLAY_SINCE_DAYS=7
PROSTAGMA_REPLAY_LIMIT=10
PROSTAGMA_REPLAY_POLL_SECONDS=300
REPLAY_SUPPORTED_BUILDS=602822
REPLAY_ALLOW_UNKNOWN_BUILDS=true
PROSTAGMA_REPLAY_SKIP_UNKNOWN_BUILDS=0
```

Then watch:

- how many rows parse successfully
- how many rows fall back from blob URLs to `GetMatchReplay`
- how many rows are skipped due to unsupported builds
- whether current-patch replays keep parsing cleanly after game updates

## When the Game Patches

After an AoM patch:

1. update `REPLAY_SUPPORTED_BUILDS`
2. confirm the `restoration` binary still parses current replays
3. restart the worker

```bash
sudo systemctl restart prostagma-replay-worker.service
```

## If the Service Fails Immediately

Check these first:

- `.env` exists and is readable
- the virtualenv exists at `.venv/`
- `python manage.py check` works in the deploy directory
- `RESTORATION_BINARY_PATH` points to a real executable
- the service user has permission to run the parser binary

## Pair It With The Importer

To keep the worker fed automatically, pair this with the scheduled importer documented in:

- `docs/MATCH_IMPORTER_SYSTEMD.md`
