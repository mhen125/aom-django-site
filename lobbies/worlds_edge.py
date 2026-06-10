import asyncio
from typing import Any

import httpx


WORLD_EDGE_LOBBY_URL = (
    "https://athens-live-api.worldsedgelink.com"
    "/community/advertisement/findAdvertisements"
)

TITLE = "athens"
DEFAULT_START_VALUES = [0, 25, 50, 75]


async def fetch_lobby_page(client: httpx.AsyncClient, start: int) -> dict[str, Any]:
    response = await client.get(
        WORLD_EDGE_LOBBY_URL,
        params={
            "title": TITLE,
            "start": start,
        },
        headers={
            "Accept": "application/json",
            "User-Agent": "AoMRetoldLobbyBrowser/0.6.0",
        },
        timeout=15.0,
    )

    response.raise_for_status()
    return response.json()


async def fetch_raw_lobbies(start_values: list[int]) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        pages = await asyncio.gather(
            *[fetch_lobby_page(client, start) for start in start_values]
        )

    combined_matches_by_id: dict[int, dict[str, Any]] = {}
    combined_avatars_by_profile_id: dict[int, dict[str, Any]] = {}

    for page in pages:
        for match in page.get("matches", []):
            lobby_id = match.get("id")

            if lobby_id is not None:
                combined_matches_by_id[lobby_id] = match

        for avatar in page.get("avatars", []):
            profile_id = avatar.get("profile_id")

            if profile_id is not None:
                combined_avatars_by_profile_id[profile_id] = avatar

    return {
        "result": pages[0].get("result", {}) if pages else {},
        "matches": list(combined_matches_by_id.values()),
        "avatars": list(combined_avatars_by_profile_id.values()),
    }