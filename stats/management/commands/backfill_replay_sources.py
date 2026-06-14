import json

from django.core.management.base import BaseCommand

from stats.replay_acquisition import backfill_replay_sources


class Command(BaseCommand):
    help = "Attach replay download URLs to imported matches and ReplayParse rows using the configured acquisition template."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Optional cap on the number of matches to scan.")
        parser.add_argument(
            "--match-id",
            action="append",
            default=[],
            help="Target one or more specific external match ids. Repeat the flag to include multiple ids.",
        )
        parser.add_argument("--ranked-only", action="store_true", help="Only consider ranked matches.")
        parser.add_argument(
            "--include-no-replay-flag",
            action="store_true",
            help="Also scan matches not currently marked replay_available.",
        )
        parser.add_argument(
            "--live-history",
            action="store_true",
            help="Try resolving replay blob URLs from the recent match history community API.",
        )
        parser.add_argument(
            "--refresh-live-history",
            action="store_true",
            help="Bypass cached recent match history lookups while resolving replay sources.",
        )
        parser.add_argument(
            "--no-api-fallback",
            action="store_true",
            help="Disable fallback URL construction via the api.ageofempires.com GetMatchReplay endpoint.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Report what would be attached without writing rows.")
        parser.add_argument("--json", action="store_true", help="Emit the summary as JSON.")

    def handle(self, *args, **options):
        summary = backfill_replay_sources(
            match_ids=options["match_id"] or None,
            limit=options["limit"] or None,
            ranked_only=bool(options["ranked_only"]),
            replay_available_only=not bool(options["include_no_replay_flag"]),
            live_recent_history=bool(options["live_history"]),
            refresh_live_history=bool(options["refresh_live_history"]),
            allow_api_fallback=not bool(options["no_api_fallback"]),
            dry_run=bool(options["dry_run"]),
        )

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
            return

        verb = "Would attach" if summary["dry_run"] else "Attached"
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"{verb} replay sources for {summary['matches_scanned']} match(es): "
                    f"{summary['rows_url_attached']} attached, "
                    f"{summary['rows_url_unchanged']} unchanged, "
                    f"{summary['rows_missing_template']} missing template/url."
                )
            )
        )

        if options["verbosity"] >= 2:
            self.stdout.write("Events:")
            for event in summary.get("events", []):
                self.stdout.write(f"  - {json.dumps(event, sort_keys=True)}")
