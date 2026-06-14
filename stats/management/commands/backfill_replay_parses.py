import json

from django.core.management.base import BaseCommand

from stats.importers import backfill_replay_parses


class Command(BaseCommand):
    help = "Create or sync ReplayParse rows for already-imported Match rows."

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
            help="Also scan matches that are not marked replay_available yet.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Report what would be backfilled without writing rows.")
        parser.add_argument("--json", action="store_true", help="Emit the summary as JSON.")

    def handle(self, *args, **options):
        summary = backfill_replay_parses(
            match_ids=options["match_id"] or None,
            limit=options["limit"] or None,
            ranked_only=bool(options["ranked_only"]),
            replay_available_only=not bool(options["include_no_replay_flag"]),
            dry_run=bool(options["dry_run"]),
        )

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
            return

        verb = "Would backfill" if summary["dry_run"] else "Backfilled"
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"{verb} replay rows for {summary['matches_scanned']} match(es): "
                    f"{summary['rows_created']} created, "
                    f"{summary['rows_updated']} updated, "
                    f"{summary['rows_unchanged']} unchanged."
                )
            )
        )

        if options["verbosity"] >= 2:
            self.stdout.write("Events:")
            for event in summary.get("events", []):
                self.stdout.write(f"  - {json.dumps(event, sort_keys=True)}")
