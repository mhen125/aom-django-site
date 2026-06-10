import time
from collections import defaultdict

import requests


AOMSTATS_RANKED_LOBBIES_URL = "https://aomstats.io/api/lobbies"
AOMSTATS_CUSTOM_LOBBIES_URL = "https://aomstats.io/api/lobbies/customs"

CACHE_SECONDS = 15

_ranked_cache = {
    "timestamp": 0,
    "matches": [],
}

_custom_cache = {
    "timestamp": 0,
    "matches": [],
}


BASE_AOMSTATS_HEADERS = {
    "accept": "*/*",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua-platform": '"macOS"',
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "dnt": "1",
}


MATCH_ID_KEYS = [
    "match_id",
    "matchId",
    "matchid",
    "id",
    "game_id",
    "gameId",
    "lobby_id",
    "lobbyId",
]

PLAYER_NAME_KEYS = [
    "alias",
    "name",
    "username",
    "player_name",
    "playerName",
    "gamertag",
    "steam_name",
]

PLAYER_ID_KEYS = [
    "profile_id",
    "profileId",
    "profileid",
    "rl_profile_id",
    "relicProfileId",
    "player_id",
    "playerId",
]

PLAYER_RATING_KEYS = [
    "rating",
    "elo",
    "ranked_rating",
    "rankedRating",
    "mmr",
    "leaderboard_rating",
]

PLAYER_GOD_KEYS = [
    "god",
    "god_name",
    "godName",
    "major_god",
    "majorGod",
    "civ",
    "civilization",
    "race",
    "raceName",
]

PLAYER_TEAM_KEYS = [
    "team",
    "teamid",
    "team_id",
    "teamId",
]


def _safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default

        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_str(value, default=""):
    if value is None:
        return default

    return str(value)


def _get_first(item, keys, default=None):
    if not isinstance(item, dict):
        return default

    for key in keys:
        if key in item and item.get(key) is not None:
            return item.get(key)

    return default


def _extract_list_payload(payload):
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    for key in (
        "lobbies",
        "matches",
        "games",
        "data",
        "items",
        "results",
    ):
        value = payload.get(key)

        if isinstance(value, list):
            return value

    return []


def _has_embedded_players(raw_match):
    if not isinstance(raw_match, dict):
        return False

    for key in ("players", "participants", "members", "slots"):
        if isinstance(raw_match.get(key), list):
            return True

    if isinstance(raw_match.get("teams"), dict):
        return True

    return False


def _looks_like_player_row(row):
    if not isinstance(row, dict):
        return False

    player_keys = set(
        PLAYER_NAME_KEYS
        + PLAYER_ID_KEYS
        + PLAYER_RATING_KEYS
        + PLAYER_GOD_KEYS
        + PLAYER_TEAM_KEYS
    )

    return any(key in row for key in player_keys)


def _normalize_player(raw_player, fallback_index=0):
    if not isinstance(raw_player, dict):
        return {
            "alias": f"Player {fallback_index + 1}",
            "profile_id": None,
            "rating": 1000,
            "team": 0,
            "god": "Unknown",
            "country": "",
            "platform": "",
        }

    alias = _get_first(
        raw_player,
        PLAYER_NAME_KEYS,
        f"Player {fallback_index + 1}",
    )

    profile_id = _get_first(
        raw_player,
        PLAYER_ID_KEYS,
        None,
    )

    rating = _safe_int(
        _get_first(
            raw_player,
            PLAYER_RATING_KEYS,
            1000,
        ),
        1000,
    )

    if rating <= 0:
        rating = 1000

    team = _get_first(
        raw_player,
        PLAYER_TEAM_KEYS,
        0,
    )

    god = _get_first(
        raw_player,
        PLAYER_GOD_KEYS,
        "Unknown",
    )

    return {
        "alias": _safe_str(alias, f"Player {fallback_index + 1}"),
        "profile_id": profile_id,
        "rating": rating,
        "team": team,
        "god": _safe_str(god, "Unknown"),
        "country": _safe_str(
            _get_first(raw_player, ["country", "country_code", "countryCode"], "")
        ),
        "platform": _safe_str(
            _get_first(raw_player, ["platform", "platformName"], "")
        ),
    }


def _extract_players_from_embedded_match(raw_match):
    if not isinstance(raw_match, dict):
        return []

    player_list = _get_first(
        raw_match,
        [
            "players",
            "participants",
            "members",
            "slots",
        ],
        [],
    )

    if isinstance(player_list, list):
        return [
            _normalize_player(player, index)
            for index, player in enumerate(player_list)
        ]

    teams = raw_match.get("teams")

    if isinstance(teams, dict):
        players = []

        for team_key, team_players in teams.items():
            if not isinstance(team_players, list):
                continue

            for player in team_players:
                normalized = _normalize_player(player, len(players))
                normalized["team"] = team_key
                players.append(normalized)

        return players

    return []


def _extract_players_from_flat_rows(rows):
    players = []

    for row in rows:
        if not _looks_like_player_row(row):
            continue

        players.append(_normalize_player(row, len(players)))

    return players


def _build_teams(players):
    teams = defaultdict(list)

    for player in players:
        team = player.get("team", 0)
        teams[str(team)].append(player)

    return dict(teams)


def _get_match_id(raw_match, fallback=None):
    match_id = _get_first(raw_match, MATCH_ID_KEYS, None)

    if match_id is not None:
        return match_id

    if fallback is not None:
        return fallback

    title_fallback = _get_first(
        raw_match,
        ["title", "name", "lobbyName"],
        "Unknown",
    )
    start_fallback = _get_first(
        raw_match,
        ["startgametime", "start_time", "startedAt"],
        "",
    )

    return f"{title_fallback}-{start_fallback}"


def _normalize_title(raw_match, source):
    title = _get_first(
        raw_match,
        [
            "title",
            "name",
            "lobby_name",
            "lobbyName",
            "match_name",
            "matchName",
        ],
        None,
    )

    title = _safe_str(title, "").strip()

    if source == "ranked":
        if not title or title.upper() in {"AUTOMATCH", "RANKED"}:
            return "AUTOMATCH"

        return title

    if not title or title.upper() in {"AUTOMATCH", "RANKED"}:
        return "Custom Match"

    return title


def _normalize_match_base(raw_match, players, source, fallback_match_id=None):
    if not isinstance(raw_match, dict):
        return None

    match_id = _get_match_id(raw_match, fallback=fallback_match_id)

    map_name = _get_first(
        raw_match,
        [
            "mapname",
            "mapName",
            "map",
            "map_name",
            "scenario",
        ],
        "Unknown",
    )

    server = _get_first(
        raw_match,
        [
            "server",
            "region",
            "serverregion",
            "serverRegion",
            "relay_region",
            "relayRegion",
        ],
        "Unknown",
    )

    startgametime = _get_first(
        raw_match,
        [
            "startgametime",
            "startGameTime",
            "start_time",
            "startTime",
            "started_at",
            "startedAt",
            "created_at",
            "createdAt",
        ],
        None,
    )

    spectators = _safe_int(
        _get_first(
            raw_match,
            [
                "spectators",
                "observer_count",
                "observerCount",
                "observers",
                "num_observers",
                "numObservers",
            ],
            0,
        ),
        0,
    )

    leaderboard_id = _safe_int(
        _get_first(
            raw_match,
            [
                "leaderboard_id",
                "leaderboardId",
                "leaderboard",
            ],
            0,
        ),
        0,
    )

    matchtype_id = _safe_int(
        _get_first(
            raw_match,
            [
                "matchtype_id",
                "matchTypeId",
                "matchtype",
                "match_type",
            ],
            0,
        ),
        0,
    )

    return {
        "match_id": match_id,
        "source": source,
        "title": _normalize_title(raw_match, source),
        "mapname": _safe_str(map_name, "Unknown"),
        "server": _safe_str(server, "Unknown"),
        "startgametime": startgametime,
        "spectators": spectators,
        "leaderboard_id": leaderboard_id,
        "matchtype_id": matchtype_id,
        "joinable": bool(_get_first(raw_match, ["joinable", "isJoinable"], False)),
        "password_protected": bool(
            _get_first(
                raw_match,
                [
                    "password_protected",
                    "passwordProtected",
                    "hasPassword",
                ],
                False,
            )
        ),
        "player_count": len(players),
        "players": players,
        "teams": _build_teams(players),
        "raw": raw_match,
    }


def _normalize_embedded_match(raw_match, source="ranked"):
    players = _extract_players_from_embedded_match(raw_match)
    return _normalize_match_base(raw_match, players, source)


def _normalize_flat_group(match_id, rows, source="ranked"):
    if not rows:
        return None

    first_row = rows[0]
    players = _extract_players_from_flat_rows(rows)

    return _normalize_match_base(
        first_row,
        players,
        source,
        fallback_match_id=match_id,
    )


def _normalize_aomstats_payload(raw_matches, source):
    if not isinstance(raw_matches, list):
        return []

    if not raw_matches:
        return []

    has_embedded_matches = any(_has_embedded_players(item) for item in raw_matches)

    if has_embedded_matches:
        normalized = []

        for raw_match in raw_matches:
            match = _normalize_embedded_match(raw_match, source=source)

            if match:
                normalized.append(match)

        return normalized

    grouped_rows = defaultdict(list)

    for index, row in enumerate(raw_matches):
        if not isinstance(row, dict):
            continue

        match_id = _get_match_id(row, fallback=f"{source}-{index}")

        grouped_rows[str(match_id)].append(row)

    normalized = []

    for match_id, rows in grouped_rows.items():
        match = _normalize_flat_group(match_id, rows, source=source)

        if match:
            normalized.append(match)

    return normalized


def _fetch_aomstats_matches(url, source):
    headers = dict(BASE_AOMSTATS_HEADERS)

    if source == "custom":
        headers["referer"] = "https://aomstats.io/lobbies/customs"
    else:
        headers["referer"] = "https://aomstats.io/lobbies"

    response = requests.get(url, headers=headers, timeout=12)
    response.raise_for_status()

    payload = response.json()
    raw_matches = _extract_list_payload(payload)

    return _normalize_aomstats_payload(raw_matches, source=source)


def get_active_ranked_matches(force_refresh=False):
    now = time.time()

    if (
        not force_refresh
        and _ranked_cache["matches"]
        and now - _ranked_cache["timestamp"] < CACHE_SECONDS
    ):
        return _ranked_cache["matches"]

    matches = _fetch_aomstats_matches(
        AOMSTATS_RANKED_LOBBIES_URL,
        source="ranked",
    )

    _ranked_cache["timestamp"] = now
    _ranked_cache["matches"] = matches

    return matches


def get_active_custom_matches(force_refresh=False):
    now = time.time()

    if (
        not force_refresh
        and _custom_cache["matches"]
        and now - _custom_cache["timestamp"] < CACHE_SECONDS
    ):
        return _custom_cache["matches"]

    matches = _fetch_aomstats_matches(
        AOMSTATS_CUSTOM_LOBBIES_URL,
        source="custom",
    )

    _custom_cache["timestamp"] = now
    _custom_cache["matches"] = matches

    return matches