from io import StringIO
import io
import os
from unittest.mock import patch
import zipfile

from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from stats.importers import _upsert_match_with_participants, backfill_replay_parses
from stats.models import Match, MatchParticipant, ReplayParse
from stats.replay_acquisition import (
    backfill_replay_sources,
    extract_replay_url_from_match_payload,
    fetch_recent_history_replay_url,
    resolve_api_match_replay_url,
    resolve_replay_download_url,
)
from stats.replay_parser import (
    ReplayArtifact,
    _download_replay_to_temp,
    enrich_replay_parse_from_json,
    parse_replay_queue_batch,
    process_replay_parse,
)


class StatsViewTests(TestCase):
    def test_meta_dashboard_route_loads(self):
        response = self.client.get(reverse("stats:meta_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_replay_discovery_route_loads(self):
        response = self.client.get(reverse("stats:replay_discovery"))
        self.assertEqual(response.status_code, 200)

    def test_replay_discovery_route_renders_parsed_replay_data(self):
        match = Match.objects.create(
            external_match_id="parsed-view-1",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="file:///tmp/demo.mythrec",
            map_name="Watering Hole",
            patch_label="601891",
            raw_payload={},
        )
        replay_parse = ReplayParse.objects.create(
            match=match,
            status=ReplayParse.STATUS_PARSED,
            replay_url="file:///tmp/demo.mythrec",
            parser_version="v0.5.4",
            extracted_facts={"build_number": 601891, "game_length_secs": 1000},
        )
        detail_match = {
            "match_type": 1,
            "match_type_label": "1v1 Supremacy",
            "map": "Watering Hole",
            "date_time": "2026-06-01T12:00:00",
            "players": [
                {
                    "profile_id": 101,
                    "name": "Alpha",
                    "team": 1,
                    "slot": 1,
                    "result": "win",
                    "god": "Oranos",
                    "elo": 1200,
                    "match_replay_available": True,
                },
                {
                    "profile_id": 102,
                    "name": "Beta",
                    "team": 2,
                    "slot": 1,
                    "result": "loss",
                    "god": "Amaterasu",
                    "elo": 1188,
                    "match_replay_available": True,
                },
            ],
        }
        _upsert_match_with_participants(
            external_match_id="parsed-view-1",
            requested_match_type=1,
            match_row={"match_id": "parsed-view-1", "map": "Watering Hole", "date_time": "2026-06-01T12:00:00"},
            detail_match=detail_match,
            detail_raw={"replayUrl": "file:///tmp/demo.mythrec"},
            dry_run=False,
        )
        parsed_json = {
            "MapName": "watering_hole",
            "BuildNumber": 601891,
            "ParserVersion": "v0.5.4",
            "GameLengthSecs": 1000,
            "WinningTeam": 0,
            "Players": [
                {"PlayerNum": 1, "TeamId": 0, "Name": "Alpha", "ProfileId": 101, "God": "Oranos", "Winner": True, "EAPM": 75},
                {"PlayerNum": 2, "TeamId": 1, "Name": "Beta", "ProfileId": 102, "God": "Amaterasu", "Winner": False, "EAPM": 60},
            ],
            "Stats": {
                "1": {"UnitCounts": {"Contarius": 20}, "Timelines": {"UnitCounts": [{"Contarius": 2}], "BuildingCounts": [], "TechsPrequeued": [{"Name": "HeroicAgeHyperion", "GameTimeSecs": 500}]}},
                "2": {"UnitCounts": {"YumiArcher": 15}, "Timelines": {"UnitCounts": [{"YumiArcher": 2}], "BuildingCounts": [], "TechsPrequeued": [{"Name": "HeroicAgeTsukuyomi", "GameTimeSecs": 590}]}}
            },
        }
        enrich_replay_parse_from_json(replay_parse, parsed_json=parsed_json, parser_binary="/tmp/restoration", replay_sha256="view123")

        response = self.client.get(reverse("stats:replay_discovery"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "parsed-view-1")
        self.assertContains(response, "Fast Heroic")

    def test_player_profile_route_loads(self):
        response = self.client.get(reverse("stats:player_profile", args=[1075470702]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1075470702")


class StatsImporterTests(TestCase):
    def test_importer_seeds_replay_parse_without_overwriting_existing_parse(self):
        detail_match = {
            "match_type": 1,
            "match_type_label": "1v1 Supremacy",
            "map": "Ghost Lake",
            "date_time": "2026-06-01T12:00:00",
            "replay_url": "https://example.com/replays/123.gz",
            "players": [
                {
                    "profile_id": 11,
                    "name": "Alpha",
                    "team": 1,
                    "slot": 1,
                    "result": "win",
                    "god": "Zeus",
                    "elo": 1200,
                    "match_replay_available": True,
                },
                {
                    "profile_id": 12,
                    "name": "Beta",
                    "team": 2,
                    "slot": 1,
                    "result": "loss",
                    "god": "Ra",
                    "elo": 1188,
                    "match_replay_available": True,
                },
            ],
        }
        match_row = {
            "match_id": "abc-123",
            "map": "Ghost Lake",
            "date_time": "2026-06-01T12:00:00",
        }
        detail_raw = {
            "replayUrl": "https://example.com/replays/123.gz",
        }

        match, participant_count = _upsert_match_with_participants(
            external_match_id="abc-123",
            requested_match_type=1,
            match_row=match_row,
            detail_match=detail_match,
            detail_raw=detail_raw,
            dry_run=False,
        )

        self.assertIsNotNone(match)
        self.assertEqual(participant_count, 2)
        self.assertEqual(Match.objects.count(), 1)

        replay_parse = ReplayParse.objects.get(match=match)
        self.assertEqual(replay_parse.status, ReplayParse.STATUS_PENDING)
        self.assertEqual(replay_parse.replay_url, "https://example.com/replays/123.gz")
        self.assertEqual(replay_parse.extracted_facts.get("replay_available"), True)

        replay_parse.status = ReplayParse.STATUS_PARSED
        replay_parse.parsed_json = {"ok": True}
        replay_parse.save(update_fields=["status", "parsed_json", "updated_at"])

        _upsert_match_with_participants(
            external_match_id="abc-123",
            requested_match_type=1,
            match_row=match_row,
            detail_match=detail_match,
            detail_raw=detail_raw,
            dry_run=False,
        )

        replay_parse.refresh_from_db()
        self.assertEqual(replay_parse.status, ReplayParse.STATUS_PARSED)
        self.assertEqual(replay_parse.parsed_json, {"ok": True})

    def test_importer_retries_once_after_mysql_disconnect(self):
        detail_match = {
            "match_type": 1,
            "match_type_label": "1v1 Supremacy",
            "map": "Ghost Lake",
            "date_time": "2026-06-01T12:00:00",
            "players": [
                {
                    "profile_id": 11,
                    "name": "Alpha",
                    "team": 1,
                    "slot": 1,
                    "result": "win",
                    "god": "Zeus",
                    "elo": 1200,
                    "match_replay_available": True,
                }
            ],
        }
        match_row = {
            "match_id": "retry-1",
            "map": "Ghost Lake",
            "date_time": "2026-06-01T12:00:00",
        }

        original_update_or_create = Match.objects.update_or_create
        call_counter = {"count": 0}

        def flaky_update_or_create(*args, **kwargs):
            call_counter["count"] += 1
            if call_counter["count"] == 1:
                raise OperationalError("MySQL server has gone away (SSLEOFError)")
            return original_update_or_create(*args, **kwargs)

        with patch("stats.importers.Match.objects.update_or_create", side_effect=flaky_update_or_create):
            match, participant_count = _upsert_match_with_participants(
                external_match_id="retry-1",
                requested_match_type=1,
                match_row=match_row,
                detail_match=detail_match,
                detail_raw={},
                dry_run=False,
            )

        self.assertIsNotNone(match)
        self.assertEqual(participant_count, 1)
        self.assertEqual(call_counter["count"], 2)

    def test_backfill_replay_parses_creates_missing_rows_for_existing_matches(self):
        match = Match.objects.create(
            external_match_id="legacy-1",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Midgard",
            raw_payload={"playerList": [{"matchReplayAvailable": True}]},
        )
        self.assertFalse(ReplayParse.objects.filter(match=match).exists())

        summary = backfill_replay_parses()

        self.assertEqual(summary["rows_created"], 1)
        replay_parse = ReplayParse.objects.get(match=match)
        self.assertEqual(replay_parse.status, ReplayParse.STATUS_PENDING)
        self.assertEqual(replay_parse.extracted_facts.get("replay_available"), True)

    def test_backfill_command_dry_run_reports_without_writing(self):
        Match.objects.create(
            external_match_id="legacy-2",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Ghost Lake",
            raw_payload={},
        )

        out = StringIO()
        call_command("backfill_replay_parses", "--dry-run", stdout=out)

        self.assertIn("Would backfill replay rows", out.getvalue())
        self.assertEqual(ReplayParse.objects.count(), 0)

    def test_run_replay_pipeline_dry_run_reports_summary(self):
        Match.objects.create(
            external_match_id="pipeline-1",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Ghost Lake",
            raw_payload={},
        )

        out = StringIO()
        call_command("run_replay_pipeline", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("Replay pipeline run 1", output)
        self.assertIn("queue created", output)

    def test_run_replay_pipeline_json_respects_recent_1v1_filters(self):
        recent_match = Match.objects.create(
            external_match_id="pipeline-recent",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            is_team_game=False,
            replay_available=True,
            started_at=timezone.now(),
            replay_url="file:///tmp/recent.mythrec.gz",
            map_name="Ghost Lake",
            raw_payload={},
        )
        team_match = Match.objects.create(
            external_match_id="pipeline-team",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=2,
            match_type_label="Team Supremacy",
            is_ranked=True,
            is_team_game=True,
            replay_available=True,
            started_at=timezone.now(),
            replay_url="file:///tmp/team.mythrec.gz",
            map_name="Midgard",
            raw_payload={},
        )
        MatchParticipant.objects.create(match=recent_match, profile_id=11, alias="A", team=1, slot=1, civilization="Zeus")
        MatchParticipant.objects.create(match=recent_match, profile_id=12, alias="B", team=2, slot=1, civilization="Ra")
        MatchParticipant.objects.create(match=team_match, profile_id=21, alias="C", team=1, slot=1, civilization="Loki")
        MatchParticipant.objects.create(match=team_match, profile_id=22, alias="D", team=1, slot=2, civilization="Isis")
        MatchParticipant.objects.create(match=team_match, profile_id=23, alias="E", team=2, slot=1, civilization="Gaia")
        MatchParticipant.objects.create(match=team_match, profile_id=24, alias="F", team=2, slot=2, civilization="Thor")
        ReplayParse.objects.create(
            match=recent_match,
            status=ReplayParse.STATUS_PENDING,
            replay_url=recent_match.replay_url,
            extracted_facts={"replay_available": True},
        )
        ReplayParse.objects.create(
            match=team_match,
            status=ReplayParse.STATUS_PENDING,
            replay_url=team_match.replay_url,
            extracted_facts={"replay_available": True},
        )

        out = StringIO()
        call_command(
            "run_replay_pipeline",
            "--dry-run",
            "--json",
            "--ranked-only",
            "--match-type",
            "1",
            "--1v1-only",
            "--since-days",
            "1",
            stdout=out,
        )

        payload = out.getvalue()
        self.assertIn('"matches_scanned": 1', payload)
        self.assertIn('"rows_created": 0', payload)

    def test_report_replay_queue_command_summarizes_rows(self):
        self.addCleanup(os.environ.pop, "REPLAY_SUPPORTED_BUILDS", None)
        os.environ["REPLAY_SUPPORTED_BUILDS"] = "601891"
        match = Match.objects.create(
            external_match_id="legacy-3",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="file:///tmp/demo.mythrec.gz",
            map_name="Megalopolis",
            patch_label="601891",
            raw_payload={},
        )
        ReplayParse.objects.create(
            match=match,
            status=ReplayParse.STATUS_PENDING,
            replay_url="file:///tmp/demo.mythrec.gz",
            extracted_facts={"replay_available": True, "build_number": 601891},
        )

        out = StringIO()
        call_command("report_replay_queue", stdout=out)

        output = out.getvalue()
        self.assertIn("Replay queue:", output)
        self.assertIn("601891", output)
        self.assertIn("unsupported builds: 0", output)

    def test_replay_source_resolution_uses_template(self):
        self.addCleanup(os.environ.pop, "REPLAY_DOWNLOAD_URL_TEMPLATE", None)
        os.environ["REPLAY_DOWNLOAD_URL_TEMPLATE"] = "https://example.com/replays/{match_id}.mythrec.gz"
        match = Match.objects.create(
            external_match_id="legacy-4",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Midgard",
            raw_payload={},
        )

        self.assertEqual(
            resolve_replay_download_url(match),
            "https://example.com/replays/legacy-4.mythrec.gz",
        )

    def test_backfill_replay_sources_attaches_urls_from_template(self):
        self.addCleanup(os.environ.pop, "REPLAY_DOWNLOAD_URL_TEMPLATE", None)
        os.environ["REPLAY_DOWNLOAD_URL_TEMPLATE"] = "https://example.com/replays/{match_id}.mythrec.gz"
        match = Match.objects.create(
            external_match_id="legacy-5",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Ghost Lake",
            raw_payload={},
        )
        replay_parse = ReplayParse.objects.create(
            match=match,
            status=ReplayParse.STATUS_PENDING,
            replay_url="",
            extracted_facts={"replay_available": True},
        )

        summary = backfill_replay_sources()

        self.assertEqual(summary["rows_url_attached"], 1)
        match.refresh_from_db()
        replay_parse.refresh_from_db()
        self.assertEqual(match.replay_url, "https://example.com/replays/legacy-5.mythrec.gz")
        self.assertEqual(replay_parse.replay_url, "https://example.com/replays/legacy-5.mythrec.gz")
        self.assertEqual(replay_parse.extracted_facts.get("replay_acquisition_source"), "url_template")

    def test_backfill_replay_sources_can_target_missing_urls_only(self):
        self.addCleanup(os.environ.pop, "REPLAY_DOWNLOAD_URL_TEMPLATE", None)
        os.environ["REPLAY_DOWNLOAD_URL_TEMPLATE"] = "https://example.com/replays/{match_id}.mythrec.gz"
        ready_match = Match.objects.create(
            external_match_id="legacy-ready",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="https://example.com/existing.mythrec.gz",
            map_name="Ghost Lake",
            raw_payload={},
        )
        missing_match = Match.objects.create(
            external_match_id="legacy-missing",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Ghost Lake",
            raw_payload={},
        )
        ReplayParse.objects.create(
            match=ready_match,
            status=ReplayParse.STATUS_PENDING,
            replay_url=ready_match.replay_url,
            extracted_facts={"replay_available": True},
        )
        ReplayParse.objects.create(
            match=missing_match,
            status=ReplayParse.STATUS_PENDING,
            replay_url="",
            extracted_facts={"replay_available": True},
        )

        summary = backfill_replay_sources(missing_replay_url_only=True)

        self.assertEqual(summary["matches_scanned"], 1)
        self.assertEqual(summary["rows_url_attached"], 1)
        ready_match.refresh_from_db()
        missing_match.refresh_from_db()
        self.assertEqual(ready_match.replay_url, "https://example.com/existing.mythrec.gz")
        self.assertEqual(missing_match.replay_url, "https://example.com/replays/legacy-missing.mythrec.gz")

    def test_extract_replay_url_from_stored_matchurls_prefers_matching_profile(self):
        match = Match.objects.create(
            external_match_id="legacy-6",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Alfheim",
            raw_payload={
                "matchurls": [
                    {"profile_id": 300, "url": "https://example.com/replays/other.gz", "size": 10, "datatype": 0},
                    {"profile_id": 200, "url": "https://example.com/replays/preferred.gz", "size": 20, "datatype": 0},
                ]
            },
        )
        MatchParticipant.objects.create(match=match, profile_id=200, alias="Alpha", team=1, slot=1, civilization="Zeus")
        MatchParticipant.objects.create(match=match, profile_id=300, alias="Beta", team=2, slot=1, civilization="Ra")

        candidate = extract_replay_url_from_match_payload(match)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["url"], "https://example.com/replays/preferred.gz")
        self.assertEqual(candidate["source"], "stored_matchurls")

    def test_fetch_recent_history_replay_url_reads_matchurls(self):
        match = Match.objects.create(
            external_match_id="39107276",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Alfheim",
            raw_payload={},
        )
        MatchParticipant.objects.create(match=match, profile_id=1073744706, alias="Mosca_", team=1, slot=1, civilization="Susanoo")
        MatchParticipant.objects.create(match=match, profile_id=1073789169, alias="Opponent", team=2, slot=1, civilization="Fuxi")

        fake_response = {
            "ok": True,
            "raw": {
                "matchHistoryStats": [
                    {
                        "id": 39107276,
                        "matchurls": [
                            {
                                "profile_id": 1073744706,
                                "url": "https://blob.example.com/M_39107276_player1.gz",
                                "size": 4585623,
                                "datatype": 0,
                            },
                            {
                                "profile_id": 1073789169,
                                "url": "https://blob.example.com/M_39107276_player2.gz",
                                "size": 4572659,
                                "datatype": 0,
                            },
                        ],
                    }
                ]
            },
        }

        with patch("stats.replay_acquisition.async_to_sync") as mocked_async_to_sync:
            mocked_async_to_sync.return_value = lambda **kwargs: fake_response
            candidate = fetch_recent_history_replay_url(match, refresh=True)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["url"], "https://blob.example.com/M_39107276_player1.gz")
        self.assertEqual(candidate["source"], "recent_match_history")

    def test_resolve_api_match_replay_url_uses_first_participant_profile_id(self):
        match = Match.objects.create(
            external_match_id="38630442",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="",
            map_name="Midgard",
            raw_payload={},
        )
        MatchParticipant.objects.create(match=match, profile_id=1073744706, alias="Mosca_", team=1, slot=1, civilization="Loki")

        self.assertEqual(
            resolve_api_match_replay_url(match),
            "https://api.ageofempires.com/api/GameStats/AgeMyth/GetMatchReplay/?matchId=38630442&profileId=1073744706",
        )

    def test_backfill_replay_parses_can_gate_to_recent_1v1_ranked_matches(self):
        recent_started_at = timezone.now()
        old_started_at = recent_started_at - timezone.timedelta(days=30)
        recent_match = Match.objects.create(
            external_match_id="recent-1v1",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            is_team_game=False,
            replay_available=True,
            started_at=recent_started_at,
            map_name="Ghost Lake",
            raw_payload={},
        )
        old_team_match = Match.objects.create(
            external_match_id="old-team",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=2,
            match_type_label="Team Supremacy",
            is_ranked=True,
            is_team_game=True,
            replay_available=True,
            started_at=old_started_at,
            map_name="Midgard",
            raw_payload={},
        )
        MatchParticipant.objects.create(match=recent_match, profile_id=1, alias="A", team=1, slot=1, civilization="Zeus")
        MatchParticipant.objects.create(match=recent_match, profile_id=2, alias="B", team=2, slot=1, civilization="Ra")
        MatchParticipant.objects.create(match=old_team_match, profile_id=3, alias="C", team=1, slot=1, civilization="Loki")
        MatchParticipant.objects.create(match=old_team_match, profile_id=4, alias="D", team=1, slot=2, civilization="Isis")
        MatchParticipant.objects.create(match=old_team_match, profile_id=5, alias="E", team=2, slot=1, civilization="Gaia")
        MatchParticipant.objects.create(match=old_team_match, profile_id=6, alias="F", team=2, slot=2, civilization="Thor")

        summary = backfill_replay_parses(
            ranked_only=True,
            match_type_ids=[1],
            one_v_one_only=True,
            started_after=recent_started_at - timezone.timedelta(days=1),
        )

        self.assertEqual(summary["matches_scanned"], 1)
        self.assertEqual(summary["rows_created"], 1)
        self.assertTrue(ReplayParse.objects.filter(match=recent_match).exists())
        self.assertFalse(ReplayParse.objects.filter(match=old_team_match).exists())


class ReplayParserTests(TestCase):
    def test_parse_replay_queue_batch_skips_unsupported_builds(self):
        supported_match = Match.objects.create(
            external_match_id="build-supported",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="file:///tmp/supported.mythrec.gz",
            map_name="Ghost Lake",
            patch_label="601891",
            raw_payload={},
        )
        unsupported_match = Match.objects.create(
            external_match_id="build-unsupported",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="file:///tmp/unsupported.mythrec.gz",
            map_name="Midgard",
            patch_label="600000",
            raw_payload={},
        )
        ReplayParse.objects.create(
            match=supported_match,
            status=ReplayParse.STATUS_PENDING,
            replay_url=supported_match.replay_url,
            extracted_facts={"replay_available": True, "build_number": 601891},
        )
        ReplayParse.objects.create(
            match=unsupported_match,
            status=ReplayParse.STATUS_PENDING,
            replay_url=unsupported_match.replay_url,
            extracted_facts={"replay_available": True, "build_number": 600000},
        )

        with patch("stats.replay_parser.process_replay_parse") as mocked_process:
            summary = parse_replay_queue_batch(limit=5, supported_builds=["601891"], allow_unknown_builds=False)

        self.assertEqual(summary["parsed_count"], 1)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(summary["skipped_count"], 1)
        self.assertEqual(mocked_process.call_count, 1)
        parsed_row = mocked_process.call_args[0][0]
        self.assertEqual(parsed_row.match.external_match_id, "build-supported")

    def test_parse_replay_queue_batch_can_block_unknown_builds(self):
        unknown_match = Match.objects.create(
            external_match_id="build-unknown",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="file:///tmp/unknown.mythrec.gz",
            map_name="Ghost Lake",
            patch_label="",
            raw_payload={},
        )
        ReplayParse.objects.create(
            match=unknown_match,
            status=ReplayParse.STATUS_PENDING,
            replay_url=unknown_match.replay_url,
            extracted_facts={"replay_available": True},
        )

        with patch("stats.replay_parser.process_replay_parse") as mocked_process:
            summary = parse_replay_queue_batch(limit=5, supported_builds=["601891"], allow_unknown_builds=False)

        self.assertEqual(summary["parsed_count"], 0)
        self.assertEqual(summary["skipped_count"], 1)
        self.assertEqual(mocked_process.call_count, 0)

    def test_download_replay_to_temp_extracts_zip_archives(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("MythRetold_Replay_123.mythrec", b"demo replay bytes")
        zip_bytes = buffer.getvalue()

        class FakeResponse:
            headers = {
                "content-type": "application/zip",
                "content-disposition": "attachment; filename=MythRetold_Replay_123.zip",
            }
            content = zip_bytes

            def raise_for_status(self):
                return None

        with patch("stats.replay_parser.requests.get", return_value=FakeResponse()):
            artifact = _download_replay_to_temp("https://api.ageofempires.com/api/GameStats/AgeMyth/GetMatchReplay/?matchId=123&profileId=456")

        try:
            self.assertTrue(str(artifact.local_path).endswith(".mythrec"))
            self.assertEqual(artifact.local_path.read_bytes(), b"demo replay bytes")
        finally:
            artifact.cleanup()

    def test_enrichment_creates_player_summaries_and_unit_rows(self):
        detail_match = {
            "match_type": 1,
            "match_type_label": "1v1 Supremacy",
            "map": "Steppe",
            "date_time": "2026-06-01T12:00:00",
            "players": [
                {
                    "profile_id": 1073744203,
                    "name": "_DesivE_",
                    "team": 1,
                    "slot": 1,
                    "result": "win",
                    "god": "Oranos",
                    "elo": 1200,
                    "match_replay_available": True,
                },
                {
                    "profile_id": 1073796204,
                    "name": "TAG_RecoN",
                    "team": 2,
                    "slot": 1,
                    "result": "loss",
                    "god": "Quetzalcoatl",
                    "elo": 1188,
                    "match_replay_available": True,
                },
            ],
        }
        match_row = {
            "match_id": "replay-123",
            "map": "Steppe",
            "date_time": "2026-06-01T12:00:00",
        }

        match, _ = _upsert_match_with_participants(
            external_match_id="replay-123",
            requested_match_type=1,
            match_row=match_row,
            detail_match=detail_match,
            detail_raw={"replayUrl": "file:///tmp/demo.mythrec.gz"},
            dry_run=False,
        )
        replay_parse = ReplayParse.objects.get(match=match)

        parsed_json = {
            "MapName": "steppe",
            "BuildNumber": 601511,
            "BuildString": "AoMRT_s.exe 601511 //stream/Athens/stable",
            "ParserVersion": "v0.5.4",
            "GameLengthSecs": 1282.85,
            "WinningTeam": 0,
            "Players": [
                {
                    "PlayerNum": 1,
                    "TeamId": 0,
                    "Name": "_DesivE_",
                    "ProfileId": 1073744203,
                    "God": "Oranos",
                    "Winner": True,
                    "EAPM": 81.849,
                    "MinorGods": ["Oceanus", "Hyperion", ""],
                },
                {
                    "PlayerNum": 2,
                    "TeamId": 1,
                    "Name": "TAG_RecoN",
                    "ProfileId": 1073796204,
                    "God": "Quetzalcoatl",
                    "Winner": False,
                    "EAPM": 79.417,
                    "MinorGods": ["Patecatl", "Coyolxauhqui", "Tlaloc"],
                },
            ],
            "Stats": {
                "1": {
                    "UnitCounts": {
                        "Murmillo": 60,
                        "Contarius": 55,
                        "Oracle": 7,
                    },
                    "Timelines": {
                        "UnitCounts": [
                            {},
                            {},
                            {},
                            {},
                            {"Murmillo": 3, "Oracle": 1},
                            {"Murmillo": 5},
                        ],
                        "BuildingCounts": [
                            {"Manor": 1},
                            {},
                            {"Temple": 1},
                            {"MilitaryBarracks": 1},
                            {},
                            {},
                            {},
                            {},
                            {"TownCenter": 1},
                            {},
                            {},
                            {},
                            {"Market": 1},
                        ],
                        "TechsPrequeued": [
                            {"Name": "ClassicalAgeOceanus", "GameTimeSecs": 171.55},
                            {"Name": "HeroicAgeHyperion", "GameTimeSecs": 597.15},
                        ],
                    },
                },
                "2": {
                    "UnitCounts": {
                        "AxeRaider": 20,
                        "EagleWarrior": 35,
                        "Villager": 2,
                    },
                    "Timelines": {
                        "UnitCounts": [
                            {},
                            {},
                            {},
                            {"EagleWarrior": 4},
                        ],
                        "BuildingCounts": [],
                        "TechsPrequeued": [
                            {"Name": "ClassicalAgePatecatl", "GameTimeSecs": 160.1},
                            {"Name": "HeroicAgeCoyolxauhqui", "GameTimeSecs": 910.0},
                        ],
                    },
                },
            },
        }

        enrich_replay_parse_from_json(
            replay_parse,
            parsed_json=parsed_json,
            parser_binary="/Users/mark/Downloads/restoration/restoration",
            replay_sha256="abc123",
        )

        replay_parse.refresh_from_db()
        self.assertEqual(replay_parse.status, ReplayParse.STATUS_PARSED)
        self.assertEqual(replay_parse.parser_version, "v0.5.4")
        self.assertEqual(replay_parse.extracted_facts["map_name"], "steppe")
        self.assertEqual(replay_parse.player_summaries.count(), 2)

        desive_summary = replay_parse.player_summaries.get(participant__profile_id=1073744203)
        self.assertEqual(desive_summary.primary_unit, "Murmillo")
        self.assertEqual(desive_summary.primary_strategy, "Fast Heroic")
        self.assertEqual(desive_summary.age_up_classical_seconds, 171)
        self.assertEqual(desive_summary.age_up_heroic_seconds, 597)
        self.assertTrue(desive_summary.unit_summaries.filter(unit_name="Murmillo", produced_count=60).exists())

    def test_process_replay_parse_falls_back_after_dead_replay_url(self):
        match = Match.objects.create(
            external_match_id="fallback-1",
            source=Match.SOURCE_WORLDSEDGE,
            match_type_id=1,
            match_type_label="1v1 Supremacy",
            is_ranked=True,
            replay_available=True,
            replay_url="https://dead.example.com/replay.gz",
            map_name="Ghost Lake",
            raw_payload={},
        )
        MatchParticipant.objects.create(match=match, profile_id=101, alias="Alpha", team=1, slot=1, civilization="Oranos")
        replay_parse = ReplayParse.objects.create(
            match=match,
            status=ReplayParse.STATUS_PENDING,
            replay_url="https://dead.example.com/replay.gz",
            extracted_facts={"replay_available": True},
        )
        parsed_json = {
            "MapName": "ghost_lake",
            "BuildNumber": 601891,
            "ParserVersion": "v0.5.4",
            "GameLengthSecs": 900,
            "WinningTeam": 0,
            "Players": [{"PlayerNum": 1, "TeamId": 0, "Name": "Alpha", "ProfileId": 101, "God": "Oranos", "Winner": True, "EAPM": 70}],
            "Stats": {"1": {"UnitCounts": {"Contarius": 10}, "Timelines": {"UnitCounts": [{"Contarius": 2}], "BuildingCounts": [], "TechsPrequeued": []}}},
        }

        def fake_download(url):
            if "dead.example.com" in url:
                raise Exception("404 dead blob")
            return ReplayArtifact(local_path=__import__("pathlib").Path("/tmp/demo-fallback.mythrec.gz"))

        with patch("stats.replay_parser._download_replay_to_temp", side_effect=fake_download):
            with patch("stats.replay_parser.parse_replay_file", return_value=(parsed_json, "/tmp/restoration", "sha123")):
                with patch("stats.replay_parser.resolve_api_match_replay_url", return_value="https://api.example.com/replay?matchId=fallback-1&profileId=101"):
                    process_replay_parse(replay_parse, resolve_live_history=False)

        replay_parse.refresh_from_db()
        self.assertEqual(replay_parse.status, ReplayParse.STATUS_PARSED)
        self.assertEqual(replay_parse.replay_url, "https://api.example.com/replay?matchId=fallback-1&profileId=101")
