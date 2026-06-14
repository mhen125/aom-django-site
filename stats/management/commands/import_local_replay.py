from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from stats.replay_parser import (
    enrich_replay_parse_from_json,
    parse_replay_file,
    upsert_match_from_parsed_replay,
)


class Command(BaseCommand):
    help = "Import one local .mythrec or .mythrec.gz into stats tables and parse it with restoration."

    def add_arguments(self, parser):
        parser.add_argument("replay_file", help="Absolute or relative path to the local replay file.")
        parser.add_argument(
            "--match-id",
            default="",
            help="Optional explicit external match id. Defaults to local-<filename-without-extension>.",
        )

    def handle(self, *args, **options):
        replay_file = Path(options["replay_file"]).expanduser().resolve()
        if not replay_file.exists():
            raise CommandError(f"Replay file does not exist: {replay_file}")

        match_id = (options["match_id"] or "").strip()
        if not match_id:
            stem = replay_file.name
            if stem.endswith(".mythrec.gz"):
                stem = stem[: -len(".mythrec.gz")]
            elif replay_file.suffix:
                stem = replay_file.stem
            match_id = f"local-{stem}"

        parsed_json, parser_binary, replay_sha256 = parse_replay_file(replay_file)
        replay_parse = upsert_match_from_parsed_replay(
            parsed_json=parsed_json,
            replay_file_path=replay_file,
            external_match_id=match_id,
        )
        enrich_replay_parse_from_json(
            replay_parse,
            parsed_json=parsed_json,
            parser_binary=parser_binary,
            replay_sha256=replay_sha256,
        )
        replay_parse.refresh_from_db()

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {replay_file.name} as {replay_parse.match.external_match_id}."
            )
        )
        self.stdout.write(
            f"Map: {replay_parse.match.map_name} | Players: {replay_parse.player_summaries.count()} | "
            f"Parser version: {replay_parse.parser_version or 'unknown'}"
        )
