import json

from django.core.management.base import BaseCommand

from stats.importers import import_recent_matches


class Command(BaseCommand):
    help = "Import recent ranked matches into the stats app from the existing live leaderboard/match APIs."

    def add_arguments(self, parser):
        parser.add_argument("--match-type", type=int, default=1, help="Ranked match type id to seed from.")
        parser.add_argument("--leaderboard-pages", type=int, default=1, help="How many leaderboard pages to import.")
        parser.add_argument("--leaderboard-count", type=int, default=25, help="Rows per leaderboard page.")
        parser.add_argument("--player-limit", type=int, default=0, help="Optional cap on imported leaderboard players.")
        parser.add_argument("--recent-count", type=int, default=10, help="How many recent matches to inspect per player.")
        parser.add_argument("--profile-id", type=int, default=0, help="Seed import from one known AoM profile_id instead of the leaderboard.")
        parser.add_argument("--player", default="", help="Optional player alias paired with --profile-id.")
        parser.add_argument("--transport", default="curl", help="Transport passed to upstream fetch helpers.")
        parser.add_argument("--dry-run", action="store_true", help="Fetch and normalize import candidates without writing stats rows.")
        parser.add_argument("--refresh", action="store_true", help="Bypass helper caches when importing.")
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit the final import summary as JSON.",
        )

    def handle(self, *args, **options):
        summary = import_recent_matches(
            match_type=options["match_type"],
            leaderboard_pages=max(1, options["leaderboard_pages"]),
            leaderboard_count=max(1, options["leaderboard_count"]),
            player_limit=options["player_limit"] or None,
            recent_count=max(1, options["recent_count"]),
            seed_profile_id=options["profile_id"] or None,
            seed_player=options["player"] or "",
            dry_run=bool(options["dry_run"]),
            refresh=bool(options["refresh"]),
            transport=options["transport"] or "curl",
        )

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
            return

        summary_verb = "Planned" if summary["dry_run"] else "Imported"
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"{summary_verb} {summary['matches_persisted']} match(es), "
                    f"{summary['participants_persisted']} participant row(s), "
                    f"and touched {summary['players_persisted']} player row(s) "
                    f"for {summary['match_type_label']}."
                )
            )
        )
        self.stdout.write(
            f"Seed mode: {summary['seed_mode']} | Dry run: {summary['dry_run']} | Players seen: {summary['players_seen']} | "
            f"Matches seen: {summary['matches_seen']} | Match-list failures: {summary['match_list_failures']} | "
            f"Detail failures: {summary['detail_failures']} | "
            f"Leaderboard failures: {summary['leaderboard_failures']}"
        )

        if options["verbosity"] >= 2:
            self.stdout.write("Events:")
            for event in summary.get("events", []):
                self.stdout.write(f"  - {json.dumps(event, sort_keys=True)}")
