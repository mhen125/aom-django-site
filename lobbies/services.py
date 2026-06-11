import time
from typing import Any

from .activity import (
    build_live_activity_payload,
    build_live_activity_payload_from_metadata,
    fetch_aomstats_lobby_metadata,
    fetch_steam_current_players,
    normalize_local_lobby,
)
from .normalizer import build_avatar_lookup, normalize_lobby
from .worlds_edge import DEFAULT_START_VALUES, fetch_raw_lobbies


CACHE_SECONDS = 20

_cache: dict[tuple[int, ...], dict[str, Any]] = {}

_live_activity_cache: dict[str, Any] = {
    "created_at": 0.0,
    "data": None,
}


async def get_normalized_lobbies(
    force_refresh: bool = False,
    start_values: list[int] | None = None,
) -> list[dict[str, Any]]:
    now = time.time()

    if start_values is None:
        start_values = DEFAULT_START_VALUES

    cache_key = tuple(start_values)
    cache_entry = _cache.get(cache_key)

    if (
        not force_refresh
        and cache_entry is not None
        and now - cache_entry["created_at"] < CACHE_SECONDS
    ):
        return cache_entry["data"]

    raw_data = await fetch_raw_lobbies(start_values)
    avatars_by_profile_id = build_avatar_lookup(raw_data)

    normalized_lobbies = [
        normalize_lobby(raw_lobby, avatars_by_profile_id)
        for raw_lobby in raw_data.get("matches", [])
    ]

    normalized_lobbies.sort(
        key=lambda lobby: lobby.get("id") or 0,
        reverse=True,
    )

    _cache[cache_key] = {
        "created_at": now,
        "data": normalized_lobbies,
    }

    return normalized_lobbies


async def get_live_activity(force_refresh: bool = False) -> dict:
    now = time.time()

    if (
        not force_refresh
        and _live_activity_cache["data"] is not None
        and now - _live_activity_cache["created_at"] < CACHE_SECONDS
    ):
        return _live_activity_cache["data"]

    steam_players_online = await fetch_steam_current_players()

    try:
        metadata = await fetch_aomstats_lobby_metadata()
        payload = build_live_activity_payload_from_metadata(
            metadata,
            steam_players_online=steam_players_online,
        )
    except Exception:
        # Fall back to the older Worlds Edge-derived payload so the home page does
        # not go completely dark if aomstats changes or temporarily fails.
        normalized_lobbies = await get_normalized_lobbies(force_refresh=force_refresh)
        activity_lobbies = [
            normalize_local_lobby(lobby)
            for lobby in normalized_lobbies
        ]

        payload = build_live_activity_payload(
            activity_lobbies,
            steam_players_online=steam_players_online,
            source="worldsedge",
        )

    _live_activity_cache["created_at"] = time.time()
    _live_activity_cache["data"] = payload

    return payload
