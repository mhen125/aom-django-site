import base64
import gzip
import json
import re
import shutil
import subprocess
import time
import zlib
from datetime import datetime, timezone
from typing import Any

import httpx

from .leaderboard_metadata import (
    get_match_type_ids_for_leaderboard,
    get_match_type_label,
    get_queue_label,
    get_ranked_queues,
    get_ranked_match_type_ids,
    resolve_community_civilization_name,
    resolve_legacy_race_name,
)
from .normalizer import format_map_name


class UpstreamLeaderboardError(Exception):
    pass


LEADERBOARD_URL = "https://api.ageofempires.com/api/agemyth/Leaderboard"
FULL_STATS_URL = "https://api.ageofempires.com/api/GameStats/AgeMyth/GetFullStats"
MATCH_LIST_URL = "https://api.ageofempires.com/api/GameStats/AgeMyth/GetMatchList"
MATCH_DETAIL_URL = "https://api.ageofempires.com/api/GameStats/AgeMyth/GetMatchDetail"
COMMUNITY_LEADERBOARD2_URL = "https://andromeda-live-release18-api.worldsedgelink.com/community/leaderboard/getLeaderboard2"
COMMUNITY_RECENT_MATCH_HISTORY_URL = "https://athens-live-api.worldsedgelink.com/community/Leaderboard/getRecentMatchHistory"


AVATAR_STAT_FOR_PROFILE_URL = "https://athens-live-api.worldsedgelink.com/community/leaderboard/GetAvatarStatForProfile"
PERSONAL_STAT_URL = "https://athens-live-api.worldsedgelink.com/community/leaderboard/GetPersonalStat"


def normalize_platform_profile_name(platform: str, platform_id: str) -> str:
    platform_key = str(platform or "").strip().lower().replace("_", "-")
    platform_value = str(platform_id or "").strip()

    if not platform_key or not platform_value:
        return ""

    aliases = {
        "steamid": "steam",
        "steam-id": "steam",
        "steam": "steam",
        "xbox": "xbox",
        "xuid": "xbox",
        "xboxlive": "xbox",
        "xbox-live": "xbox",
    }

    normalized_platform = aliases.get(platform_key, platform_key)
    return f"/{normalized_platform}/{platform_value}"


def resolve_profile_id_from_platform_sync(
    *,
    platform: str,
    platform_id: str,
    timeout_seconds: int = 12,
) -> dict[str, Any]:
    """Resolve a platform account into a Worlds Edge/AoM profile_id.

    Worlds Edge community endpoints expect slash-prefixed profile names such as
    /steam/<steam_id>. Xbox accounts should use /xbox/<xuid>.
    """
    profile_name = normalize_platform_profile_name(platform, platform_id)

    if not profile_name:
        return {
            "ok": False,
            "profile_name": profile_name,
            "profile_id": None,
            "error": "Missing platform or platform_id.",
            "raw": None,
        }

    params = {
        "title": "athens",
        "profile_names": json.dumps([profile_name]),
    }

    try:
        response = httpx.get(
            AVATAR_STAT_FOR_PROFILE_URL,
            params=params,
            headers={
                "accept": "application/json",
                "user-agent": "curl/8.7.1",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "ok": False,
            "profile_name": profile_name,
            "profile_id": None,
            "error": str(exc),
            "raw": None,
        }

    avatar_stats = payload.get("avatarStatsForProfile") if isinstance(payload, dict) else None
    profile_id = None

    if isinstance(avatar_stats, list):
        for item in avatar_stats:
            if not isinstance(item, dict):
                continue
            profile_id = to_int_or_none(item.get("profile_id") or item.get("profileId"))
            if profile_id is not None:
                break

    result = payload.get("result") if isinstance(payload, dict) else {}
    message = result.get("message") if isinstance(result, dict) else ""

    return {
        "ok": profile_id is not None,
        "profile_name": profile_name,
        "profile_id": profile_id,
        "message": message,
        "raw": payload,
    }


def extract_alias_from_personal_stat_sync(
    *,
    profile_id: int,
    timeout_seconds: int = 12,
) -> dict[str, Any]:
    """Resolve the real AoM alias from a Worlds Edge profile_id.

    GetAvatarStatForProfile gives us the bridge from /steam/<id> or /xbox/<xuid>
    to profile_id. GetPersonalStat with profile_ids gives us the member alias
    such as "<color...>Shake Zula".
    """
    params = {
        "title": "athens",
        "profile_ids": json.dumps([str(profile_id)]),
    }

    try:
        response = httpx.get(
            PERSONAL_STAT_URL,
            params=params,
            headers={
                "accept": "application/json",
                "user-agent": "curl/8.7.1",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "ok": False,
            "profile_id": profile_id,
            "alias": "",
            "avatar_url": "",
            "error": str(exc),
            "raw": None,
        }

    alias = ""
    platform_name = ""
    country = ""
    clan = ""

    if isinstance(payload, dict):
        stat_groups = payload.get("statGroups") or []
        if isinstance(stat_groups, list):
            for group in stat_groups:
                if not isinstance(group, dict):
                    continue

                members = group.get("members") or []
                if not isinstance(members, list):
                    continue

                for member in members:
                    if not isinstance(member, dict):
                        continue

                    member_profile_id = to_int_or_none(member.get("profile_id") or member.get("profileId"))
                    if member_profile_id != int(profile_id):
                        continue

                    alias = clean_leaderboard_name(member.get("alias"))
                    platform_name = str(member.get("name") or "")
                    country = str(member.get("country") or "")
                    clan = str(member.get("clanlist_name") or "")
                    break

                if alias:
                    break

    result = payload.get("result") if isinstance(payload, dict) else {}
    message = result.get("message") if isinstance(result, dict) else ""

    return {
        "ok": bool(alias),
        "profile_id": int(profile_id),
        "alias": alias,
        "avatar_url": "",
        "platform_name": platform_name,
        "country": country,
        "clan": clan,
        "message": message,
        "raw": payload,
    }


def extract_alias_from_full_stats_sync(
    *,
    profile_id: int,
    fallback_name: str = "unknown user",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Best-effort profile alias lookup from the existing FullStats endpoint."""
    body = build_full_stats_body(
        profile_id=profile_id,
        gamertag=fallback_name or "unknown user",
        match_types=get_ranked_match_type_ids(),
    )

    response = post_json_with_curl(
        url=FULL_STATS_URL,
        body=body,
        label="full_stats_profile_alias",
        timeout_seconds=timeout_seconds,
    )

    records = collect_stat_records(response.get("raw"))
    best = pick_best_full_stats_record(
        records,
        profile_id=profile_id,
        player=fallback_name,
        requested_match_type=1,
    )

    alias = ""
    avatar_url = ""

    if isinstance(best, dict):
        alias = clean_leaderboard_name(best.get("name"))
        avatar_url = str(best.get("avatar_url") or "")

    return {
        "ok": bool(alias),
        "profile_id": profile_id,
        "alias": alias,
        "avatar_url": avatar_url,
        "raw_response_ok": bool(response.get("ok")),
        "status_code": response.get("status_code"),
        "record_count": len(records),
    }


def resolve_worldsedge_identity_sync(
    *,
    platform: str,
    platform_id: str,
    fallback_name: str = "unknown user",
) -> dict[str, Any]:
    """Resolve Steam/Xbox platform id to AoM profile_id and display alias."""
    profile_result = resolve_profile_id_from_platform_sync(
        platform=platform,
        platform_id=platform_id,
    )

    if not profile_result.get("ok") or profile_result.get("profile_id") is None:
        return {
            **profile_result,
            "alias": "",
            "avatar_url": "",
            "alias_result": None,
        }

    profile_id = int(profile_result["profile_id"])

    personal_stat_result = extract_alias_from_personal_stat_sync(profile_id=profile_id)
    alias_result = personal_stat_result

    if not alias_result.get("ok"):
        alias_result = extract_alias_from_full_stats_sync(
            profile_id=profile_id,
            fallback_name=fallback_name,
        )

    return {
        **profile_result,
        "alias": alias_result.get("alias") or "",
        "avatar_url": alias_result.get("avatar_url") or "",
        "alias_result": alias_result,
        "personal_stat_result": personal_stat_result,
    }
LEADERBOARD_CACHE_SECONDS = 300

_leaderboard_cache: dict[tuple[Any, ...], dict[str, Any]] = {}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_source_meta(
    *,
    endpoint: str,
    queue_id: int | None = None,
    expanded_match_type_ids: list[int] | None = None,
    cached: Any = None,
    status_code: Any = None,
    source: str | None = None,
) -> dict[str, Any]:
    return {
        "source": source or endpoint,
        "endpoint": endpoint,
        "queue_id": queue_id,
        "queue_label": get_queue_label(queue_id) if queue_id is not None else None,
        "expanded_match_type_ids": expanded_match_type_ids or [],
        "cached": bool(cached),
        "status_code": status_code,
        "fetched_at": utc_timestamp(),
    }


def build_leaderboard_body(
    *,
    player: str = "",
    region: int = 7,
    match_type: int = 1,
    console_match_type: int = 15,
    page: int = 1,
    count: int = 100,
    sort_column: str = "rank",
    sort_direction: str = "ASC",
) -> dict[str, Any]:
    return {
        "region": int(region),
        "matchType": int(match_type),
        "consoleMatchType": int(console_match_type),
        "searchPlayer": str(player or ""),
        "page": int(page),
        "count": int(count),
        "sortColumn": str(sort_column or "rank"),
        "sortDirection": str(sort_direction or "ASC").upper(),
    }


def build_leaderboard_headers() -> dict[str, str]:
    # This intentionally mirrors the minimal curl that works:
    #   accept: application/json
    #   content-type: application/json
    # No Cookie header.
    #
    # The User-Agent is included because some services return different results
    # for Python/httpx default user agents even when curl succeeds.
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "curl/8.7.1",
    }


def get_cache_key(body: dict[str, Any]) -> tuple[Any, ...]:
    return (
        body["region"],
        body["matchType"],
        body["consoleMatchType"],
        body["searchPlayer"].casefold(),
        body["page"],
        body["count"],
        body["sortColumn"],
        body["sortDirection"],
    )


def try_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "_non_json_response": text,
        }


def extract_candidate_lists(value: Any) -> list[list[Any]]:
    lists: list[list[Any]] = []

    if isinstance(value, list):
        lists.append(value)
        for item in value:
            lists.extend(extract_candidate_lists(item))
    elif isinstance(value, dict):
        for child in value.values():
            lists.extend(extract_candidate_lists(child))

    return lists


def summarize_payload_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        candidate_lists = extract_candidate_lists(value)
        largest_lists = sorted(
            [
                {
                    "length": len(item),
                    "first_item_type": type(item[0]).__name__ if item else None,
                    "first_item_keys": list(item[0].keys())[:30] if item and isinstance(item[0], dict) else None,
                }
                for item in candidate_lists
            ],
            key=lambda item: item["length"],
            reverse=True,
        )[:5]

        return {
            "type": "dict",
            "top_level_keys": list(value.keys()),
            "largest_lists": largest_lists,
        }

    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first_item_type": type(value[0]).__name__ if value else None,
            "first_item_keys": list(value[0].keys())[:30] if value and isinstance(value[0], dict) else None,
        }

    return {
        "type": type(value).__name__,
    }


async def post_with_httpx(body: dict[str, Any]) -> dict[str, Any]:
    headers = build_leaderboard_headers()

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        # Use content=json.dumps(...) instead of json=... so the request is as
        # close as possible to curl --data 'json here'.
        response = await client.post(
            LEADERBOARD_URL,
            headers=headers,
            content=json.dumps(body),
        )

    raw_text = response.text
    parsed = try_parse_json(raw_text)

    return {
        "transport": "httpx",
        "request": {
            "url": LEADERBOARD_URL,
            "headers": headers,
            "body": body,
        },
        "status_code": response.status_code,
        "ok": response.is_success,
        "response_headers": dict(response.headers),
        "text_length": len(raw_text),
        "text_preview": raw_text[:1000],
        "shape": summarize_payload_shape(parsed),
        "raw": parsed,
    }


def post_with_curl(body: dict[str, Any]) -> dict[str, Any]:
    return post_json_with_curl(
        url=LEADERBOARD_URL,
        body=body,
        label="leaderboard",
        timeout_seconds=30,
    )


def post_json_with_curl(
    *,
    url: str,
    body: dict[str, Any],
    label: str,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    curl_path = shutil.which("curl")
    if not curl_path:
        return {
            "transport": "curl",
            "ok": False,
            "status_code": None,
            "error": "curl executable was not found on this system.",
            "raw": None,
        }

    body_text = json.dumps(body)

    command = [
        curl_path,
        "--silent",
        "--show-error",
        "--location",
        "--write-out",
        "\n__HTTP_STATUS__:%{http_code}",
        url,
        "--header",
        "accept: application/json",
        "--header",
        "content-type: application/json",
        "--data",
        body_text,
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""

    status_code = None
    response_text = stdout

    marker = "\n__HTTP_STATUS__:"
    if marker in stdout:
        response_text, status_text = stdout.rsplit(marker, 1)
        try:
            status_code = int(status_text.strip())
        except ValueError:
            status_code = None

    parsed = try_parse_json(response_text)

    return {
        "transport": "curl",
        "endpoint": label,
        "request": {
            "url": url,
            "headers": {
                "accept": "application/json",
                "content-type": "application/json",
            },
            "body": body,
            "command_preview": (
                "curl --location '" + url + "' "
                "--header 'accept: application/json' "
                "--header 'content-type: application/json' "
                "--data '" + body_text + "'"
            ),
        },
        "status_code": status_code,
        "ok": completed.returncode == 0 and status_code is not None and 200 <= status_code < 300,
        "return_code": completed.returncode,
        "stderr": stderr,
        "text_length": len(response_text),
        "text_preview": response_text[:1000],
        "shape": summarize_payload_shape(parsed),
        "raw": parsed,
    }


def get_json_with_curl(
    *,
    url: str,
    params: dict[str, Any],
    label: str,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    curl_path = shutil.which("curl")
    if not curl_path:
        return {
            "transport": "curl",
            "ok": False,
            "status_code": None,
            "error": "curl executable was not found on this system.",
            "raw": None,
        }

    request_url = f"{url}?{httpx.QueryParams(params)}" if params else url

    command = [
        curl_path,
        "--silent",
        "--show-error",
        "--location",
        "--write-out",
        "\n__HTTP_STATUS__:%{http_code}",
        request_url,
        "--header",
        "accept: application/json",
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""

    status_code = None
    response_text = stdout

    marker = "\n__HTTP_STATUS__:"
    if marker in stdout:
        response_text, status_text = stdout.rsplit(marker, 1)
        try:
            status_code = int(status_text.strip())
        except ValueError:
            status_code = None

    parsed = try_parse_json(response_text)

    return {
        "transport": "curl",
        "endpoint": label,
        "request": {
            "url": request_url,
            "headers": {
                "accept": "application/json",
            },
            "params": params,
            "command_preview": (
                "curl --location '" + request_url + "' "
                "--header 'accept: application/json'"
            ),
        },
        "status_code": status_code,
        "ok": completed.returncode == 0 and status_code is not None and 200 <= status_code < 300,
        "return_code": completed.returncode,
        "stderr": stderr,
        "text_length": len(response_text),
        "text_preview": response_text[:1000],
        "shape": summarize_payload_shape(parsed),
        "raw": parsed,
    }


def payload_has_any_rows(payload: Any) -> bool:
    if isinstance(payload, list):
        return len(payload) > 0

    if isinstance(payload, dict):
        for candidate in extract_candidate_lists(payload):
            if len(candidate) > 0:
                return True

    return False


async def fetch_leaderboard_raw(
    *,
    player: str = "",
    region: int = 7,
    match_type: int = 1,
    console_match_type: int = 15,
    page: int = 1,
    count: int = 100,
    sort_column: str = "rank",
    sort_direction: str = "ASC",
    refresh: bool = False,
    force_transport: str = "auto",
) -> dict[str, Any]:
    body = build_leaderboard_body(
        player=player,
        region=region,
        match_type=match_type,
        console_match_type=console_match_type,
        page=page,
        count=count,
        sort_column=sort_column,
        sort_direction=sort_direction,
    )

    cache_key = get_cache_key(body) + (force_transport,)
    now = time.time()

    cached = _leaderboard_cache.get(cache_key)
    if (
        not refresh
        and cached is not None
        and now - float(cached.get("created_at", 0)) < LEADERBOARD_CACHE_SECONDS
    ):
        payload = dict(cached["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(
            now - float(cached["created_at"]), 2)
        return payload

    result: dict[str, Any]

    if force_transport == "curl":
        result = post_with_curl(body)
    else:
        try:
            result = await post_with_httpx(body)
        except httpx.HTTPError as error:
            if force_transport == "httpx":
                raise UpstreamLeaderboardError(
                    f"Failed to contact Age of Empires leaderboard API with httpx: {error}"
                ) from error

            result = {
                "transport": "httpx",
                "ok": False,
                "status_code": None,
                "error": str(error),
                "raw": None,
            }

        # Auto fallback: if httpx succeeds but returns no rows, try the local
        # curl binary because we know the user's direct curl works.
        if (
            force_transport == "auto"
            and (
                not result.get("ok")
                or not payload_has_any_rows(result.get("raw"))
            )
        ):
            curl_result = post_with_curl(body)
            result = {
                "transport": "auto",
                "selected_transport": "curl" if curl_result.get("ok") else result.get("transport"),
                "httpx_attempt": result,
                "curl_attempt": curl_result,
                "request": curl_result.get("request") or result.get("request"),
                "status_code": curl_result.get("status_code") if curl_result.get("ok") else result.get("status_code"),
                "ok": bool(curl_result.get("ok") or result.get("ok")),
                "raw": curl_result.get("raw") if curl_result.get("ok") else result.get("raw"),
                "shape": curl_result.get("shape") if curl_result.get("ok") else result.get("shape"),
                "text_preview": curl_result.get("text_preview") if curl_result.get("ok") else result.get("text_preview"),
                "text_length": curl_result.get("text_length") if curl_result.get("ok") else result.get("text_length"),
            }

    result["cached"] = False
    result["cache_age_seconds"] = 0

    _leaderboard_cache[cache_key] = {
        "created_at": now,
        "payload": result,
    }

    return result


def clean_leaderboard_name(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)
    text = re.sub(r"<color[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</color>", "", text, flags=re.IGNORECASE)
    return " ".join(text.strip().split())


def normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def get_first_value(row: dict[str, Any], keys: list[str]) -> Any:
    normalized_lookup = {normalize_key(
        key): value for key, value in row.items()}

    for key in keys:
        normalized_key = normalize_key(key)
        if normalized_key in normalized_lookup:
            value = normalized_lookup[normalized_key]
            if value not in (None, ""):
                return value

    return None


def to_int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def to_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def looks_like_player_record(row: dict[str, Any]) -> bool:
    keys = {normalize_key(key) for key in row.keys()}

    has_name_or_id = bool(
        keys
        & {
            "name",
            "player",
            "playername",
            "gamertag",
            "alias",
            "username",
            "displayname",
            "profilealias",
            "userid",
            "rluserid",
            "profileid",
        }
    )

    has_rank_or_rating = bool(
        keys
        & {
            "rank",
            "rating",
            "elo",
            "elorating",
            "elohighest",
            "ranklevel",
            "rankrating",
            "ranking",
            "rate",
            "rmrank",
            "rmrating",
            "ranktotal",
            "wins",
            "losses",
            "totalgames",
        }
    )

    return has_name_or_id and has_rank_or_rating


def collect_player_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    if isinstance(value, dict):
        if looks_like_player_record(value):
            records.append(value)

        for child_value in value.values():
            records.extend(collect_player_records(child_value))

    elif isinstance(value, list):
        for item in value:
            records.extend(collect_player_records(item))

    return records


def calculate_confidence(query: str, name: str) -> str:
    query_clean = " ".join(str(query or "").casefold().split())
    name_clean = " ".join(str(name or "").casefold().split())

    if not query_clean:
        return "page"

    if query_clean == name_clean:
        return "exact"

    if query_clean in name_clean or name_clean in query_clean:
        return "partial"

    return "low"


def normalize_leaderboard_record(row: dict[str, Any], query: str) -> dict[str, Any]:
    raw_name = get_first_value(
        row,
        [
            "userName",
            "username",
            "name",
            "player",
            "playerName",
            "gamertag",
            "alias",
            "displayName",
            "profileAlias",
        ],
    )
    name = clean_leaderboard_name(raw_name)

    rl_user_id = get_first_value(
        row, ["rlUserId", "rl_user_id", "profile_id", "profileId", "profileID"])
    user_id = get_first_value(row, ["userId", "user_id", "userID"])
    rank = get_first_value(
        row, ["rank", "ranking", "leaderboardRank", "rankNumber", "rmRank"])
    rank_total = get_first_value(row, ["rankTotal", "rank_total"])
    rating = get_first_value(
        row, ["elo", "rating", "rankRating", "leaderboardRating", "rate", "rmRating"])
    elo_rating = get_first_value(row, ["eloRating", "elo_rating"])
    highest_rating = get_first_value(
        row, ["eloHighest", "elo_highest", "highestRating", "highest_rating"])
    wins = get_first_value(row, ["wins", "win", "gamesWon", "games_won"])
    losses = get_first_value(
        row, ["losses", "loss", "gamesLost", "games_lost"])
    games = get_first_value(
        row, ["totalGames", "total_games", "games", "gamesPlayed", "games_played"])
    win_rate = get_first_value(
        row, ["winPercent", "win_percent", "winRate", "win_rate"])
    streak = get_first_value(row, ["winStreak", "win_streak", "streak"])
    country = get_first_value(row, ["country", "countryCode", "country_code"])
    avatar_url = get_first_value(row, ["avatarUrl", "avatar_url"])
    region = get_first_value(row, ["region"])

    wins_int = to_int_or_none(wins)
    losses_int = to_int_or_none(losses)
    games_int = to_int_or_none(games)

    if games_int is None and (wins_int is not None or losses_int is not None):
        games_int = int(wins_int or 0) + int(losses_int or 0)

    win_rate_float = to_float_or_none(win_rate)
    if win_rate_float is None and games_int and games_int > 0:
        win_rate_float = round((int(wins_int or 0) / games_int) * 100, 1)

    profile_id = to_int_or_none(rl_user_id)

    return {
        "name": name,
        "raw_name": raw_name,
        "profile_id": profile_id,
        "rl_user_id": profile_id,
        "user_id": to_int_or_none(user_id),
        "rank": to_int_or_none(rank),
        "rank_total": to_int_or_none(rank_total),
        "rating": to_int_or_none(rating),
        "elo": to_int_or_none(rating),
        "elo_rating": to_int_or_none(elo_rating),
        "highest_rating": to_int_or_none(highest_rating),
        "wins": wins_int,
        "losses": losses_int,
        "games": games_int,
        "win_rate": win_rate_float,
        "streak": to_int_or_none(streak),
        "country": country,
        "region": region,
        "avatar_url": avatar_url,
        "confidence": calculate_confidence(query, name),
        "raw_keys": sorted(row.keys()),
        "raw": row,
    }


async def search_leaderboard(
    *,
    player: str = "",
    region: int = 7,
    match_type: int = 1,
    console_match_type: int = 15,
    page: int = 1,
    count: int = 100,
    sort_column: str = "rank",
    sort_direction: str = "ASC",
    refresh: bool = False,
    force_transport: str = "auto",
) -> dict[str, Any]:
    raw_response = await fetch_leaderboard_raw(
        player=player,
        region=region,
        match_type=match_type,
        console_match_type=console_match_type,
        page=page,
        count=count,
        sort_column=sort_column,
        sort_direction=sort_direction,
        refresh=refresh,
        force_transport=force_transport,
    )

    records = collect_player_records(raw_response.get("raw"))
    normalized_matches = [
        normalize_leaderboard_record(record, player)
        for record in records
    ]

    if player:
        confidence_order = {
            "exact": 0,
            "partial": 1,
            "low": 2,
            "page": 3,
        }
        normalized_matches.sort(
            key=lambda match: (
                confidence_order.get(str(match.get("confidence")), 99),
                match.get("rank") if match.get(
                    "rank") is not None else 999999999,
            )
        )
    else:
        normalized_matches.sort(
            key=lambda match: (
                match.get("rank") if match.get(
                    "rank") is not None else 999999999,
                str(match.get("name") or "").casefold(),
            )
        )

    return {
        "query": player,
        "request": raw_response.get("request"),
        "transport": raw_response.get("transport"),
        "selected_transport": raw_response.get("selected_transport"),
        "status_code": raw_response.get("status_code"),
        "ok": raw_response.get("ok"),
        "cached": raw_response.get("cached"),
        "shape": raw_response.get("shape"),
        "match_count": len(normalized_matches),
        "matches": normalized_matches,
    }


def build_community_leaderboard2_params(
    *,
    leaderboard_id: int,
    count: int = 100,
    start: int = 1,
    title: str = "athens",
) -> dict[str, Any]:
    return {
        "title": title,
        "count": int(count),
        "start": int(start),
        "leaderboard_id": int(leaderboard_id),
    }


def normalize_community_leaderboard_row(
    member: dict[str, Any],
    stats_row: dict[str, Any],
) -> dict[str, Any]:
    wins = to_int_or_none(stats_row.get("wins"))
    losses = to_int_or_none(stats_row.get("losses"))
    games = None
    if wins is not None or losses is not None:
        games = int(wins or 0) + int(losses or 0)

    win_rate = None
    if games and games > 0:
        win_rate = round((int(wins or 0) / games) * 100, 1)

    profile_name = str(member.get("name") or "").strip()
    platform = "unknown"
    platform_id = ""
    if profile_name.startswith("/steam/"):
        platform = "steam"
        platform_id = profile_name.removeprefix("/steam/")
    elif profile_name.startswith("/xboxlive/"):
        platform = "xbox"
        platform_id = profile_name.removeprefix("/xboxlive/")

    return {
        "name": clean_leaderboard_name(member.get("alias")),
        "raw_name": member.get("alias"),
        "profile_id": to_int_or_none(member.get("profile_id")),
        "rl_user_id": to_int_or_none(member.get("profile_id")),
        "user_id": None,
        "rank": to_int_or_none(stats_row.get("rank")),
        "rank_total": to_int_or_none(stats_row.get("ranktotal")),
        "rating": to_int_or_none(stats_row.get("rating")),
        "elo": to_int_or_none(stats_row.get("rating")),
        "elo_rating": None,
        "highest_rating": to_int_or_none(stats_row.get("highestrating")),
        "wins": wins,
        "losses": losses,
        "games": games,
        "win_rate": win_rate,
        "streak": to_int_or_none(stats_row.get("streak")),
        "country": member.get("country"),
        "region": to_int_or_none(member.get("leaderboardregion_id")),
        "avatar_url": "",
        "confidence": "page",
        "platform": platform,
        "platform_id": platform_id,
        "clan": member.get("clanlist_name") or "",
        "raw_keys": sorted({*member.keys(), *stats_row.keys()}),
        "raw": {
            "member": member,
            "leaderboard_stats": stats_row,
        },
    }


def build_personal_stat_params(
    *,
    profile_ids: list[int | str] | None = None,
    profile_names: list[str] | None = None,
    aliases: list[str] | None = None,
    title: str = "athens",
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "title": title,
    }

    if profile_ids:
        params["profile_ids"] = json.dumps([
            int(value) if to_int_or_none(value) is not None else str(value)
            for value in profile_ids
            if value not in (None, "")
        ])

    if profile_names:
        params["profile_names"] = json.dumps([str(value) for value in profile_names if value not in (None, "")])

    if aliases:
        params["aliases"] = json.dumps([str(value) for value in aliases if value not in (None, "")])

    return params


def normalize_personal_stat_record(
    member: dict[str, Any],
    stats_row: dict[str, Any],
    *,
    requested_match_type: int | None = None,
) -> dict[str, Any]:
    wins = to_int_or_none(stats_row.get("wins"))
    losses = to_int_or_none(stats_row.get("losses"))
    games = None
    if wins is not None or losses is not None:
        games = int(wins or 0) + int(losses or 0)

    win_rate = None
    if games and games > 0:
        win_rate = round((int(wins or 0) / games) * 100, 1)

    profile_name = str(member.get("name") or "").strip()
    platform = "unknown"
    platform_id = ""
    if profile_name.startswith("/steam/"):
        platform = "steam"
        platform_id = profile_name.removeprefix("/steam/")
    elif profile_name.startswith("/xbox/"):
        platform = "xbox"
        platform_id = profile_name.removeprefix("/xbox/")
    elif profile_name.startswith("/xboxlive/"):
        platform = "xbox"
        platform_id = profile_name.removeprefix("/xboxlive/")

    queue_id = to_int_or_none(stats_row.get("leaderboard_id"))
    if queue_id is None:
        queue_id = requested_match_type

    return {
        "source": "personal_stat",
        "name": clean_leaderboard_name(member.get("alias")),
        "raw_name": member.get("alias"),
        "profile_id": to_int_or_none(member.get("profile_id")),
        "rl_user_id": to_int_or_none(member.get("profile_id")),
        "queue_id": queue_id,
        "queue_label": get_queue_label(queue_id),
        "leaderboard_id": queue_id,
        "match_type": queue_id,
        "match_type_label": get_queue_label(queue_id),
        "rating": to_int_or_none(stats_row.get("rating")),
        "elo": to_int_or_none(stats_row.get("rating")),
        "highest_rating": to_int_or_none(stats_row.get("highestrating")),
        "rank": to_int_or_none(stats_row.get("rank")),
        "rank_total": to_int_or_none(stats_row.get("ranktotal")),
        "wins": wins,
        "losses": losses,
        "games": games,
        "win_rate": win_rate,
        "streak": to_int_or_none(stats_row.get("streak")),
        "avatar_url": "",
        "country": member.get("country"),
        "region": to_int_or_none(member.get("leaderboardregion_id")),
        "platform": platform,
        "platform_id": platform_id,
        "clan": member.get("clanlist_name") or "",
        "confidence": "id",
        "raw_keys": sorted({*member.keys(), *stats_row.keys()}),
        "raw": {
            "member": member,
            "leaderboard_stats": stats_row,
        },
    }


async def fetch_personal_stat_raw(
    *,
    profile_id: int | None = None,
    profile_names: list[str] | None = None,
    aliases: list[str] | None = None,
    refresh: bool = False,
    title: str = "athens",
) -> dict[str, Any]:
    params = build_personal_stat_params(
        profile_ids=[profile_id] if profile_id is not None else None,
        profile_names=profile_names,
        aliases=aliases,
        title=title,
    )
    cache_key = (
        "personal_stat",
        str(profile_id or ""),
        tuple(str(value) for value in (profile_names or [])),
        tuple(str(value) for value in (aliases or [])),
        str(title).casefold(),
    )
    now = time.time()

    cached = _leaderboard_cache.get(cache_key)
    if (
        not refresh
        and cached is not None
        and now - float(cached.get("created_at", 0)) < LEADERBOARD_CACHE_SECONDS
    ):
        payload = dict(cached["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(now - float(cached["created_at"]), 2)
        return payload

    result = get_json_with_curl(
        url=PERSONAL_STAT_URL,
        params=params,
        label="personal_stat",
        timeout_seconds=30,
    )
    result["cached"] = False
    result["cache_age_seconds"] = 0

    _leaderboard_cache[cache_key] = {
        "created_at": now,
        "payload": result,
    }
    return result


async def fetch_personal_stat_summary(
    *,
    profile_id: int | None = None,
    player: str = "",
    profile_names: list[str] | None = None,
    aliases: list[str] | None = None,
    requested_match_type: int | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    raw_response = await fetch_personal_stat_raw(
        profile_id=profile_id,
        profile_names=profile_names,
        aliases=aliases,
        refresh=refresh,
    )
    payload = raw_response.get("raw") if isinstance(raw_response.get("raw"), dict) else {}
    stat_groups = payload.get("statGroups") if isinstance(payload, dict) else []
    leaderboard_stats = payload.get("leaderboardStats") if isinstance(payload, dict) else []

    members_by_statgroup_id: dict[int, dict[str, Any]] = {}
    for group in stat_groups if isinstance(stat_groups, list) else []:
        if not isinstance(group, dict):
            continue
        group_id = to_int_or_none(group.get("id"))
        members = group.get("members")
        if group_id is None or not isinstance(members, list) or not members:
            continue
        first_member = members[0]
        if isinstance(first_member, dict):
            members_by_statgroup_id[group_id] = first_member

    ratings: list[dict[str, Any]] = []
    for row in leaderboard_stats if isinstance(leaderboard_stats, list) else []:
        if not isinstance(row, dict):
            continue
        statgroup_id = to_int_or_none(row.get("statgroup_id"))
        member = members_by_statgroup_id.get(statgroup_id)
        if not member:
            continue
        ratings.append(
            normalize_personal_stat_record(
                member,
                row,
                requested_match_type=requested_match_type,
            )
        )

    ratings.sort(
        key=lambda item: (
            0 if requested_match_type is not None and item.get("queue_id") == requested_match_type else 1,
            item.get("queue_id") if item.get("queue_id") is not None else 999999999,
        )
    )

    display_name = ratings[0].get("name") if ratings else clean_leaderboard_name(player)

    return {
        "ok": bool(raw_response.get("ok")),
        "source": "personal_stat",
        "profile_id": profile_id or (ratings[0].get("profile_id") if ratings else None),
        "player": player,
        "display_name": display_name,
        "avatar_url": "",
        "ratings": ratings,
        "request": raw_response.get("request"),
        "status_code": raw_response.get("status_code"),
        "cached": raw_response.get("cached"),
        "shape": raw_response.get("shape"),
        "raw": payload,
    }


async def fetch_community_leaderboard2(
    *,
    leaderboard_id: int,
    page: int = 1,
    count: int = 100,
    title: str = "athens",
    refresh: bool = False,
) -> dict[str, Any]:
    start = ((max(1, int(page)) - 1) * int(count)) + 1
    params = build_community_leaderboard2_params(
        leaderboard_id=leaderboard_id,
        count=count,
        start=start,
        title=title,
    )

    cache_key = ("community_leaderboard2", int(leaderboard_id), int(page), int(count), str(title).casefold())
    now = time.time()

    cached = _leaderboard_cache.get(cache_key)
    if (
        not refresh
        and cached is not None
        and now - float(cached.get("created_at", 0)) < LEADERBOARD_CACHE_SECONDS
    ):
        payload = dict(cached["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(now - float(cached["created_at"]), 2)
        return payload

    raw_response = get_json_with_curl(
        url=COMMUNITY_LEADERBOARD2_URL,
        params=params,
        label="community_leaderboard2",
        timeout_seconds=30,
    )

    payload = raw_response.get("raw") if isinstance(raw_response.get("raw"), dict) else {}
    stat_groups = payload.get("statGroups") if isinstance(payload, dict) else []
    leaderboard_stats = payload.get("leaderboardStats") if isinstance(payload, dict) else []

    members_by_statgroup_id: dict[int, dict[str, Any]] = {}
    for group in stat_groups if isinstance(stat_groups, list) else []:
        if not isinstance(group, dict):
            continue
        group_id = to_int_or_none(group.get("id"))
        members = group.get("members")
        if group_id is None or not isinstance(members, list) or not members:
            continue
        first_member = members[0]
        if isinstance(first_member, dict):
            members_by_statgroup_id[group_id] = first_member

    normalized_matches: list[dict[str, Any]] = []
    for row in leaderboard_stats if isinstance(leaderboard_stats, list) else []:
        if not isinstance(row, dict):
            continue
        statgroup_id = to_int_or_none(row.get("statgroup_id"))
        member = members_by_statgroup_id.get(statgroup_id)
        if not member:
            continue
        normalized_matches.append(normalize_community_leaderboard_row(member, row))

    result = {
        "request": raw_response.get("request"),
        "transport": raw_response.get("transport"),
        "status_code": raw_response.get("status_code"),
        "ok": bool(raw_response.get("ok")),
        "cached": False,
        "shape": raw_response.get("shape"),
        "rank_total": to_int_or_none(payload.get("rankTotal")) if isinstance(payload, dict) else None,
        "match_count": len(normalized_matches),
        "matches": normalized_matches,
        "raw": payload,
    }

    _leaderboard_cache[cache_key] = {
        "created_at": now,
        "payload": result,
    }

    return result


def build_full_stats_body(
    *,
    profile_id: int | str,
    gamertag: str = "unknown user",
    match_types: list[int] | None = None,
) -> dict[str, Any]:
    if match_types is None:
        match_types = get_ranked_match_type_ids()

    return {
        "profileId": str(profile_id),
        "gamertag": gamertag or "unknown user",
        "playerNumber": 0,
        "gameId": 0,
        "matchType": [int(match_type) for match_type in match_types],
    }


def collect_stat_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    if isinstance(value, dict):
        merged_candidates: list[dict[str, Any]] = []

        user = value.get("user")
        if isinstance(user, dict):
            merged_candidates.append({**value, **user})

        player = value.get("player")
        if isinstance(player, dict):
            merged_candidates.append({**value, **player})

        for candidate in merged_candidates:
            if any(key in candidate for key in ["elo", "eloRating", "rank", "wins", "losses", "totalGames"]):
                records.append(candidate)

        if any(key in value for key in ["elo", "eloRating", "rank", "wins", "losses", "totalGames"]):
            records.append(value)

        for child in value.values():
            records.extend(collect_stat_records(child))

    elif isinstance(value, list):
        for item in value:
            records.extend(collect_stat_records(item))

    return records


def get_record_match_type(
    record: dict[str, Any],
    *,
    requested_match_type: int | None = None,
) -> int | None:
    direct_match_type = get_first_value(
        record,
        [
            "matchType",
            "matchtype",
            "match_type",
            "matchTypeId",
            "matchTypeID",
            "matchtype_id",
            "match_type_id",
        ],
    )
    normalized_direct_match_type = to_int_or_none(direct_match_type)
    if normalized_direct_match_type is not None:
        return normalized_direct_match_type

    leaderboard_id = to_int_or_none(
        get_first_value(record, ["leaderboardId", "leaderboard_id"]))
    if leaderboard_id is None:
        return requested_match_type

    leaderboard_match_types = get_match_type_ids_for_leaderboard(leaderboard_id)
    if requested_match_type is not None and requested_match_type in leaderboard_match_types:
        return requested_match_type

    if leaderboard_match_types:
        return leaderboard_match_types[0]

    return requested_match_type


def normalize_full_stats_record(
    record: dict[str, Any],
    *,
    profile_id: int | None,
    player: str,
    requested_match_type: int,
) -> dict[str, Any]:
    raw_name = get_first_value(
        record,
        [
            "userName",
            "username",
            "gamertag",
            "displayName",
            "alias",
            "name",
        ],
    )
    name = clean_leaderboard_name(raw_name) or clean_leaderboard_name(player)

    rl_user_id = get_first_value(
        record,
        [
            "rlUserId",
            "rl_user_id",
            "profileId",
            "profile_id",
            "profileID",
            "userId",
            "user_id",
        ],
    )

    record_profile_id = to_int_or_none(rl_user_id) or profile_id
    rating = get_first_value(
        record, ["elo", "rating", "rankRating", "leaderboardRating", "rate"])
    highest_rating = get_first_value(
        record, ["eloHighest", "elo_highest", "highestRating", "highest_rating"])
    rank = get_first_value(record, ["rank", "leaderboardRank", "rankNumber"])
    rank_total = get_first_value(record, ["rankTotal", "rank_total"])
    wins = get_first_value(record, ["wins", "gamesWon", "games_won"])
    losses = get_first_value(record, ["losses", "gamesLost", "games_lost"])
    games = get_first_value(
        record, ["totalGames", "total_games", "games", "gamesPlayed", "games_played"])
    win_rate = get_first_value(
        record, ["winPercent", "win_percent", "winRate", "win_rate"])
    streak = get_first_value(record, ["winStreak", "win_streak", "streak"])
    avatar_url = get_first_value(record, ["avatarUrl", "avatar_url"])

    wins_int = to_int_or_none(wins)
    losses_int = to_int_or_none(losses)
    games_int = to_int_or_none(games)

    if games_int is None and (wins_int is not None or losses_int is not None):
        games_int = int(wins_int or 0) + int(losses_int or 0)

    win_rate_float = to_float_or_none(win_rate)
    if win_rate_float is None and games_int and games_int > 0:
        win_rate_float = round((int(wins_int or 0) / games_int) * 100, 1)

    match_type = get_record_match_type(
        record,
        requested_match_type=requested_match_type,
    )
    if match_type is None:
        match_type = requested_match_type

    return {
        "source": "full_stats",
        "name": name,
        "raw_name": raw_name,
        "profile_id": record_profile_id,
        "rl_user_id": record_profile_id,
        "match_type": match_type,
        "match_type_label": get_match_type_label(match_type),
        "rating": to_int_or_none(rating),
        "elo": to_int_or_none(rating),
        "highest_rating": to_int_or_none(highest_rating),
        "rank": to_int_or_none(rank),
        "rank_total": to_int_or_none(rank_total),
        "wins": wins_int,
        "losses": losses_int,
        "games": games_int,
        "win_rate": win_rate_float,
        "streak": to_int_or_none(streak),
        "avatar_url": avatar_url,
        "confidence": "id" if profile_id and record_profile_id == profile_id else calculate_confidence(player, name),
        "raw_keys": sorted(record.keys()),
        "raw": record,
    }


def pick_best_full_stats_record(
    records: list[dict[str, Any]],
    *,
    profile_id: int | None,
    player: str,
    requested_match_type: int,
) -> dict[str, Any] | None:
    normalized = [
        normalize_full_stats_record(
            record,
            profile_id=profile_id,
            player=player,
            requested_match_type=requested_match_type,
        )
        for record in records
    ]

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        id_score = 0 if profile_id and item.get(
            "profile_id") == profile_id else 1
        match_type_score = 0 if item.get(
            "match_type") == requested_match_type else 1
        rating_score = 0 if item.get("rating") is not None else 1
        return (id_score, match_type_score, rating_score)

    normalized.sort(key=score)

    return normalized[0] if normalized else None


async def fetch_full_stats_raw(
    *,
    profile_id: int,
    player: str = "unknown user",
    match_types: list[int] | None = None,
    refresh: bool = False,
    force_transport: str = "curl",
) -> dict[str, Any]:
    body = build_full_stats_body(
        profile_id=profile_id,
        gamertag=player or "unknown user",
        match_types=match_types or get_ranked_match_type_ids(),
    )
    cache_key = ("full_stats", int(profile_id), str(
        player or "").casefold(), tuple(body["matchType"]), force_transport)
    now = time.time()

    cached = _leaderboard_cache.get(cache_key)
    if (
        not refresh
        and cached is not None
        and now - float(cached.get("created_at", 0)) < LEADERBOARD_CACHE_SECONDS
    ):
        payload = dict(cached["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(
            now - float(cached["created_at"]), 2)
        return payload

    # Use curl by default because the Age of Empires endpoints have already
    # proven more reliable from curl than httpx in this project.
    result = post_json_with_curl(
        url=FULL_STATS_URL,
        body=body,
        label="full_stats",
        timeout_seconds=30,
    )
    result["cached"] = False
    result["cache_age_seconds"] = 0

    _leaderboard_cache[cache_key] = {
        "created_at": now,
        "payload": result,
    }
    return result


async def fetch_player_rating(
    *,
    profile_id: int | None = None,
    player: str = "",
    match_type: int = 1,
    refresh: bool = False,
    force_transport: str = "curl",
) -> dict[str, Any]:
    resolved_profile_id = profile_id
    resolved_player = player

    if resolved_profile_id is None and player and not str(player).startswith("/"):
        leaderboard_search = await search_leaderboard(
            player=player,
            match_type=match_type,
            refresh=refresh,
            force_transport=force_transport,
        )
        leaderboard_matches = leaderboard_search.get("matches", []) if isinstance(leaderboard_search, dict) else []
        exact_match = next(
            (
                item for item in leaderboard_matches
                if clean_leaderboard_name(item.get("name")).casefold() == clean_leaderboard_name(player).casefold()
            ),
            None,
        )
        if exact_match:
            resolved_profile_id = exact_match.get("profile_id") or resolved_profile_id
            resolved_player = exact_match.get("name") or resolved_player

    profile_names = []
    if resolved_player and str(resolved_player).startswith("/"):
        profile_names.append(str(resolved_player))

    aliases = [resolved_player] if resolved_player and not str(resolved_player).startswith("/") else []
    personal_stat_response = await fetch_personal_stat_summary(
        profile_id=resolved_profile_id,
        player=resolved_player,
        profile_names=profile_names,
        aliases=aliases,
        requested_match_type=match_type,
        refresh=refresh,
    )
    personal_stat_ratings = personal_stat_response.get("ratings", []) if isinstance(personal_stat_response, dict) else []
    personal_stat_best = next(
        (
            item for item in personal_stat_ratings
            if item.get("queue_id") == match_type and item.get("rating") is not None
        ),
        None,
    )

    if personal_stat_best and personal_stat_best.get("rating") is not None:
        return {
            "ok": True,
            "source": "personal_stat",
            "data_source": build_source_meta(
                endpoint="community/leaderboard/GetPersonalStat",
                queue_id=match_type,
                cached=personal_stat_response.get("cached"),
                status_code=personal_stat_response.get("status_code"),
                source="personal_stat",
            ),
            "profile_id": personal_stat_response.get("profile_id") or resolved_profile_id,
            "player": resolved_player,
            "requested_match_type": match_type,
            "requested_match_type_label": get_queue_label(match_type),
            "rating": personal_stat_best,
            "ratings": personal_stat_ratings,
            "personal_stat_status_code": personal_stat_response.get("status_code"),
            "personal_stat_shape": personal_stat_response.get("shape"),
            "leaderboard_fallback_used": False,
        }

    leaderboard_response = None
    leaderboard_matches: list[dict[str, Any]] = []

    if player:
        leaderboard_response = await search_leaderboard(
            player=resolved_player,
            match_type=match_type,
            refresh=refresh,
            force_transport=force_transport,
        )
        leaderboard_matches = leaderboard_response.get("matches", [])

    id_matches = [
        match for match in leaderboard_matches
        if profile_id is not None and match.get("profile_id") == profile_id
    ]

    if id_matches:
        best = id_matches[0]
        best = {**best, "source": "leaderboard", "match_type": match_type,
                "match_type_label": get_queue_label(match_type), "confidence": "id"}
        return {
            "ok": True,
            "source": "leaderboard",
            "data_source": build_source_meta(
                endpoint="api/agemyth/Leaderboard",
                queue_id=match_type,
                cached=leaderboard_response.get("cached") if leaderboard_response else None,
                status_code=leaderboard_response.get("status_code") if leaderboard_response else None,
                source="leaderboard",
            ),
            "profile_id": resolved_profile_id,
            "player": resolved_player,
            "requested_match_type": match_type,
            "requested_match_type_label": get_queue_label(match_type),
            "rating": best,
            "ratings": [best],
            "personal_stat_status_code": personal_stat_response.get("status_code") if personal_stat_response else None,
            "personal_stat_shape": personal_stat_response.get("shape") if personal_stat_response else None,
            "leaderboard_fallback_used": True,
            "leaderboard_match_count": len(leaderboard_matches),
        }

    exact_name_matches = [
        match for match in leaderboard_matches
        if clean_leaderboard_name(match.get("name")).casefold() == clean_leaderboard_name(resolved_player).casefold()
    ]

    if resolved_profile_id is None and len(exact_name_matches) == 1:
        best = {**exact_name_matches[0], "source": "leaderboard", "match_type": match_type,
                "match_type_label": get_queue_label(match_type), "confidence": "exact"}
        return {
            "ok": True,
            "source": "leaderboard",
            "data_source": build_source_meta(
                endpoint="api/agemyth/Leaderboard",
                queue_id=match_type,
                cached=leaderboard_response.get("cached") if leaderboard_response else None,
                status_code=leaderboard_response.get("status_code") if leaderboard_response else None,
                source="leaderboard",
            ),
            "profile_id": resolved_profile_id,
            "player": resolved_player,
            "requested_match_type": match_type,
            "requested_match_type_label": get_queue_label(match_type),
            "rating": best,
            "ratings": [best],
            "personal_stat_status_code": personal_stat_response.get("status_code") if personal_stat_response else None,
            "personal_stat_shape": personal_stat_response.get("shape") if personal_stat_response else None,
            "leaderboard_fallback_used": True,
            "leaderboard_match_count": len(leaderboard_matches),
        }

    reason = "No rating returned by GetPersonalStat and no authoritative leaderboard ID match."
    if personal_stat_response is not None and not personal_stat_response.get("ok"):
        reason = "GetPersonalStat request failed and no authoritative leaderboard ID match was found."
    elif profile_id is not None and personal_stat_response is not None:
        reason = f"GetPersonalStat returned {len(personal_stat_ratings)} candidate record(s), but none contained a usable rating for profile_id {profile_id}."

    return {
        "ok": False,
        "source": None,
        "data_source": build_source_meta(
            endpoint="community/leaderboard/GetPersonalStat",
            queue_id=match_type,
            cached=personal_stat_response.get("cached") if personal_stat_response else None,
            status_code=personal_stat_response.get("status_code") if personal_stat_response else None,
            source="personal_stat",
        ),
        "profile_id": resolved_profile_id,
        "player": resolved_player,
        "requested_match_type": match_type,
        "requested_match_type_label": get_queue_label(match_type),
        "rating": None,
        "ratings": [],
        "reason": reason,
        "personal_stat_status_code": personal_stat_response.get("status_code") if personal_stat_response else None,
        "personal_stat_shape": personal_stat_response.get("shape") if personal_stat_response else None,
        "personal_stat_record_count": len(personal_stat_ratings),
        "leaderboard_fallback_used": leaderboard_response is not None,
        "leaderboard_match_count": len(leaderboard_matches),
    }


def build_match_list_body(
    *,
    profile_id: int | str,
    gamertag: str = "unknown user",
    match_type: int = 1,
    page: int = 1,
    record_count: int = 10,
) -> dict[str, Any]:
    return {
        "gamertag": gamertag or "unknown user",
        "playerNumber": 0,
        "game": "ageMyth",
        "profileId": str(profile_id),
        "sortColumn": "dateTime",
        "sortDirection": "DESC",
        "page": int(page),
        "recordCount": int(record_count),
        "matchType": str(int(match_type)),
    }


def get_nested_first_value(source: Any, keys: list[str]) -> Any:
    if not isinstance(source, dict):
        return None

    direct = get_first_value(source, keys)
    if direct is not None:
        return direct

    for value in source.values():
        if isinstance(value, dict):
            nested = get_nested_first_value(value, keys)
            if nested is not None:
                return nested
        elif isinstance(value, list):
            for item in value:
                nested = get_nested_first_value(item, keys)
                if nested is not None:
                    return nested

    return None


def normalize_match_result(value: Any) -> str | None:
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return "Win" if value else "Loss"

    text = str(value).strip()
    lower = text.casefold()

    if lower in {"win", "won", "victory", "1", "true"}:
        return "Win"

    if lower in {"loss", "lost", "defeat", "0", "false"}:
        return "Loss"

    return text


def normalize_match_list_record(
    row: dict[str, Any],
    *,
    requested_match_type: int | None = None,
) -> dict[str, Any]:
    match_id = get_nested_first_value(
        row, ["matchId", "match_id", "id", "gameId", "game_id"])
    date_time = get_nested_first_value(
        row, ["dateTime", "date_time", "started", "startTime", "start_time", "matchDate"])
    map_name = get_nested_first_value(
        row, ["map", "mapName", "map_name", "location", "scenario", "mapNameResolved", "scenarioName"])
    decoded_map_name = get_nested_first_value(
        row, ["mGameMapName", "gameMapName", "mapNameDecoded", "decodedMapName", "mGameFilename"])
    duration = get_nested_first_value(
        row, ["duration", "durationSeconds", "duration_seconds", "gameDuration"])
    result = get_nested_first_value(
        row, ["result", "outcome", "playerResult", "winner", "won", "isWinner", "victory"])
    match_type = get_record_match_type(
        row,
        requested_match_type=requested_match_type,
    )
    rating_change = get_nested_first_value(
        row, ["eloChange", "elo_change", "ratingChange", "rating_change"])
    rating = get_nested_first_value(
        row, ["elo", "rating", "playerElo", "player_rating"])

    return {
        "match_id": str(match_id) if match_id is not None else None,
        "date_time": date_time,
        "map": format_map_name(str(map_name) if map_name is not None else None, str(decoded_map_name) if decoded_map_name is not None else None),
        "duration": duration,
        "result": normalize_match_result(result),
        "match_type": match_type,
        "match_type_label": get_match_type_label(match_type),
        "rating": to_int_or_none(rating),
        "rating_change": to_int_or_none(rating_change),
        "raw_keys": sorted(row.keys()),
        "raw": row,
    }


def build_recent_match_history_params(
    *,
    profile_ids: list[int | str] | None = None,
    profile_names: list[str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "title": "athens",
    }

    if profile_ids:
        params["profile_ids"] = json.dumps([
            int(value) if to_int_or_none(value) is not None else str(value)
            for value in profile_ids
            if value not in (None, "")
        ])

    if profile_names:
        params["profile_names"] = json.dumps([str(value) for value in profile_names if value not in (None, "")])

    return params


def build_recent_match_history_profile_lookup(raw_payload: Any) -> dict[int, dict[str, Any]]:
    if not isinstance(raw_payload, dict):
        return {}

    profiles = raw_payload.get("profiles")
    if not isinstance(profiles, list):
        return {}

    lookup: dict[int, dict[str, Any]] = {}

    for item in profiles:
        if not isinstance(item, dict):
            continue

        profile_id = to_int_or_none(item.get("profile_id") or item.get("profileId"))
        if profile_id is None:
            continue

        lookup[profile_id] = item

    return lookup


def decode_base64_compressed_text(value: Any) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {"decoded": False, "text": ""}

    try:
        compressed = base64.b64decode(text)
    except Exception as error:
        return {"decoded": False, "text": "", "error": str(error)}

    last_error: Exception | None = None
    for compression, decoder in (("gzip", gzip.decompress), ("zlib", zlib.decompress)):
        try:
            decoded = decoder(compressed)
            return {
                "decoded": True,
                "compression": compression,
                "byte_length": len(decoded),
                "text": decoded.decode("utf-8", errors="replace").rstrip("\x00"),
            }
        except Exception as error:
            last_error = error

    return {"decoded": False, "text": "", "error": str(last_error) if last_error else "Unable to decompress payload."}


def decoded_payload_meta(decoded: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in decoded.items() if key != "text"}


def parse_json_payload_text(text: str) -> Any:
    cleaned = str(text or "").strip().rstrip("\x00")
    if not cleaned:
        return None

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def parse_slot_info_text(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip().rstrip("\x00")
    if not cleaned:
        return None

    slot_count = None
    payload_text = cleaned
    if "," in cleaned:
        possible_count, _, possible_payload = cleaned.partition(",")
        try:
            slot_count = int(possible_count)
            payload_text = possible_payload
        except ValueError:
            payload_text = cleaned

    parsed = parse_json_payload_text(payload_text)
    if parsed is None:
        return None

    return {
        "slot_count": slot_count,
        "players": parsed if isinstance(parsed, list) else [],
        "raw": parsed,
    }


def parse_report_counters(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if not value:
        return {}

    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def build_match_report_lookup(row: dict[str, Any]) -> dict[int, dict[str, Any]]:
    reports = row.get("matchhistoryreportresults")
    if not isinstance(reports, list):
        return {}

    lookup: dict[int, dict[str, Any]] = {}
    for report in reports:
        if not isinstance(report, dict):
            continue

        profile_id = to_int_or_none(report.get("profile_id"))
        if profile_id is None:
            continue

        normalized = dict(report)
        normalized["counters"] = parse_report_counters(report.get("counters"))
        lookup[profile_id] = normalized

    return lookup


def get_match_type_filter_ids(match_type: int | None) -> list[int]:
    if match_type is None:
        return []

    leaderboard_match_types = get_match_type_ids_for_leaderboard(match_type)
    if leaderboard_match_types:
        return leaderboard_match_types

    return [int(match_type)]


def normalize_recent_match_history_record(
    row: dict[str, Any],
    *,
    profiles_by_id: dict[int, dict[str, Any]] | None = None,
    requested_profile_id: int | None = None,
    requested_match_type: int | None = None,
) -> dict[str, Any]:
    profiles_by_id = profiles_by_id or {}
    member_rows = row.get("matchhistorymember") if isinstance(row.get("matchhistorymember"), list) else []
    report_rows_by_profile_id = build_match_report_lookup(row)
    decoded_options = decode_base64_compressed_text(row.get("options"))
    decoded_slot_info = decode_base64_compressed_text(row.get("slotinfo") or row.get("slotInfo"))
    options_payload = parse_json_payload_text(decoded_options.get("text", ""))
    slot_info_payload = parse_slot_info_text(decoded_slot_info.get("text", ""))
    slot_players = slot_info_payload.get("players", []) if isinstance(slot_info_payload, dict) else []
    slot_players_by_profile_id = {
        int(profile_id): slot
        for slot in slot_players
        if isinstance(slot, dict)
        for profile_id in [to_int_or_none(slot.get("profileInfo.id") or slot.get("profile_id"))]
        if profile_id is not None
    }

    match_id = row.get("id")
    match_type = get_record_match_type(row, requested_match_type=requested_match_type)
    start_time = to_int_or_none(row.get("startgametime"))
    completion_time = to_int_or_none(row.get("completiontime"))
    duration = None
    if start_time is not None and completion_time is not None and completion_time >= start_time:
        duration = completion_time - start_time

    requested_member = None
    if requested_profile_id is not None:
        requested_member = next(
            (
                member for member in member_rows
                if to_int_or_none(member.get("profile_id")) == int(requested_profile_id)
            ),
            None,
        )

    requested_report = report_rows_by_profile_id.get(int(requested_profile_id)) if requested_profile_id is not None else None
    result = normalize_match_result(requested_member.get("outcome")) if requested_member else normalize_match_result(
        requested_report.get("resulttype") if requested_report else None
    )
    rating = to_int_or_none(requested_member.get("newrating")) if requested_member else None
    old_rating = to_int_or_none(requested_member.get("oldrating")) if requested_member else None
    rating_change = None
    if rating is not None and old_rating is not None:
        rating_change = rating - old_rating
    requested_counters = requested_report.get("counters", {}) if requested_report else {}
    ranked_match = requested_counters.get("rankedMatch") if isinstance(requested_counters, dict) else None

    players: list[dict[str, Any]] = []
    for member in member_rows:
        profile_id = to_int_or_none(member.get("profile_id"))
        profile = profiles_by_id.get(profile_id or -1, {})
        report = report_rows_by_profile_id.get(profile_id or -1, {})
        counters = report.get("counters", {}) if isinstance(report, dict) else {}
        slot = slot_players_by_profile_id.get(profile_id or -1, {})
        player_rating = to_int_or_none(member.get("newrating"))
        player_old_rating = to_int_or_none(member.get("oldrating"))
        player_rating_change = None
        if player_rating is not None and player_old_rating is not None:
            player_rating_change = player_rating - player_old_rating

        players.append(
            {
                "user_id": profile_id,
                "profile_id": profile_id,
                "name": clean_leaderboard_name(profile.get("alias") or profile.get("name")),
                "platform_name": str(profile.get("name") or ""),
                "avatar_url": "",
                "team": to_int_or_none(member.get("teamid")),
                "god": resolve_community_civilization_name(member.get("civilization_id")),
                "elo": player_rating,
                "rating_change": player_rating_change,
                "result": normalize_match_result(member.get("outcome")),
                "ranked_match": counters.get("rankedMatch") if isinstance(counters, dict) else None,
                "counters": counters,
                "country": str(profile.get("country") or ""),
                "match_replay_available": False,
                "slot_info": slot,
                "raw_profile": profile,
                "raw_member": member,
                "raw_report": report,
            }
        )

    if start_time is not None:
        date_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time))
    else:
        date_time = None

    raw_map_name = row.get("mapname") or ""
    decoded_map_name = ""
    if not raw_map_name and isinstance(options_payload, dict):
        decoded_map_name = str(options_payload.get("mGameMapName") or options_payload.get("mGameFilename") or "")
    map_name = format_map_name(str(raw_map_name) if raw_map_name else None, decoded_map_name or None)

    return {
        "match_id": str(match_id) if match_id is not None else None,
        "date_time": date_time,
        "sort_timestamp": float(completion_time or start_time or 0),
        "map": map_name,
        "duration": duration,
        "result": result,
        "match_type": match_type,
        "match_type_label": get_match_type_label(match_type),
        "rating": rating,
        "rating_change": rating_change,
        "civilization": resolve_community_civilization_name(requested_member.get("civilization_id")) if requested_member else "",
        "ranked_match": ranked_match,
        "options": options_payload if isinstance(options_payload, dict) else {},
        "slot_info": slot_info_payload or {},
        "decoded_payloads": {
            "options": decoded_payload_meta(decoded_options),
            "slotinfo": decoded_payload_meta(decoded_slot_info),
        },
        "players": players,
        "raw_keys": sorted(row.keys()),
        "raw": row,
    }


def collect_match_list_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    if isinstance(value, dict):
        for key in ["items", "matches", "matchList", "match_list", "games", "results"]:
            child = value.get(key)
            if isinstance(child, list):
                records.extend(
                    [item for item in child if isinstance(item, dict)])

        if any(key in value for key in ["matchId", "match_id", "dateTime", "date_time"]):
            records.append(value)

        for child in value.values():
            if isinstance(child, (dict, list)):
                records.extend(collect_match_list_records(child))

    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                records.extend(collect_match_list_records(item))

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        key = json.dumps(
            {
                "matchId": get_first_value(record, ["matchId", "match_id", "id"]),
                "dateTime": get_first_value(record, ["dateTime", "date_time"]),
                "map": get_first_value(record, ["map", "mapName", "map_name"]),
            },
            sort_keys=True,
            default=str,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)

    return deduped


async def fetch_match_list_raw(
    *,
    profile_id: int,
    player: str = "unknown user",
    match_type: int = 1,
    page: int = 1,
    record_count: int = 10,
    refresh: bool = False,
    force_transport: str = "curl",
) -> dict[str, Any]:
    body = build_match_list_body(
        profile_id=profile_id,
        gamertag=player or "unknown user",
        match_type=match_type,
        page=page,
        record_count=record_count,
    )
    cache_key = ("match_list", int(profile_id), str(player or "").casefold(), int(
        match_type), int(page), int(record_count), force_transport)
    now = time.time()

    cached = _leaderboard_cache.get(cache_key)
    if (
        not refresh
        and cached is not None
        and now - float(cached.get("created_at", 0)) < LEADERBOARD_CACHE_SECONDS
    ):
        payload = dict(cached["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(
            now - float(cached["created_at"]), 2)
        return payload

    result = post_json_with_curl(
        url=MATCH_LIST_URL,
        body=body,
        label="match_list",
        timeout_seconds=30,
    )
    result["cached"] = False
    result["cache_age_seconds"] = 0

    _leaderboard_cache[cache_key] = {
        "created_at": now,
        "payload": result,
    }
    return result


async def fetch_recent_match_history_raw(
    *,
    profile_ids: list[int | str] | None = None,
    profile_names: list[str] | None = None,
    count: int = 10,
    start: int = 1,
    refresh: bool = False,
) -> dict[str, Any]:
    params = build_recent_match_history_params(
        profile_ids=profile_ids,
        profile_names=profile_names,
    )
    cache_key = (
        "community_recent_match_history",
        tuple(str(value) for value in (profile_ids or [])),
        tuple(str(value) for value in (profile_names or [])),
        int(count),
        int(start),
    )
    now = time.time()

    cached = _leaderboard_cache.get(cache_key)
    if (
        not refresh
        and cached is not None
        and now - float(cached.get("created_at", 0)) < LEADERBOARD_CACHE_SECONDS
    ):
        payload = dict(cached["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(now - float(cached["created_at"]), 2)
        return payload

    result = get_json_with_curl(
        url=COMMUNITY_RECENT_MATCH_HISTORY_URL,
        params=params,
        label="community_recent_match_history",
        timeout_seconds=30,
    )
    result["cached"] = False
    result["cache_age_seconds"] = 0

    _leaderboard_cache[cache_key] = {
        "created_at": now,
        "payload": result,
    }
    return result


async def fetch_recent_match_history(
    *,
    profile_ids: list[int | str] | None = None,
    profile_names: list[str] | None = None,
    requested_profile_id: int | None = None,
    match_type: int | None = None,
    count: int = 10,
    start: int = 1,
    refresh: bool = False,
) -> dict[str, Any]:
    raw_response = await fetch_recent_match_history_raw(
        profile_ids=profile_ids,
        profile_names=profile_names,
        count=count,
        start=start,
        refresh=refresh,
    )
    raw_payload = raw_response.get("raw")
    profiles_by_id = build_recent_match_history_profile_lookup(raw_payload)
    raw_records = []

    if isinstance(raw_payload, dict) and isinstance(raw_payload.get("matchHistoryStats"), list):
        raw_records = [item for item in raw_payload.get("matchHistoryStats", []) if isinstance(item, dict)]

    matches = [
        normalize_recent_match_history_record(
            record,
            profiles_by_id=profiles_by_id,
            requested_profile_id=requested_profile_id,
            requested_match_type=match_type,
        )
        for record in raw_records
    ]

    if match_type is not None:
        allowed_match_types = set(get_match_type_filter_ids(match_type))
        matches = [
            match
            for match in matches
            if int(match.get("match_type") or -1) in allowed_match_types
        ]

    matches.sort(key=lambda item: item.get("sort_timestamp") or 0, reverse=True)
    start_index = max(0, int(start) - 1)
    end_index = start_index + max(1, int(count))

    return {
        "ok": bool(raw_response.get("ok")),
        "source": "community_recent_match_history",
        "data_source": build_source_meta(
            endpoint="community/leaderboard/getRecentMatchHistory",
            queue_id=match_type,
            expanded_match_type_ids=get_match_type_filter_ids(match_type),
            cached=raw_response.get("cached"),
            status_code=raw_response.get("status_code"),
            source="community_recent_match_history",
        ),
        "profile_ids": profile_ids or [],
        "profile_names": profile_names or [],
        "requested_profile_id": requested_profile_id,
        "match_type": match_type,
        "match_type_label": get_queue_label(match_type),
        "match_type_filter_ids": get_match_type_filter_ids(match_type),
        "status_code": raw_response.get("status_code"),
        "cached": raw_response.get("cached"),
        "shape": raw_response.get("shape"),
        "match_count": len(matches),
        "matches": matches[start_index:end_index],
        "profiles_by_id": profiles_by_id,
    }


async def fetch_player_match_list(
    *,
    profile_id: int,
    player: str = "unknown user",
    match_type: int = 1,
    page: int = 1,
    record_count: int = 10,
    refresh: bool = False,
    force_transport: str = "curl",
) -> dict[str, Any]:
    recent_profile_names = [player] if player and str(player).startswith("/") else None
    recent_history = await fetch_recent_match_history(
        profile_ids=[profile_id],
        profile_names=recent_profile_names,
        requested_profile_id=profile_id,
        match_type=match_type,
        count=record_count,
        start=((max(1, int(page)) - 1) * int(record_count)) + 1,
        refresh=refresh,
    )
    if recent_history.get("ok") and recent_history.get("matches"):
        return {
            **recent_history,
            "profile_id": profile_id,
            "player": player,
            "match_type": match_type,
            "match_type_label": get_queue_label(match_type),
            "cached": recent_history.get("cached"),
            "matches": recent_history.get("matches", []),
        }

    raw_response = await fetch_match_list_raw(
        profile_id=profile_id,
        player=player,
        match_type=match_type,
        page=page,
        record_count=record_count,
        refresh=refresh,
        force_transport=force_transport,
    )
    raw_records = collect_match_list_records(raw_response.get("raw"))
    matches = [
        normalize_match_list_record(
            record,
            requested_match_type=match_type,
        )
        for record in raw_records
    ]

    return {
        "ok": bool(raw_response.get("ok")),
        "source": "match_list",
        "data_source": build_source_meta(
            endpoint="api/GameStats/AgeMyth/GetMatchList",
            queue_id=match_type,
            expanded_match_type_ids=[match_type],
            cached=raw_response.get("cached"),
            status_code=raw_response.get("status_code"),
            source="match_list",
        ),
        "profile_id": profile_id,
        "player": player,
        "match_type": match_type,
        "match_type_label": get_queue_label(match_type),
        "status_code": raw_response.get("status_code"),
        "cached": raw_response.get("cached"),
        "shape": raw_response.get("shape"),
        "match_count": len(matches),
        "matches": matches[:record_count],
    }


def build_match_detail_body(
    *,
    profile_id: int | str,
    match_id: int | str,
) -> dict[str, Any]:
    return {
        "profileId": int(profile_id),
        "matchId": str(match_id),
    }


async def fetch_match_detail_raw(
    *,
    profile_id: int,
    match_id: int | str,
    refresh: bool = False,
    force_transport: str = "curl",
) -> dict[str, Any]:
    body = build_match_detail_body(profile_id=profile_id, match_id=match_id)
    cache_key = ("match_detail", int(profile_id),
                 str(match_id), force_transport)
    now = time.time()

    cached = _leaderboard_cache.get(cache_key)
    if (
        not refresh
        and cached is not None
        and now - float(cached.get("created_at", 0)) < LEADERBOARD_CACHE_SECONDS
    ):
        payload = dict(cached["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(
            now - float(cached["created_at"]), 2)
        return payload

    result = post_json_with_curl(
        url=MATCH_DETAIL_URL,
        body=body,
        label="match_detail",
        timeout_seconds=30,
    )
    result["cached"] = False
    result["cache_age_seconds"] = 0

    _leaderboard_cache[cache_key] = {
        "created_at": now,
        "payload": result,
    }
    return result


def deep_find_key_values(source: Any, wanted_keys: set[str]) -> list[Any]:
    found: list[Any] = []

    if isinstance(source, dict):
        for key, value in source.items():
            if key in wanted_keys and value not in (None, ""):
                found.append(value)

            if isinstance(value, (dict, list)):
                found.extend(deep_find_key_values(value, wanted_keys))

    elif isinstance(source, list):
        for item in source:
            found.extend(deep_find_key_values(item, wanted_keys))

    return found


def first_deep_value(source: Any, keys: list[str]) -> Any:
    values = deep_find_key_values(source, set(keys))
    return values[0] if values else None


def find_player_detail_record(source: Any, profile_id: int) -> dict[str, Any] | None:
    if isinstance(source, dict):
        possible_values = [
            source.get("profileId"),
            source.get("profile_id"),
            source.get("rlUserId"),
            source.get("rl_user_id"),
            source.get("userId"),
            source.get("user_id"),
        ]

        for possible_id in possible_values:
            if to_int_or_none(possible_id) == profile_id:
                return source

        for value in source.values():
            found = find_player_detail_record(value, profile_id)
            if found is not None:
                return found

    elif isinstance(source, list):
        for item in source:
            found = find_player_detail_record(item, profile_id)
            if found is not None:
                return found

    return None


def collect_match_players(raw_detail: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_detail, dict):
        return []

    players = raw_detail.get("playerList")
    if not isinstance(players, list):
        players = raw_detail.get("players")

    if not isinstance(players, list):
        players = []

    normalized_players: list[dict[str, Any]] = []

    for player in players:
        if not isinstance(player, dict):
            continue

        user_id = (
            get_first_value(
                player, ["userId", "user_id", "rlUserId", "rl_user_id"])
            or get_first_value(player, ["profileId", "profile_id"])
        )

        normalized_players.append(
            {
                "user_id": to_int_or_none(user_id),
                "profile_id": to_int_or_none(user_id),
                "name": clean_leaderboard_name(
                    get_first_value(
                        player, ["userName", "username", "name", "gamertag", "alias"])
                ),
                "avatar_url": get_first_value(player, ["avatarUrl", "avatar_url"]),
                "team": to_int_or_none(get_first_value(player, ["team", "teamId", "team_id"])),
                "god": resolve_legacy_race_name(
                    get_first_value(
                        player,
                        [
                            "civName",
                            "civilization",
                            "civilizationName",
                            "civ",
                            "race",
                            "raceId",
                            "race_id",
                            "majorGod",
                            "major_god",
                        ],
                    )
                ),
                "elo": to_int_or_none(get_first_value(player, ["elo", "rating", "playerElo", "player_rating"])),
                "rating_change": to_int_or_none(
                    get_first_value(player, ["eloChange", "elo_change", "ratingChange", "rating_change"])
                ),
                "result": normalize_match_result(
                    get_first_value(
                        player, ["winLoss", "result", "outcome", "playerResult", "won", "isWinner"])
                ),
                "is_human": get_first_value(player, ["isHuman", "is_human"]),
                "match_replay_available": bool(get_first_value(player, ["matchReplayAvailable", "match_replay_available"])),
            }
        )

    return normalized_players


def get_match_summary(raw_detail: Any) -> dict[str, Any]:
    if isinstance(raw_detail, dict) and isinstance(raw_detail.get("matchSummary"), dict):
        return raw_detail["matchSummary"]

    if isinstance(raw_detail, dict):
        return raw_detail

    return {}


def parse_match_sort_timestamp(value: Any) -> float:
    if value in (None, ""):
        return 0

    text = str(value).strip()

    # Avoid importing dateutil; try the common API format first, then ISO-like
    # formats. Sorting only needs relative ordering.
    for fmt in [
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            from datetime import datetime

            return datetime.strptime(text.split(".")[0], fmt).timestamp()
        except Exception:
            pass

    try:
        from datetime import datetime

        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0


def normalize_match_detail_for_player(
    *,
    raw_detail: Any,
    profile_id: int,
    match_id: str | int,
    requested_match_type: int | None = None,
) -> dict[str, Any]:
    summary = get_match_summary(raw_detail)
    players = collect_match_players(raw_detail)
    player_record = next(
        (
            player
            for player in players
            if to_int_or_none(player.get("user_id")) == profile_id
            or to_int_or_none(player.get("profile_id")) == profile_id
        ),
        None,
    )

    raw_map_name = (
        get_first_value(summary, [
                        "mapType", "mapName", "map_name", "map", "scenario", "scenarioName", "location"])
        or first_deep_value(raw_detail, ["mapType", "mapName", "map_name", "map", "scenario", "scenarioName", "location"])
    )
    decoded_map_name = (
        get_first_value(summary, ["mGameMapName", "gameMapName", "mapNameDecoded", "decodedMapName", "mGameFilename"])
        or first_deep_value(raw_detail, ["mGameMapName", "gameMapName", "mapNameDecoded", "decodedMapName", "mGameFilename"])
    )
    date_time = (
        get_first_value(summary, ["dateTime", "date_time",
                        "started", "startTime", "start_time", "matchDate"])
        or first_deep_value(raw_detail, ["dateTime", "date_time", "started", "startTime", "start_time", "matchDate"])
    )
    result = player_record.get("result") if player_record else (
        get_first_value(summary, [
                        "winLoss", "result", "outcome", "playerResult", "won", "isWinner", "victory"])
        or first_deep_value(raw_detail, ["winLoss", "result", "outcome", "playerResult", "won", "isWinner", "victory"])
    )
    match_type = get_record_match_type(
        summary,
        requested_match_type=requested_match_type,
    )
    if match_type is None:
        match_type = get_record_match_type(
            raw_detail if isinstance(raw_detail, dict) else {},
            requested_match_type=requested_match_type,
        )
    if match_type is None:
        match_type = requested_match_type
    rating_change = player_record.get("rating_change") if player_record and player_record.get(
        "rating_change") is not None else first_deep_value(
            raw_detail, ["eloChange", "elo_change", "ratingChange", "rating_change"]
        )
    rating = player_record.get("elo") if player_record and player_record.get(
        "elo") is not None else first_deep_value(raw_detail, ["elo", "rating", "playerElo", "player_rating"])
    civilization = player_record.get("god") if player_record else None
    match_length = (
        get_first_value(
            summary, ["matchLength", "match_length", "duration", "durationMinutes"])
        or first_deep_value(raw_detail, ["matchLength", "match_length", "duration", "durationMinutes"])
    )

    return {
        "match_id": str(match_id),
        "date_time": date_time,
        "sort_timestamp": parse_match_sort_timestamp(date_time),
        "map": format_map_name(str(raw_map_name) if raw_map_name is not None else None, str(decoded_map_name) if decoded_map_name is not None else None),
        "result": normalize_match_result(result),
        "match_type": match_type,
        "match_type_label": get_match_type_label(match_type),
        "rating": to_int_or_none(rating),
        "rating_change": to_int_or_none(rating_change),
        "civilization": civilization,
        "match_length": to_float_or_none(match_length),
        "players": players,
        "current_player": player_record,
        "detail_available": True,
    }


async def enrich_recent_matches_with_details(
    *,
    profile_id: int,
    matches: list[dict[str, Any]],
    refresh: bool = False,
    force_transport: str = "curl",
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for match in matches:
        match_id = match.get("match_id")

        if not match_id:
            enriched.append(match)
            continue

        try:
            detail_response = await fetch_match_detail_raw(
                profile_id=profile_id,
                match_id=match_id,
                refresh=refresh,
                force_transport=force_transport,
            )
        except Exception:
            enriched.append(match)
            continue

        if not detail_response.get("ok"):
            enriched.append(match)
            continue

        detail = normalize_match_detail_for_player(
            raw_detail=detail_response.get("raw"),
            profile_id=profile_id,
            match_id=match_id,
            requested_match_type=to_int_or_none(match.get("match_type")),
        )

        # Keep the list endpoint's known values, then fill missing/weak fields
        # from detail. Detail is preferred for map/result/rating fields.
        merged = {
            **match,
            "detail_available": True,
            "detail_status_code": detail_response.get("status_code"),
        }

        for key in ["map", "result", "match_type", "match_type_label", "rating", "rating_change", "civilization", "match_length", "players", "current_player", "sort_timestamp"]:
            if detail.get(key) not in (None, ""):
                merged[key] = detail.get(key)

        if detail.get("date_time") not in (None, "") and merged.get("date_time") in (None, ""):
            merged["date_time"] = detail.get("date_time")

        enriched.append(merged)

    enriched.sort(
        key=lambda match: (
            float(match.get("sort_timestamp") or parse_match_sort_timestamp(
                match.get("date_time")) or 0),
            int(match.get("match_id") or 0) if str(
                match.get("match_id") or "").isdigit() else 0,
        ),
        reverse=True,
    )

    return enriched


async def fetch_player_summary(
    *,
    profile_id: int,
    player: str = "unknown user",
    recent_match_type: int = 1,
    recent_count: int = 10,
    refresh: bool = False,
    force_transport: str = "curl",
) -> dict[str, Any]:
    ratings = []
    for queue in get_ranked_queues():
        match_type = int(queue["id"])
        rating_response = await fetch_player_rating(
            profile_id=profile_id,
            player=player,
            match_type=match_type,
            refresh=refresh,
            force_transport=force_transport,
        )
        ratings.append(
            {
                "match_type": match_type,
                "match_type_label": get_queue_label(match_type),
                "ok": bool(rating_response.get("ok")),
                "source": rating_response.get("source"),
                "data_source": rating_response.get("data_source"),
                "rating": rating_response.get("rating"),
                "reason": rating_response.get("reason"),
            }
        )

    recent_matches = await fetch_player_match_list(
        profile_id=profile_id,
        player=player,
        match_type=recent_match_type,
        page=1,
        record_count=recent_count,
        refresh=refresh,
        force_transport=force_transport,
    )

    if recent_matches.get("matches") and recent_matches.get("source") != "community_recent_match_history":
        recent_matches["matches"] = await enrich_recent_matches_with_details(
            profile_id=profile_id,
            matches=recent_matches.get("matches", []),
            refresh=refresh,
            force_transport=force_transport,
        )

    avatar_url = None
    display_name = player

    for rating_bucket in ratings:
        rating_record = rating_bucket.get("rating")
        if not isinstance(rating_record, dict):
            continue

        if not avatar_url and rating_record.get("avatar_url"):
            avatar_url = rating_record.get("avatar_url")

        if rating_record.get("name"):
            display_name = rating_record.get("name")

    return {
        "ok": True,
        "profile_id": profile_id,
        "player": player,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "ratings": ratings,
        "recent_match_type": recent_match_type,
        "recent_match_type_label": get_queue_label(recent_match_type),
        "recent_matches": recent_matches,
        "data_sources": {
            "ratings": [
                rating_bucket.get("data_source")
                for rating_bucket in ratings
                if rating_bucket.get("data_source")
            ],
            "recent_matches": recent_matches.get("data_source"),
        },
    }
