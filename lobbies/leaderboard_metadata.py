from __future__ import annotations

from typing import Any

from .mappings import GOD_BY_RACE_ID


LEADERBOARDS: list[dict[str, Any]] = [
    {
        "id": 0,
        "name": "Custom",
        "label": "Custom",
        "is_ranked": False,
        "match_type_ids": [0],
    },
    {
        "id": 1,
        "name": "1v1Supremacy",
        "label": "Ranked 1v1",
        "is_ranked": True,
        "match_type_ids": [1],
    },
    {
        "id": 2,
        "name": "TeamSupremacy",
        "label": "Ranked Teams",
        "is_ranked": True,
        "match_type_ids": [2, 3, 4],
    },
    {
        "id": 3,
        "name": "Deathmatch",
        "label": "Deathmatch",
        "is_ranked": True,
        "match_type_ids": [5],
    },
    {
        "id": 4,
        "name": "TeamDeathmatch",
        "label": "Team Deathmatch",
        "is_ranked": True,
        "match_type_ids": [6, 7, 8],
    },
    {
        "id": 11,
        "name": "1v1SupremacyControllerOnly",
        "label": "1v1 Supremacy Controller",
        "is_ranked": True,
        "match_type_ids": [40],
    },
    {
        "id": 12,
        "name": "TeamSupremacyControllerOnly",
        "label": "Team Supremacy Controller",
        "is_ranked": True,
        "match_type_ids": [41, 42, 43],
    },
    {
        "id": 13,
        "name": "DeathmatchControllerOnly",
        "label": "1v1 Deathmatch Controller",
        "is_ranked": True,
        "match_type_ids": [44],
    },
    {
        "id": 14,
        "name": "TeamDeathmatchControllerOnly",
        "label": "Team Deathmatch Controller",
        "is_ranked": True,
        "match_type_ids": [45, 46, 47],
    },
]


MATCH_TYPES: list[dict[str, Any]] = [
    {"id": 0, "name": "CUSTOM", "label": "Custom", "leaderboard_id": 0, "is_ranked": False},
    {"id": 1, "name": "1V1_SUPREMACY", "label": "1v1 Supremacy", "leaderboard_id": 1, "is_ranked": True},
    {"id": 2, "name": "2V2_SUPREMACY", "label": "2v2 Supremacy", "leaderboard_id": 2, "is_ranked": True},
    {"id": 3, "name": "3V3_SUPREMACY", "label": "3v3 Supremacy", "leaderboard_id": 2, "is_ranked": True},
    {"id": 4, "name": "4V4_SUPREMACY", "label": "4v4 Supremacy", "leaderboard_id": 2, "is_ranked": True},
    {"id": 5, "name": "1V1_DEATHMATCH", "label": "1v1 Deathmatch", "leaderboard_id": 3, "is_ranked": True},
    {"id": 6, "name": "2V2_DEATHMATCH", "label": "2v2 Deathmatch", "leaderboard_id": 4, "is_ranked": True},
    {"id": 7, "name": "3V3_DEATHMATCH", "label": "3v3 Deathmatch", "leaderboard_id": 4, "is_ranked": True},
    {"id": 8, "name": "4V4_DEATHMATCH", "label": "4v4 Deathmatch", "leaderboard_id": 4, "is_ranked": True},
    {
        "id": 40,
        "name": "1V1_SUPREMACY_CONTROLLER_ONLY",
        "label": "1v1 Supremacy Controller",
        "leaderboard_id": 11,
        "is_ranked": True,
    },
    {
        "id": 41,
        "name": "2V2_SUPREMACY_CONTROLLER_ONLY",
        "label": "2v2 Supremacy Controller",
        "leaderboard_id": 12,
        "is_ranked": True,
    },
    {
        "id": 42,
        "name": "3V3_SUPREMACY_CONTROLLER_ONLY",
        "label": "3v3 Supremacy Controller",
        "leaderboard_id": 12,
        "is_ranked": True,
    },
    {
        "id": 43,
        "name": "4V4_SUPREMACY_CONTROLLER_ONLY",
        "label": "4v4 Supremacy Controller",
        "leaderboard_id": 12,
        "is_ranked": True,
    },
    {
        "id": 44,
        "name": "1V1_DEATHMATCH_CONTROLLER_ONLY",
        "label": "1v1 Deathmatch Controller",
        "leaderboard_id": 13,
        "is_ranked": True,
    },
    {
        "id": 45,
        "name": "2V2_DEATHMATCH_CONTROLLER_ONLY",
        "label": "2v2 Deathmatch Controller",
        "leaderboard_id": 14,
        "is_ranked": True,
    },
    {
        "id": 46,
        "name": "3V3_DEATHMATCH_CONTROLLER_ONLY",
        "label": "3v3 Deathmatch Controller",
        "leaderboard_id": 14,
        "is_ranked": True,
    },
    {
        "id": 47,
        "name": "4V4_DEATHMATCH_CONTROLLER_ONLY",
        "label": "4v4 Deathmatch Controller",
        "leaderboard_id": 14,
        "is_ranked": True,
    },
]


FACTIONS: list[dict[str, Any]] = [
    {"id": 0, "name": "MotherNature", "locstringid": -1},
    {"id": 1, "name": "Greek", "locstringid": -1},
    {"id": 2, "name": "Egyptian", "locstringid": -1},
    {"id": 3, "name": "Norse", "locstringid": -1},
    {"id": 4, "name": "Atlantean", "locstringid": -1},
    {"id": 5, "name": "Chinese", "locstringid": -1},
    {"id": 6, "name": "Japanese", "locstringid": -1},
    {"id": 7, "name": "Aztec", "locstringid": -1},
]


RACES: list[dict[str, Any]] = [
    {"id": 1, "name": "Zeus", "faction_id": 1, "locstringid": -1},
    {"id": 2, "name": "Hades", "faction_id": 1, "locstringid": -1},
    {"id": 3, "name": "Poseidon", "faction_id": 1, "locstringid": -1},
    {"id": 4, "name": "Ra", "faction_id": 2, "locstringid": -1},
    {"id": 5, "name": "Isis", "faction_id": 2, "locstringid": -1},
    {"id": 6, "name": "Set", "faction_id": 2, "locstringid": -1},
    {"id": 7, "name": "Thor", "faction_id": 3, "locstringid": -1},
    {"id": 8, "name": "Odin", "faction_id": 3, "locstringid": -1},
    {"id": 9, "name": "Loki", "faction_id": 3, "locstringid": -1},
    {"id": 10, "name": "Kronos", "faction_id": 4, "locstringid": -1},
    {"id": 11, "name": "Oranos", "faction_id": 4, "locstringid": -1},
    {"id": 12, "name": "Gaia", "faction_id": 4, "locstringid": -1},
    {"id": 13, "name": "Freyr", "faction_id": 3, "locstringid": -1},
    {"id": 14, "name": "Fuxi", "faction_id": 5, "locstringid": -1},
    {"id": 15, "name": "Nuwa", "faction_id": 5, "locstringid": -1},
    {"id": 16, "name": "Shennong", "faction_id": 5, "locstringid": -1},
    {"id": 17, "name": "Amaterasu", "faction_id": 6, "locstringid": -1},
    {"id": 18, "name": "Tsukuyomi", "faction_id": 6, "locstringid": -1},
    {"id": 19, "name": "Susanoo", "faction_id": 6, "locstringid": -1},
    {"id": 20, "name": "Demeter", "faction_id": 1, "locstringid": -1},
    {"id": 21, "name": "Huitzilopochtli", "faction_id": 7, "locstringid": -1},
    {"id": 22, "name": "Tezcatlipoca", "faction_id": 7, "locstringid": -1},
    {"id": 23, "name": "Quetzalcoatl", "faction_id": 7, "locstringid": -1},
]


MATCH_TYPE_LOOKUP = {item["id"]: item for item in MATCH_TYPES}
LEADERBOARD_LOOKUP = {item["id"]: item for item in LEADERBOARDS}
RACE_LOOKUP = {item["id"]: item for item in RACES}
FACTION_LOOKUP = {item["id"]: item for item in FACTIONS}


def get_match_type_meta(match_type_id: int | None) -> dict[str, Any] | None:
    if match_type_id is None:
        return None

    return MATCH_TYPE_LOOKUP.get(int(match_type_id))


def get_match_type_label(match_type_id: int | None) -> str:
    if match_type_id is None:
        return "Unknown"

    meta = get_match_type_meta(match_type_id)
    return str(meta["label"]) if meta else f"Match Type {match_type_id}"


def get_queue_meta(queue_id: int | None) -> dict[str, Any] | None:
    if queue_id is None:
        return None

    return LEADERBOARD_LOOKUP.get(int(queue_id))


def get_queue_label(queue_id: int | None) -> str:
    if queue_id is None:
        return "Unknown"

    meta = get_queue_meta(queue_id)
    return str(meta["label"]) if meta else f"Queue {queue_id}"


def get_ranked_queues() -> list[dict[str, Any]]:
    # The community leaderboard and personal-stat APIs expose these as the
    # primary PC leaderboard queue IDs: 1, 2, 3, and 4.
    return [item for item in LEADERBOARDS if item.get("is_ranked") and int(item["id"]) in {1, 2, 3, 4}]


def get_ranked_match_type_ids() -> list[int]:
    return [int(item["id"]) for item in MATCH_TYPES if item.get("is_ranked")]


def get_match_type_ids_for_leaderboard(leaderboard_id: int | None) -> list[int]:
    if leaderboard_id is None:
        return []

    meta = LEADERBOARD_LOOKUP.get(int(leaderboard_id))
    if not meta:
        return []

    values = meta.get("match_type_ids") or []
    return [int(value) for value in values]


def resolve_community_civilization_name(value: Any) -> str:
    if value in (None, ""):
        return ""

    try:
        race_id = int(value)
    except (TypeError, ValueError):
        return str(value).strip()

    race = RACE_LOOKUP.get(race_id)
    return str(race["name"]) if race else str(value).strip()


def resolve_legacy_race_name(value: Any) -> str:
    if value in (None, ""):
        return ""

    try:
        race_id = int(value)
    except (TypeError, ValueError):
        return str(value).strip()

    race_name = GOD_BY_RACE_ID.get(race_id)
    return str(race_name) if race_name else str(value).strip()


def resolve_race_name(value: Any) -> str:
    # Backward-compatible alias for community/history payloads that expose
    # civilization_id values rather than the older lobby/detail race IDs.
    return resolve_community_civilization_name(value)


def get_ranked_match_types() -> list[dict[str, Any]]:
    return [item for item in MATCH_TYPES if item.get("is_ranked")]


def build_leaderboard_metadata_payload() -> dict[str, Any]:
    return {
        "leaderboards": LEADERBOARDS,
        "queues": LEADERBOARDS,
        "ranked_queues": get_ranked_queues(),
        "match_types": MATCH_TYPES,
        "ranked_match_types": get_ranked_match_types(),
        "races": RACES,
        "factions": FACTIONS,
    }
