import json

from django.core.management.base import BaseCommand

from stats.importers import backfill_player_personal_stats


class Command(BaseCommand):
    help = "Hydrate existing imported Player rows with persisted GetPersonalStat queue ratings."

    def add_arguments(self, parser):
        parser.add_argument("--match-type", type=int, default=1, help="Queue/match type to prioritize while hydrating ratings.")
        parser.add_argument("--limit", type=int, default=0, help="Optional cap on the number of players to scan.")
        parser.add_argument(
            "--profile-id",
            action="append",
            default=[],
            help="Target one or more specific AoM profile ids. Repeat the flag to include multiple ids.",
        )
        parser.add_argument("--ranked-only", action="store_true", help="Only consider players seen in ranked imported matches.")
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Skip players that already have a persisted rating for the requested queue.",
        )
        parser.add_argument("--refresh", action="store_true", help="Bypass helper caches when hydrating.")
        parser.add_argument("--dry-run", action="store_true", help="Fetch and report hydration candidates without writing rows.")
        parser.add_argument("--json", action="store_true", help="Emit the summary as JSON.")

    def handle(self, *args, **options):
        summary = backfill_player_personal_stats(
            match_type=options["match_type"],
            profile_ids=[int(value) for value in options["profile_id"] if str(value).strip()] or None,
            limit=options["limit"] or None,
            ranked_only=bool(options["ranked_only"]),
            missing_only=bool(options["missing_only"]),
            refresh=bool(options["refresh"]),
            dry_run=bool(options["dry_run"]),
        )

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
            return

        verb = "Would hydrate" if summary["dry_run"] else "Hydrated"
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"{verb} {summary['players_scanned']} player row(s) for {summary['match_type_label']}: "
                    f"{summary['rows_updated']} updated, "
                    f"{summary['rows_unchanged']} unchanged, "
                    f"{summary['rows_skipped']} skipped, "
                    f"{summary['rows_failed']} failed."
                )
            )
        )

        if options["verbosity"] >= 2:
            self.stdout.write("Events:")
            for event in summary.get("events", []):
                self.stdout.write(f"  - {json.dumps(event, sort_keys=True)}")
