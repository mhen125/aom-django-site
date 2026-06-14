import json
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from stats.importers import backfill_replay_parses
from stats.replay_filters import build_started_after
from stats.replay_acquisition import backfill_replay_sources
from stats.replay_parser import parse_replay_queue_batch


class Command(BaseCommand):
    help = "Run the replay pipeline: backfill queue rows, resolve replay sources, and parse a batch."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10, help="How many replay rows to parse per run.")
        parser.add_argument("--match-id", action="append", default=[], help="Target one or more specific match ids.")
        parser.add_argument(
            "--match-type",
            action="append",
            default=[],
            help="Only consider one or more specific match_type_id values. Repeat the flag to include multiple ids.",
        )
        parser.add_argument("--ranked-only", action="store_true", help="Only consider ranked matches for backfill/source resolution.")
        parser.add_argument(
            "--1v1-only",
            action="store_true",
            dest="one_v_one_only",
            help="Only consider non-team matches with exactly two participants.",
        )
        parser.add_argument(
            "--include-no-replay-flag",
            action="store_true",
            help="Also consider matches not currently marked replay_available.",
        )
        parser.add_argument("--since-days", type=int, default=0, help="Only consider matches started within the last N days.")
        parser.add_argument(
            "--started-after",
            help="Only consider matches started at or after this ISO datetime, for example 2026-06-01T00:00:00+00:00.",
        )
        parser.add_argument(
            "--missing-url-only",
            action="store_true",
            help="Only backfill replay sources for matches that do not already have a replay URL.",
        )
        parser.add_argument(
            "--supported-build",
            action="append",
            default=[],
            help="Only parse replays from one or more known supported build numbers. Repeat the flag to include multiple builds.",
        )
        parser.add_argument(
            "--skip-unknown-builds",
            action="store_true",
            help="Do not parse replays when the build is unknown.",
        )
        parser.add_argument(
            "--live-history",
            action="store_true",
            help="Resolve replay blob URLs from GetRecentMatchHistory before falling back to GetMatchReplay.",
        )
        parser.add_argument(
            "--refresh-live-history",
            action="store_true",
            help="Bypass cached recent match history lookups.",
        )
        parser.add_argument(
            "--no-api-fallback",
            action="store_true",
            help="Disable GetMatchReplay fallback resolution.",
        )
        parser.add_argument("--loop", action="store_true", help="Run continuously on a polling interval.")
        parser.add_argument(
            "--poll-seconds",
            type=int,
            default=10,
            help="Polling interval for --loop mode. Recommended minimum is 5 seconds.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen without changing data.")
        parser.add_argument("--json", action="store_true", help="Emit summaries as JSON.")

    def handle(self, *args, **options):
        poll_seconds = max(1, int(options["poll_seconds"] or 10))
        if options["loop"] and poll_seconds < 5:
            raise CommandError("Loop mode should poll no faster than every 5 seconds.")

        run_index = 0
        while True:
            run_index += 1
            summary = self._run_once(options)
            if options["json"]:
                self.stdout.write(json.dumps({"run": run_index, **summary}, indent=2, sort_keys=True))
            else:
                queue = summary["queue_backfill"]
                sources = summary["source_backfill"]
                parse = summary["parse_batch"]
                self.stdout.write(
                    self.style.SUCCESS(
                        (
                            f"Replay pipeline run {run_index}: "
                            f"queue created {queue['rows_created']}, "
                            f"sources attached {sources['rows_url_attached']}, "
                            f"parsed {parse['parsed_count']}, "
                            f"failed {parse['failed_count']}, "
                            f"skipped {parse.get('skipped_count', 0)}."
                        )
                    )
                )

            if not options["loop"]:
                break

            time.sleep(poll_seconds)

    def _run_once(self, options):
        match_ids = options["match_id"] or None
        ranked_only = bool(options["ranked_only"])
        replay_available_only = not bool(options["include_no_replay_flag"])
        match_type_ids = [int(value) for value in (options["match_type"] or [])]
        one_v_one_only = bool(options["one_v_one_only"])
        started_after = self._parse_started_after(options.get("started_after"), options.get("since_days"))
        supported_build_values = [str(value).strip() for value in (options["supported_build"] or []) if str(value).strip()]
        supported_builds = supported_build_values or None
        allow_unknown_builds = None if not options["skip_unknown_builds"] else False
        dry_run = bool(options["dry_run"])

        queue_backfill = backfill_replay_parses(
            match_ids=match_ids,
            ranked_only=ranked_only,
            replay_available_only=replay_available_only,
            match_type_ids=match_type_ids,
            one_v_one_only=one_v_one_only,
            started_after=started_after,
            dry_run=dry_run,
        )
        source_backfill = backfill_replay_sources(
            match_ids=match_ids,
            ranked_only=ranked_only,
            replay_available_only=replay_available_only,
            match_type_ids=match_type_ids,
            one_v_one_only=one_v_one_only,
            started_after=started_after,
            missing_replay_url_only=bool(options["missing_url_only"]),
            live_recent_history=bool(options["live_history"]),
            refresh_live_history=bool(options["refresh_live_history"]),
            allow_api_fallback=not bool(options["no_api_fallback"]),
            dry_run=dry_run,
        )
        parse_batch = (
            {
                "ok": True,
                "requested_rows": 0,
                "parsed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "events": [],
                "skipped": True,
            }
            if dry_run
            else parse_replay_queue_batch(
                limit=max(1, int(options["limit"] or 10)),
                match_id=(match_ids[0] if match_ids and len(match_ids) == 1 else ""),
                ranked_only=ranked_only,
                replay_available_only=replay_available_only,
                match_type_ids=match_type_ids,
                one_v_one_only=one_v_one_only,
                started_after=started_after,
                supported_builds=supported_builds,
                allow_unknown_builds=allow_unknown_builds,
                resolve_live_history=bool(options["live_history"]),
                refresh_live_history=bool(options["refresh_live_history"]),
            )
        )

        return {
            "ok": True,
            "queue_backfill": queue_backfill,
            "source_backfill": source_backfill,
            "parse_batch": parse_batch,
        }

    def _parse_started_after(self, started_after_raw, since_days_raw):
        if started_after_raw:
            parsed = parse_datetime(str(started_after_raw).strip())
            if parsed is None:
                raise CommandError("Invalid --started-after value. Use an ISO datetime.")
            return build_started_after(started_after=parsed)
        if since_days_raw:
            return build_started_after(since_days=int(since_days_raw))
        return None
