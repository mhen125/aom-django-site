import base64
import json
import zlib
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from .leaderboard import (
    build_source_meta,
    get_match_type_filter_ids,
    normalize_match_detail_for_player,
    normalize_personal_stat_record,
    normalize_recent_match_history_record,
    search_leaderboard,
)
from .leaderboard_metadata import (
    resolve_community_civilization_name,
    resolve_legacy_race_name,
)


def encode_payload(value):
    text = value if isinstance(value, str) else json.dumps(value)
    return base64.b64encode(zlib.compress(text.encode("utf-8"))).decode("ascii")


class PersonalStatNormalizationTests(SimpleTestCase):
    def test_personal_stat_uses_queue_ids_and_lifetime_record(self):
        member = {
            "profile_id": 1075470702,
            "name": "/steam/76561199052679921",
            "alias": "<color1,1,1,0.2,0,0.4>Shake Zula",
            "leaderboardregion_id": 3,
            "country": "us",
            "clanlist_name": "SAY",
        }
        stats_row = {
            "leaderboard_id": 2,
            "wins": 31,
            "losses": 35,
            "rating": 1056,
            "rank": 3720,
            "ranktotal": 8783,
            "highestrating": 1148,
        }

        normalized = normalize_personal_stat_record(member, stats_row)

        self.assertEqual(normalized["queue_id"], 2)
        self.assertEqual(normalized["queue_label"], "Ranked Teams")
        self.assertEqual(normalized["games"], 66)
        self.assertEqual(normalized["win_rate"], 47.0)
        self.assertEqual(normalized["name"], "Shake Zula")
        self.assertEqual(normalized["platform"], "steam")
        self.assertEqual(normalized["platform_id"], "76561199052679921")


class LeaderboardSearchTests(SimpleTestCase):
    @patch("lobbies.leaderboard.fetch_leaderboard_raw")
    def test_search_keeps_duplicate_alias_candidates(self, fetch_leaderboard_raw):
        fetch_leaderboard_raw.return_value = {
            "ok": True,
            "cached": False,
            "status_code": 200,
            "transport": "test",
            "selected_transport": "test",
            "request": {},
            "shape": {},
            "raw": {
                "items": [
                    {
                        "userName": "SameName",
                        "rlUserId": 101,
                        "rank": 1,
                        "rating": 1200,
                        "wins": 10,
                        "losses": 2,
                    },
                    {
                        "userName": "SameName",
                        "rlUserId": 202,
                        "rank": 2,
                        "rating": 1190,
                        "wins": 9,
                        "losses": 3,
                    },
                ],
            },
        }

        result = async_to_sync(search_leaderboard)(player="SameName", match_type=1)

        self.assertEqual(result["match_count"], 2)
        self.assertEqual(
            [match["profile_id"] for match in result["matches"]],
            [101, 202],
        )
        self.assertTrue(all(match["confidence"] == "exact" for match in result["matches"]))


class RecentMatchHistoryNormalizationTests(SimpleTestCase):
    def test_recent_history_decodes_payloads_and_normalizes_map(self):
        row = {
            "id": 555,
            "matchtype_id": 1,
            "startgametime": 1781320000,
            "completiontime": 1781321800,
            "mapname": "",
            "options": encode_payload({"mGameMapName": "rm_giza"}),
            "slotinfo": encode_payload(
                '2,[{"profileInfo.id":107,"team":1},{"profileInfo.id":208,"team":2}]'
            ),
            "matchhistorymember": [
                {
                    "profile_id": 107,
                    "teamid": 1,
                    "civilization_id": 17,
                    "outcome": 1,
                    "oldrating": 1000,
                    "newrating": 1016,
                },
                {
                    "profile_id": 208,
                    "teamid": 2,
                    "civilization_id": 1,
                    "outcome": 0,
                    "oldrating": 1000,
                    "newrating": 984,
                },
            ],
            "matchhistoryreportresults": [
                {
                    "profile_id": 107,
                    "resulttype": 1,
                    "counters": json.dumps({"rankedMatch": 1}),
                },
            ],
        }

        normalized = normalize_recent_match_history_record(
            row,
            profiles_by_id={
                107: {"profile_id": 107, "alias": "Player One", "name": "/steam/1"},
                208: {"profile_id": 208, "alias": "Player Two", "name": "/steam/2"},
            },
            requested_profile_id=107,
            requested_match_type=1,
        )

        self.assertEqual(normalized["map"], "Giza")
        self.assertEqual(normalized["result"], "Win")
        self.assertEqual(normalized["rating_change"], 16)
        self.assertEqual(normalized["civilization"], "Amaterasu")
        self.assertEqual(normalized["ranked_match"], 1)
        self.assertTrue(normalized["decoded_payloads"]["options"]["decoded"])
        self.assertTrue(normalized["decoded_payloads"]["slotinfo"]["decoded"])
        self.assertEqual(normalized["slot_info"]["slot_count"], 2)
        self.assertEqual(len(normalized["players"]), 2)

    def test_community_civilization_ids_stay_separate_from_legacy_race_ids(self):
        self.assertEqual(resolve_community_civilization_name(17), "Amaterasu")
        self.assertEqual(resolve_community_civilization_name(23), "Quetzalcoatl")
        self.assertEqual(resolve_legacy_race_name(17), "Amaterasu")
        self.assertEqual(resolve_legacy_race_name(23), "Quetzalcoatl")

    def test_leaderboard_metadata_matches_canonical_frontend_tables(self):
        from .leaderboard_metadata import FACTIONS, RACES

        self.assertEqual(FACTIONS[0], {"id": 0, "name": "MotherNature", "locstringid": -1})
        self.assertEqual(FACTIONS[-1], {"id": 7, "name": "Aztec", "locstringid": -1})
        self.assertEqual(RACES[6]["name"], "Thor")
        self.assertEqual(RACES[7]["name"], "Odin")
        self.assertEqual(RACES[10]["name"], "Oranos")
        self.assertEqual(RACES[11]["name"], "Gaia")
        self.assertEqual(RACES[12]["name"], "Freyr")
        self.assertEqual(RACES[16]["name"], "Amaterasu")
        self.assertEqual(RACES[22]["name"], "Quetzalcoatl")

    def test_match_detail_uses_legacy_race_ids(self):
        normalized = normalize_match_detail_for_player(
            raw_detail={
                "matchSummary": {
                    "mapName": "rm_giza",
                    "dateTime": "2026-06-13T12:00:00Z",
                },
                "players": [
                    {
                        "userId": 107,
                        "userName": "Player One",
                        "raceId": 17,
                        "team": 0,
                        "elo": 1200,
                        "eloChange": 15,
                        "winLoss": "Win",
                    },
                    {
                        "userId": 208,
                        "userName": "Player Two",
                        "raceId": 23,
                        "team": 1,
                        "elo": 1185,
                        "eloChange": -15,
                        "winLoss": "Loss",
                    },
                ],
            },
            profile_id=107,
            match_id="detail-1",
            requested_match_type=1,
        )

        self.assertEqual(normalized["civilization"], "Amaterasu")
        self.assertEqual(normalized["players"][0]["god"], "Amaterasu")
        self.assertEqual(normalized["players"][1]["god"], "Quetzalcoatl")


class QueueFilterTests(SimpleTestCase):
    def test_ranked_teams_expands_to_team_match_types(self):
        self.assertEqual(get_match_type_filter_ids(2), [2, 3, 4])


class SourceMetadataTests(SimpleTestCase):
    def test_source_meta_contains_queue_cache_status_and_timestamp(self):
        meta = build_source_meta(
            endpoint="community/leaderboard/getRecentMatchHistory",
            queue_id=2,
            expanded_match_type_ids=[2, 3, 4],
            cached=True,
            status_code=200,
            source="community_recent_match_history",
        )

        self.assertEqual(meta["source"], "community_recent_match_history")
        self.assertEqual(meta["endpoint"], "community/leaderboard/getRecentMatchHistory")
        self.assertEqual(meta["queue_id"], 2)
        self.assertEqual(meta["queue_label"], "Ranked Teams")
        self.assertEqual(meta["expanded_match_type_ids"], [2, 3, 4])
        self.assertTrue(meta["cached"])
        self.assertEqual(meta["status_code"], 200)
        self.assertRegex(meta["fetched_at"], r"^\d{4}-\d{2}-\d{2}T.*Z$")
