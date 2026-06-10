import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx


AOMSTATS_LOBBIES_URL = "https://aomstats.io/lobbies/__data.json"
AOMSTATS_LOBBIES_PAGE_URL = "https://aomstats.io/lobbies"
AOMSTATS_LOBBIES_METADATA_URL = "https://aomstats.io/api/lobbies/metadata"
STEAM_CURRENT_PLAYERS_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
AOM_RETOLD_STEAM_APP_ID = 1934680

DB_PATH = Path(__file__).resolve().parent / "activity_snapshots.sqlite3"

REGION_COORDS: dict[str, dict[str, Any]] = {
    "us-east": {"label": "US East", "lat": 39.0, "lon": -77.0},
    "us-west": {"label": "US West", "lat": 37.8, "lon": -122.4},
    "europe": {"label": "Europe", "lat": 50.1, "lon": 8.6},
    "brazil": {"label": "Brazil", "lat": -23.5, "lon": -46.6},
    "asia": {"label": "Asia", "lat": 35.7, "lon": 139.7},
    "australia": {"label": "Australia", "lat": -33.9, "lon": 151.2},
    "india": {"label": "India", "lat": 19.1, "lon": 72.9},
    "middle-east": {"label": "Middle East", "lat": 25.2, "lon": 55.3},
    "south-africa": {"label": "South Africa", "lat": -26.2, "lon": 28.0},
    "unknown": {"label": "Unknown", "lat": 0.0, "lon": 0.0},
}

REGION_ALIASES = {
    "eastus": "us-east",
    "east-us": "us-east",
    "us east": "us-east",
    "us-east": "us-east",
    "useast": "us-east",
    "east us": "us-east",
    "virginia": "us-east",
    "westus": "us-west",
    "west-us": "us-west",
    "us west": "us-west",
    "us-west": "us-west",
    "uswest": "us-west",
    "west us": "us-west",
    "california": "us-west",
    "europe": "europe",
    "eu": "europe",
    "westeurope": "europe",
    "west europe": "europe",
    "northeurope": "europe",
    "north europe": "europe",
    "germany": "europe",
    "france": "europe",
    "uk": "europe",
    "united kingdom": "europe",
    "brazil": "brazil",
    "brasil": "brazil",
    "southamerica": "brazil",
    "south america": "brazil",
    "eastasia": "asia",
    "east asia": "asia",
    "southeastasia": "asia",
    "southeast asia": "asia",
    "asia": "asia",
    "japan": "asia",
    "korea": "asia",
    "singapore": "asia",
    "australia": "australia",
    "australiaeast": "australia",
    "australia east": "australia",
    "india": "india",
    "centralindia": "india",
    "central india": "india",
    "uae": "middle-east",
    "uae north": "middle-east",
    "middleeast": "middle-east",
    "middle east": "middle-east",
    "southafrica": "south-africa",
    "south africa": "south-africa",
    # Azure / Worlds Edge relay-region names observed in aomstats and the upstream lobby API.
    "eastus": "us-east",
    "east us": "us-east",
    "southcentralus": "us-east",
    "south central us": "us-east",
    "centralus": "us-east",
    "central us": "us-east",
    "westus": "us-west",
    "westus2": "us-west",
    "westus3": "us-west",
    "west us 2": "us-west",
    "west us 3": "us-west",
    "brazilsouth": "brazil",
    "brazil south": "brazil",
    "westeurope": "europe",
    "west europe": "europe",
    "northeurope": "europe",
    "north europe": "europe",
    "italynorth": "europe",
    "italy north": "europe",
    "ukwest": "europe",
    "uk west": "europe",
    "uksouth": "europe",
    "uk south": "europe",
    "australiasoutheast": "australia",
    "australia southeast": "australia",
}

MODE_ALIASES = {
    "standard": "supremacy",
    "supremacy": "supremacy",
    "conquest": "supremacy",
    "deathmatch": "deathmatch",
    "death match": "deathmatch",
    "lightning": "lightning",
    "king of the hill": "king-of-the-hill",
    "regicide": "regicide",
    "arena of the gods": "arena-of-the-gods",
    "arenaofthegods": "arena-of-the-gods",
    "aotg": "arena-of-the-gods",
}

MODE_LABELS = {
    "supremacy": "Supremacy",
    "deathmatch": "Deathmatch",
    "lightning": "Lightning",
    "king-of-the-hill": "King of the Hill",
    "regicide": "Regicide",
    "arena-of-the-gods": "Arena of the Gods",
    "unknown": "Unknown",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def slugify(value: Any, default: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default

    cleaned = []
    previous_dash = False

    for char in text:
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
        elif not previous_dash:
            cleaned.append("-")
            previous_dash = True

    slug = "".join(cleaned).strip("-")
    return slug or default


def normalize_region(raw_region: Any) -> tuple[str, str, float, float]:
    text = str(raw_region or "").strip()
    key = text.lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    compact_key = key.replace(" ", "")

    region_id = (
        REGION_ALIASES.get(key)
        or REGION_ALIASES.get(compact_key)
        or REGION_ALIASES.get(str(raw_region or "").strip().lower())
    )

    if not region_id:
        region_id = slugify(text)

    coords = REGION_COORDS.get(region_id)

    if not coords:
        coords = REGION_COORDS["unknown"]
        label = text or "Unknown"
        return region_id, label, coords["lat"], coords["lon"]

    return region_id, coords["label"], coords["lat"], coords["lon"]


def normalize_mode(raw_mode: Any, lobby_name: Any = None, map_name: Any = None) -> tuple[str, str]:
    candidates = [raw_mode, lobby_name, map_name]

    for candidate in candidates:
        text = str(candidate or "").strip()
        key = text.lower().replace("_", " ").replace("-", " ")
        key = " ".join(key.split())
        compact_key = key.replace(" ", "")

        if key in MODE_ALIASES:
            mode_id = MODE_ALIASES[key]
            return mode_id, MODE_LABELS.get(mode_id, text)

        for alias, mode_id in MODE_ALIASES.items():
            if alias in key or alias.replace(" ", "") in compact_key:
                return mode_id, MODE_LABELS.get(mode_id, text)

    return "unknown", "Unknown"


def get_first_value(source: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in source and source.get(key) not in (None, ""):
            return source.get(key)
    return None


def count_slots_from_list(slots: list[Any]) -> dict[str, int]:
    humans = 0
    ai = 0
    open_slots = 0
    closed = 0

    for slot in slots:
        if not isinstance(slot, dict):
            continue

        slot_text = " ".join(str(value).lower() for value in slot.values() if value is not None)
        status = slot.get("status")
        slot_type = str(slot.get("type") or slot.get("slot_type") or slot.get("kind") or "").lower()

        if status == 1 or "closed" in slot_text or slot_type == "closed":
            closed += 1
        elif status == 2 or " ai" in f" {slot_text}" or slot_type == "ai":
            ai += 1
        elif "open" in slot_text or "empty" in slot_text:
            open_slots += 1
        else:
            humans += 1

    return {
        "human_players": humans,
        "ai_players": ai,
        "open_human_slots": open_slots,
        "closed_slots": closed,
    }


def normalize_external_lobby(raw_lobby: dict[str, Any]) -> dict[str, Any]:
    name = get_first_value(raw_lobby, ["name", "title", "description", "lobbyName", "lobby_name", "lobby", "lobbyTitle"]) or "Unnamed lobby"
    raw_region = get_first_value(raw_lobby, ["region", "relay_region", "relayserver_region", "serverRegion", "server_region", "server", "serverName", "server_name", "azureRegion", "azure_region"])
    region_id, region_label, lat, lon = normalize_region(raw_region)

    map_name = get_first_value(raw_lobby, ["map", "mapName", "map_name", "mapname"])
    raw_mode = get_first_value(raw_lobby, ["mode", "gameMode", "game_mode", "gameType", "game_type", "matchType", "match_type", "ladder", "ladderName", "ladder_name"])
    mode_id, mode_label = normalize_mode(raw_mode, name, map_name)

    slots = get_first_value(raw_lobby, ["slots", "participants", "players", "members"])
    slot_counts = count_slots_from_list(slots) if isinstance(slots, list) else {}

    human_players = safe_int(
        get_first_value(raw_lobby, ["human_players", "humans", "currentPlayers", "current_players", "playersCurrent", "players_current", "occupied_slots"]),
        slot_counts.get("human_players", 0),
    )
    ai_players = safe_int(get_first_value(raw_lobby, ["ai_players", "aiPlayers", "ais"]), slot_counts.get("ai_players", 0))
    open_slots = safe_int(get_first_value(raw_lobby, ["open_human_slots", "openSlots", "open_slots"]), slot_counts.get("open_human_slots", 0))
    max_players = safe_int(get_first_value(raw_lobby, ["max_players", "maxPlayers", "maxplayers", "slotsMax", "slots_max", "slotCount", "slot_count", "maxSlots", "max_slots"]), human_players + ai_players + open_slots)

    has_ai = ai_players > 0
    text_blob = " ".join(str(raw_lobby.get(key, "")) for key in ["name", "title", "description", "mode", "gameMode", "map", "mapName"]).lower()
    is_aotg = "arena of the gods" in text_blob or "aotg" in text_blob

    return {
        "id": get_first_value(raw_lobby, ["id", "match_id", "matchID", "lobby_id", "lobbyID", "advertisement_id", "advertisementID"]),
        "name": str(name),
        "region": region_id,
        "region_label": region_label,
        "lat": lat,
        "lon": lon,
        "map": str(map_name or "Unknown"),
        "mode": mode_id,
        "mode_label": mode_label,
        "human_players": human_players,
        "ai_players": ai_players,
        "open_human_slots": open_slots,
        "max_players": max_players,
        "occupied_slots": human_players + ai_players,
        "password_protected": bool(get_first_value(raw_lobby, ["password_protected", "passwordProtected", "hasPassword", "has_password"])),
        "has_ai": has_ai,
        "is_aotg": is_aotg,
        "is_public_mp": human_players > 0,
        "is_counted_activity": human_players > 0,
        "activity_type": str(get_first_value(raw_lobby, ["state", "status", "phase", "matchState", "match_state"]) or "unknown"),
        "source": "aomstats",
        "raw": raw_lobby,
    }


def looks_like_lobby(value: dict[str, Any]) -> bool:
    keys = {str(key).lower() for key in value.keys()}
    lobbyish = {
        "lobby",
        "lobbyname",
        "lobby_name",
        "matchid",
        "match_id",
        "advertisement_id",
        "region",
        "map",
        "mapname",
        "gamemode",
        "game_mode",
        "maxplayers",
        "max_players",
        "slots",
        "players",
        "participants",
    }

    return len(keys & lobbyish) >= 2


def extract_lobby_candidates(obj: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 12:
        return []

    if isinstance(obj, list):
        dict_items = [item for item in obj if isinstance(item, dict)]

        if dict_items and sum(1 for item in dict_items if looks_like_lobby(item)) >= max(1, len(dict_items) // 3):
            return dict_items

        candidates: list[dict[str, Any]] = []
        for item in obj:
            candidates.extend(extract_lobby_candidates(item, depth + 1))
        return candidates

    if isinstance(obj, dict):
        for key in ["lobbies", "matches", "data", "rows", "items", "advertisements"]:
            value = obj.get(key)
            if isinstance(value, list):
                candidates = extract_lobby_candidates(value, depth + 1)
                if candidates:
                    return candidates

        candidates = []
        for value in obj.values():
            candidates.extend(extract_lobby_candidates(value, depth + 1))
        return candidates

    return []


def infer_player_count_from_lobby(raw_lobby: dict[str, Any], fallback: int = 0) -> int:
    """Best-effort player count for third-party lobby/ranked data.

    aomstats mixes ranked games, custom games, and open lobbies. Depending on the
    tab/source, the field may be explicit, represented as a list of players, or
    only implied by the ladder label such as "1v1" or "Team".
    """
    explicit_value = get_first_value(
        raw_lobby,
        [
            "human_players",
            "humanPlayers",
            "humans",
            "currentPlayers",
            "current_players",
            "playersCurrent",
            "players_current",
            "occupied_slots",
            "occupiedSlots",
            "playerCount",
            "player_count",
            "numPlayers",
            "num_players",
            "num_players_current",
            "participantsCount",
            "participant_count",
        ],
    )
    explicit = safe_int(explicit_value, default=-1)
    if explicit >= 0:
        return explicit

    for key in ["players", "participants", "members", "matchmembers", "teams"]:
        value = raw_lobby.get(key)
        if isinstance(value, list):
            if key == "teams":
                team_count = 0
                for team in value:
                    if isinstance(team, list):
                        team_count += len(team)
                    elif isinstance(team, dict):
                        inner_players = team.get("players") or team.get("members") or team.get("participants")
                        if isinstance(inner_players, list):
                            team_count += len(inner_players)
                        else:
                            team_count += 1
                    else:
                        team_count += 1
                if team_count > 0:
                    return team_count
            elif value:
                return len(value)

    text_blob = " ".join(
        str(raw_lobby.get(key, ""))
        for key in [
            "ladder",
            "ladderName",
            "ladder_name",
            "matchType",
            "match_type",
            "gameMode",
            "game_mode",
            "mode",
            "name",
            "title",
        ]
    ).lower()

    match = re.search(r"(\d+)\s*v\s*(\d+)", text_blob)
    if match:
        return int(match.group(1)) + int(match.group(2))

    if "ffa" in text_blob:
        match = re.search(r"(\d+)\s*player", text_blob)
        if match:
            return int(match.group(1))

    return fallback


def normalize_aomstats_lobby(raw_lobby: dict[str, Any]) -> dict[str, Any]:
    lobby = normalize_external_lobby(raw_lobby)
    inferred_players = infer_player_count_from_lobby(raw_lobby, fallback=safe_int(lobby.get("human_players")))

    if inferred_players > safe_int(lobby.get("human_players")):
        lobby["human_players"] = inferred_players
        lobby["occupied_slots"] = inferred_players + safe_int(lobby.get("ai_players"))

    # For the activity page, count every live human match/lobby we can see.
    # This intentionally includes full and in-progress matches, because someone
    # in a match is still online and active. Filtering out AI/story/custom modes
    # can be done later as a separate breakdown, but it should not drive the
    # main busyness score.
    lobby["is_public_mp"] = safe_int(lobby.get("human_players")) > 0
    lobby["is_counted_activity"] = safe_int(lobby.get("human_players")) > 0
    lobby["source"] = "aomstats"
    return lobby


def flatten_potential_lobbies(obj: Any, depth: int = 0) -> list[dict[str, Any]]:
    """Find lobby-like dictionaries in normal JSON or SvelteKit/devalue-ish JSON.

    SvelteKit's __data.json is not intended as a stable public API, so this stays
    intentionally defensive: recurse through all objects/lists and then let the
    normalizer decide whether the result is usable.
    """
    if depth > 16:
        return []

    candidates: list[dict[str, Any]] = []

    if isinstance(obj, dict):
        if looks_like_lobby(obj):
            candidates.append(obj)

        for value in obj.values():
            candidates.extend(flatten_potential_lobbies(value, depth + 1))

    elif isinstance(obj, list):
        # Some SvelteKit/devalue payloads flatten object values into lists. We do
        # not try to fully deserialize devalue here, but we still recurse into all
        # nested values so standard object nodes are discovered.
        for item in obj:
            candidates.extend(flatten_potential_lobbies(item, depth + 1))

    return candidates


async def fetch_aomstats_json() -> Any:
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json",
        "Referer": "https://aomstats.io/",
        "Origin": "https://aomstats.io",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # The request Mark captured from the browser/Postman is a POST because
        # curl's --data '' flips the method. Use that first, then fall back to GET.
        response = await client.post(AOMSTATS_LOBBIES_URL, headers=headers, content=b"")
        if response.status_code in {405, 404, 400}:
            response = await client.get(AOMSTATS_LOBBIES_URL, headers=headers)
        response.raise_for_status()
        return response.json()



async def fetch_aomstats_lobby_metadata() -> dict[str, Any]:
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://aomstats.io/lobbies",
        "Origin": "https://aomstats.io",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(AOMSTATS_LOBBIES_METADATA_URL, headers=headers)
        response.raise_for_status()
        return response.json()


def sum_numeric_leaf_values(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)

    if isinstance(value, int | float):
        return int(value)

    if isinstance(value, dict):
        return sum(sum_numeric_leaf_values(child) for child in value.values())

    if isinstance(value, list):
        return sum(sum_numeric_leaf_values(child) for child in value)

    return 0


def build_live_activity_payload_from_metadata(
    metadata_payload: dict[str, Any],
    steam_players_online: int | None = None,
    source: str = "aomstats_metadata",
) -> dict[str, Any]:
    current_time = utc_now()
    lobby_numbers = metadata_payload.get("lobbyNumbers") or {}
    players_in_queue = metadata_payload.get("playersInQueue") or {}
    metadata = metadata_payload.get("metadata") or {}

    custom_lobbies = safe_int(lobby_numbers.get("custom"))
    ranked_lobbies = safe_int(lobby_numbers.get("ranked"))
    joinable_lobbies = safe_int(lobby_numbers.get("joinable"))
    total_lobby_signals = custom_lobbies + ranked_lobbies + joinable_lobbies

    inflated_queue_players = sum_numeric_leaf_values(players_in_queue)
    direct_queue_players = safe_int(players_in_queue.get("num_in_queue"))
    ranked_queue = players_in_queue.get("ranked") if isinstance(players_in_queue.get("ranked"), dict) else {}

    # Metadata exposes reliable game/lobby counts and queue counts, but not a
    # true player count for every in-progress game. For the atlas we use an
    # intentionally visible activity estimate: ranked games are at least 1v1,
    # custom games tend to be partially filled, joinable lobbies have visible
    # players waiting, and the queue value is the direct queue total.
    estimated_custom_players = round(custom_lobbies * 1.35)
    estimated_ranked_players = ranked_lobbies * 2
    estimated_lobby_players = joinable_lobbies
    estimated_players_in_matches = estimated_custom_players + estimated_ranked_players + estimated_lobby_players
    total_tracked_players = estimated_players_in_matches + direct_queue_players

    last_lobby_time = metadata.get("lastLobbyTime")
    generated_at = current_time.isoformat()

    if last_lobby_time not in (None, ""):
        try:
            generated_at = datetime.fromtimestamp(float(last_lobby_time), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            generated_at = current_time.isoformat()

    # The metadata endpoint is global and does not provide a true geographic
    # distribution. The front end treats these as server-area markers, not as a
    # claim that the player count is distributed this way.
    server_region_ids = [
        "us-east",
        "us-west",
        "brazil",
        "europe",
        "asia",
        "australia",
    ]
    regions = [
        {
            "id": region_id,
            "label": REGION_COORDS[region_id]["label"],
            "lat": REGION_COORDS[region_id]["lat"],
            "lon": REGION_COORDS[region_id]["lon"],
            "lobbies": 0,
            "players": 0,
            "intensity": 1,
            "isServerArea": True,
        }
        for region_id in server_region_ids
    ]

    modes = [
        {
            "id": "quickmatch",
            "label": "Quickmatch",
            "lobbies": 0,
            "players": safe_int(players_in_queue.get("num_quickmatch")),
        },
        {
            "id": "ranked",
            "label": "Ranked",
            "lobbies": ranked_lobbies,
            "players": safe_int(players_in_queue.get("num_ranked")),
        },
        {
            "id": "teamqueue",
            "label": "Team queue",
            "lobbies": 0,
            "players": safe_int(players_in_queue.get("num_teamqueue")),
        },
        {
            "id": "ranked_buckets",
            "label": "Ranked ELO buckets",
            "lobbies": 0,
            "players": sum_numeric_leaf_values(ranked_queue),
        },
    ]

    return {
        "generatedAt": generated_at,
        "source": source,
        "metadataRaw": metadata_payload,
        "queue": players_in_queue,
        "lobbyNumbers": lobby_numbers,
        "status": {
            "label": "Live",
            "busynessLabel": "Live now",
            "ratio": None,
            "percentDifference": None,
            "currentPlayersInLobbies": inflated_queue_players,
            "typicalPlayersInLobbies": None,
            "baselineSampleCount": 0,
            "baselineWindowMinutes": 45,
        },
        "summary": {
            "openLobbies": total_lobby_signals,
            "publicMpLobbies": total_lobby_signals,
            "customLobbies": custom_lobbies,
            "customGames": custom_lobbies,
            "rankedLobbies": ranked_lobbies,
            "rankedGames": ranked_lobbies,
            "joinableLobbies": joinable_lobbies,
            "inLobbies": joinable_lobbies,
            "totalGames": total_lobby_signals,
            "activeMatches": ranked_lobbies + custom_lobbies,
            "rankedPlayers": estimated_ranked_players,
            "playersInRanked": estimated_ranked_players,
            "customPlayers": estimated_custom_players,
            "playersInCustom": estimated_custom_players,
            "lobbyPlayers": estimated_lobby_players,
            "joinablePlayers": estimated_lobby_players,
            "playersInMatches": estimated_players_in_matches,
            "playersInGames": estimated_players_in_matches,
            "playersInLobbies": estimated_players_in_matches,
            "activePlayers": total_tracked_players,
            "trackedPlayers": total_tracked_players,
            "totalVisiblePlayers": total_tracked_players,
            "estimatedVisiblePlayers": total_tracked_players,
            "playersInQueue": direct_queue_players,
            "playersInQueueInflated": inflated_queue_players,
            "queueSignals": inflated_queue_players,
            "topRegion": "Worldwide",
            "steamPlayersOnline": steam_players_online,
        },
        "regions": regions,
        "modes": [mode for mode in modes if mode["players"] > 0 or mode["lobbies"] > 0],
    }

async def fetch_aomstats_lobbies() -> list[dict[str, Any]]:
    raw_data = await fetch_aomstats_json()

    candidates = extract_lobby_candidates(raw_data)
    if not candidates:
        candidates = flatten_potential_lobbies(raw_data)

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []

    for candidate in candidates:
        lobby = normalize_aomstats_lobby(candidate)
        unique_key = str(
            lobby.get("id")
            or candidate.get("matchId")
            or candidate.get("match_id")
            or f"{lobby.get('name')}|{lobby.get('region')}|{lobby.get('human_players')}|{lobby.get('max_players')}"
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)
        normalized.append(lobby)

    # If the SvelteKit JSON structure changes and we cannot hydrate useful counts,
    # let /api/activity/live?source=auto fall back to the existing Worlds Edge path.
    if normalized and sum(safe_int(lobby.get("human_players")) for lobby in normalized) == 0:
        return []

    return normalized

async def fetch_steam_current_players() -> int | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                STEAM_CURRENT_PLAYERS_URL,
                params={"appid": AOM_RETOLD_STEAM_APP_ID},
                headers={"User-Agent": "AoMRetoldLobbyBrowser/0.10.0"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return None

    return safe_int(data.get("response", {}).get("player_count"), default=None)  # type: ignore[arg-type]


def normalize_local_lobby(lobby: dict[str, Any]) -> dict[str, Any]:
    region_id, region_label, lat, lon = normalize_region(lobby.get("region") or lobby.get("relay_region"))
    mode_id, mode_label = normalize_mode(lobby.get("game_mode") or lobby.get("game_type"), lobby.get("name"), lobby.get("map"))
    human_players = safe_int(lobby.get("human_players"))
    ai_players = safe_int(lobby.get("ai_players"))
    open_slots = safe_int(lobby.get("open_human_slots"))
    name = str(lobby.get("name") or "Unnamed lobby")
    map_name = str(lobby.get("map") or "Unknown")
    text_blob = f"{name} {map_name} {mode_label}".lower()
    is_aotg = "arena of the gods" in text_blob or "aotg" in text_blob

    return {
        "id": lobby.get("id"),
        "name": name,
        "region": region_id,
        "region_label": region_label,
        "lat": lat,
        "lon": lon,
        "map": map_name,
        "mode": mode_id,
        "mode_label": mode_label,
        "human_players": human_players,
        "ai_players": ai_players,
        "open_human_slots": open_slots,
        "max_players": safe_int(lobby.get("max_players_configured") or lobby.get("max_players_raw"), human_players + ai_players + open_slots),
        "occupied_slots": safe_int(lobby.get("occupied_slots"), human_players + ai_players),
        "password_protected": bool(lobby.get("password_protected")),
        "has_ai": ai_players > 0,
        "is_aotg": is_aotg,
        "is_public_mp": human_players > 0,
        "is_counted_activity": human_players > 0,
        "activity_type": str(lobby.get("state") or lobby.get("status") or "lobby"),
        "source": "worldsedge",
    }


def get_busyness_label(ratio: float | None) -> str:
    if ratio is None:
        return "Collecting baseline"
    if ratio < 0.5:
        return "Very quiet"
    if ratio < 0.8:
        return "Quiet"
    if ratio <= 1.2:
        return "Typical"
    if ratio <= 1.6:
        return "Busier than usual"
    return "Very busy"


def init_activity_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                open_lobbies INTEGER NOT NULL,
                public_mp_lobbies INTEGER NOT NULL,
                players_in_lobbies INTEGER NOT NULL,
                steam_players_online INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_region_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                region TEXT NOT NULL,
                region_label TEXT NOT NULL,
                lobbies INTEGER NOT NULL,
                players INTEGER NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_mode_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                mode_label TEXT NOT NULL,
                lobbies INTEGER NOT NULL,
                players INTEGER NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id)
            )
            """
        )


def get_typical_players(current_time: datetime, window_minutes: int = 45, min_samples: int = 8) -> dict[str, Any]:
    init_activity_db()
    current_weekday = current_time.weekday()
    current_minute = current_time.hour * 60 + current_time.minute
    earliest = current_time - timedelta(days=35)

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT created_at, players_in_lobbies
            FROM activity_snapshots
            WHERE created_at >= ?
            ORDER BY created_at DESC
            """,
            (earliest.isoformat(),),
        ).fetchall()

    samples = []

    for row in rows:
        try:
            sample_time = datetime.fromisoformat(row["created_at"])
        except ValueError:
            continue

        if sample_time.tzinfo is None:
            sample_time = sample_time.replace(tzinfo=timezone.utc)

        if sample_time.weekday() != current_weekday:
            continue

        sample_minute = sample_time.hour * 60 + sample_time.minute
        minute_delta = abs(sample_minute - current_minute)
        minute_delta = min(minute_delta, 1440 - minute_delta)

        if minute_delta <= window_minutes:
            samples.append(int(row["players_in_lobbies"]))

    if len(samples) < min_samples:
        return {
            "typicalPlayersInLobbies": None,
            "baselineSampleCount": len(samples),
            "baselineWindowMinutes": window_minutes,
        }

    typical = round(sum(samples) / len(samples))

    return {
        "typicalPlayersInLobbies": typical,
        "baselineSampleCount": len(samples),
        "baselineWindowMinutes": window_minutes,
    }


def save_activity_snapshot(payload: dict[str, Any]) -> int:
    init_activity_db()

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO activity_snapshots (
                created_at,
                source,
                open_lobbies,
                public_mp_lobbies,
                players_in_lobbies,
                steam_players_online
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload["generatedAt"],
                payload.get("source", "unknown"),
                payload["summary"]["openLobbies"],
                payload["summary"]["publicMpLobbies"],
                payload["summary"]["playersInLobbies"],
                payload["summary"].get("steamPlayersOnline"),
            ),
        )
        snapshot_id = int(cursor.lastrowid)

        for region in payload.get("regions", []):
            connection.execute(
                """
                INSERT INTO activity_region_snapshots (
                    snapshot_id,
                    region,
                    region_label,
                    lobbies,
                    players
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    region["id"],
                    region["label"],
                    region["lobbies"],
                    region["players"],
                ),
            )

        for mode in payload.get("modes", []):
            connection.execute(
                """
                INSERT INTO activity_mode_snapshots (
                    snapshot_id,
                    mode,
                    mode_label,
                    lobbies,
                    players
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    mode["id"],
                    mode["label"],
                    mode["lobbies"],
                    mode["players"],
                ),
            )

    return snapshot_id


def build_live_activity_payload(
    lobbies: list[dict[str, Any]],
    steam_players_online: int | None = None,
    source: str = "unknown",
    saved_snapshot_id: int | None = None,
) -> dict[str, Any]:
    current_time = utc_now()
    counted_activity = [
        lobby
        for lobby in lobbies
        if lobby.get("is_counted_activity", lobby.get("is_public_mp"))
    ]

    open_lobbies = len(lobbies)
    public_mp_lobbies = len(counted_activity)
    players_in_lobbies = sum(safe_int(lobby.get("human_players")) for lobby in counted_activity)

    region_groups: dict[str, dict[str, Any]] = {}
    mode_counts: dict[str, dict[str, Any]] = {}

    for lobby in counted_activity:
        region_id = str(lobby.get("region") or "unknown")
        region_label = str(lobby.get("region_label") or region_id)
        region = region_groups.setdefault(
            region_id,
            {
                "id": region_id,
                "label": region_label,
                "lat": lobby.get("lat", REGION_COORDS.get(region_id, REGION_COORDS["unknown"])["lat"]),
                "lon": lobby.get("lon", REGION_COORDS.get(region_id, REGION_COORDS["unknown"])["lon"]),
                "lobbies": 0,
                "players": 0,
            },
        )
        region["lobbies"] += 1
        region["players"] += safe_int(lobby.get("human_players"))

        mode_id = str(lobby.get("mode") or "unknown")
        mode = mode_counts.setdefault(
            mode_id,
            {
                "id": mode_id,
                "label": str(lobby.get("mode_label") or MODE_LABELS.get(mode_id, mode_id.title())),
                "lobbies": 0,
                "players": 0,
            },
        )
        mode["lobbies"] += 1
        mode["players"] += safe_int(lobby.get("human_players"))

    max_region_players = max([region["players"] for region in region_groups.values()] or [0])
    regions = []

    for region in region_groups.values():
        intensity = 0.0 if max_region_players <= 0 else region["players"] / max_region_players
        regions.append({**region, "intensity": round(intensity, 3)})

    regions.sort(key=lambda region: (region["players"], region["lobbies"]), reverse=True)
    modes = sorted(mode_counts.values(), key=lambda mode: (mode["players"], mode["lobbies"]), reverse=True)

    typical = get_typical_players(current_time)
    typical_players = typical.get("typicalPlayersInLobbies")
    ratio = None
    percent_difference = None

    if typical_players and typical_players > 0:
        ratio = players_in_lobbies / typical_players
        percent_difference = round((ratio - 1) * 100)

    busyness_label = get_busyness_label(ratio)
    top_region = regions[0]["label"] if regions else None

    return {
        "generatedAt": current_time.isoformat(),
        "source": source,
        "savedSnapshotId": saved_snapshot_id,
        "status": {
            "label": "Live",
            "busynessLabel": busyness_label,
            "ratio": round(ratio, 3) if ratio is not None else None,
            "percentDifference": percent_difference,
            "currentPlayersInLobbies": players_in_lobbies,
            "typicalPlayersInLobbies": typical_players,
            "baselineSampleCount": typical.get("baselineSampleCount", 0),
            "baselineWindowMinutes": typical.get("baselineWindowMinutes", 45),
        },
        "summary": {
            "openLobbies": open_lobbies,
            "publicMpLobbies": public_mp_lobbies,
            "activeMatches": public_mp_lobbies,
            "playersInLobbies": players_in_lobbies,
            "activePlayers": players_in_lobbies,
            "topRegion": top_region,
            "steamPlayersOnline": steam_players_online,
        },
        "regions": regions,
        "modes": modes,
    }
