from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from stats.replay_parser import ReplayParserError, parse_replay_queue_batch


class Command(BaseCommand):
    help = "Parse pending replay rows with the configured restoration binary and store extracted summaries."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25, help="Maximum number of pending replay rows to process.")
        parser.add_argument("--match-id", default="", help="Optional external match id to process exactly one replay row.")
        parser.add_argument("--replay-file", default="", help="Optional local replay file path for a single targeted parse.")
        parser.add_argument(
            "--resolve-live-history",
            action="store_true",
            help="Try resolving replay blob URLs from the recent match history community API when a row has no replay_url yet.",
        )
        parser.add_argument(
            "--refresh-live-history",
            action="store_true",
            help="Bypass cached recent match history lookups when resolving replay sources.",
        )

    def handle(self, *args, **options):
        try:
            summary = parse_replay_queue_batch(
                limit=max(1, int(options["limit"] or 25)),
                match_id=(options["match_id"] or "").strip(),
                replay_file_path=(options["replay_file"] or "").strip() or None,
                resolve_live_history=bool(options["resolve_live_history"]),
                refresh_live_history=bool(options["refresh_live_history"]),
            )
        except ReplayParserError as error:
            raise CommandError(str(error))

        if not summary["requested_rows"]:
            self.stdout.write("No replay rows matched the requested selection.")
            return

        for event in summary["events"]:
            if event.get("ok"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Parsed {event['match_id']} with parser version {event.get('parser_version') or 'unknown'}."
                    )
                )
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed {event['match_id']}: {event.get('error') or 'unknown error'}"
                    )
                )

        self.stdout.write(
            f"Replay parsing complete. Parsed: {summary['parsed_count']} | Failed: {summary['failed_count']} | Requested: {summary['requested_rows']}"
        )
