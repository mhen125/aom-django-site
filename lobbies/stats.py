from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .leaderboard import (
    enrich_recent_matches_with_details,
    fetch_player_match_list,
    get_match_type_label,
)

MATCH_TYPES = [1, 2, 3, 4]


def _normalize_text(value: Any, fallback: str = "Unknown") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _normalize_result(value: Any) -> str:
    text = str(value or "").strip().lower()

    if text in {"win", "won", "victory", "true", "1"}:
        return "win"

    if text in {"loss", "lost", "defeat", "false", "0"}:
        return "loss"

    return "unknown"


def _percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0

    return round((count / total) * 100, 2)


def _match_identity(match: dict[str, Any], match_type: int) -> str:
    match_id = match.get("match_id") or match.get("id")

    if match_id not in (None, ""):
        return str(match_id)

    return "|".join(
        [
            str(match_type),
            str(match.get("date_time") or match.get("sort_timestamp") or ""),
            str(match.get("map") or ""),
            str(match.get("civilization") or ""),
        ]
    )


def _get_player_god(match: dict[str, Any], profile_id: int) -> str:
    direct_value = match.get("civilization") or match.get("god") or match.get("major_god")

    if direct_value:
        return _normalize_text(direct_value)

    current_player = match.get("current_player")

    if isinstance(current_player, dict):
        value = current_player.get("god") or current_player.get("civilization") or current_player.get("civ")

        if value:
            return _normalize_text(value)

    players = match.get("players")

    if isinstance(players, list):
        for player in players:
            if not isinstance(player, dict):
                continue

            possible_ids = [
                player.get("profile_id"),
                player.get("user_id"),
                player.get("rl_user_id"),
                player.get("rlUserId"),
            ]

            if any(str(value) == str(profile_id) for value in possible_ids if value not in (None, "")):
                value = player.get("god") or player.get("civilization") or player.get("civ")

                if value:
                    return _normalize_text(value)

    return "Unknown"


def _serialize_counter(counter: Counter[str], total: int, limit: int | None = None) -> list[dict[str, Any]]:
    items = counter.most_common(limit)

    return [
        {
            "name": name,
            "count": count,
            "percent": _percent(count, total),
        }
        for name, count in items
    ]


async def build_player_recent_stats(
    *,
    profile_id: int,
    player: str = "unknown user",
    recent_count: int = 25,
    match_types: list[int] | None = None,
    refresh: bool = False,
    force_transport: str = "curl",
) -> dict[str, Any]:
    selected_match_types = match_types or MATCH_TYPES
    all_matches: list[dict[str, Any]] = []
    seen_match_ids: set[str] = set()
    sources: list[dict[str, Any]] = []

    for match_type in selected_match_types:
        response = await fetch_player_match_list(
            profile_id=profile_id,
            player=player,
            match_type=match_type,
            page=1,
            record_count=recent_count,
            refresh=refresh,
            force_transport=force_transport,
        )

        matches = response.get("matches") or []

        if matches:
            matches = await enrich_recent_matches_with_details(
                profile_id=profile_id,
                matches=matches,
                refresh=refresh,
                force_transport=force_transport,
            )

        sources.append(
            {
                "match_type": match_type,
                "match_type_label": get_match_type_label(match_type),
                "ok": bool(response.get("ok")),
                "match_count": len(matches),
                "cached": response.get("cached"),
            }
        )

        for match in matches:
            match_id = _match_identity(match, match_type)

            if match_id in seen_match_ids:
                continue

            seen_match_ids.add(match_id)
            enriched_match = dict(match)
            enriched_match["match_type"] = match_type
            enriched_match["match_type_label"] = get_match_type_label(match_type)
            all_matches.append(enriched_match)

    all_matches.sort(
        key=lambda match: (
            float(match.get("sort_timestamp") or 0),
            str(match.get("match_id") or ""),
        ),
        reverse=True,
    )

    total_matches = len(all_matches)
    god_counts: Counter[str] = Counter()
    map_counts: Counter[str] = Counter()
    match_type_counts: Counter[str] = Counter()
    result_counts: Counter[str] = Counter()
    god_results: dict[str, Counter[str]] = defaultdict(Counter)
    god_match_types: dict[str, Counter[str]] = defaultdict(Counter)

    for match in all_matches:
        god = _get_player_god(match, profile_id)
        map_name = _normalize_text(match.get("map"))
        result = _normalize_result(match.get("result"))
        match_type_label = _normalize_text(match.get("match_type_label"))

        god_counts[god] += 1
        map_counts[map_name] += 1
        match_type_counts[match_type_label] += 1
        result_counts[result] += 1
        god_results[god][result] += 1
        god_match_types[god][match_type_label] += 1

    gods: list[dict[str, Any]] = []

    for god, count in god_counts.most_common():
        wins = god_results[god].get("win", 0)
        losses = god_results[god].get("loss", 0)
        known_results = wins + losses

        gods.append(
            {
                "name": god,
                "count": count,
                "percent": _percent(count, total_matches),
                "wins": wins,
                "losses": losses,
                "win_rate": _percent(wins, known_results),
                "match_types": _serialize_counter(god_match_types[god], count),
            }
        )

    return {
        "ok": True,
        "profile_id": profile_id,
        "player": player,
        "recent_count_per_match_type": recent_count,
        "match_types": selected_match_types,
        "total_matches": total_matches,
        "sources": sources,
        "summary": {
            "unique_gods": len(god_counts),
            "wins": result_counts.get("win", 0),
            "losses": result_counts.get("loss", 0),
            "unknown_results": result_counts.get("unknown", 0),
            "win_rate": _percent(result_counts.get("win", 0), result_counts.get("win", 0) + result_counts.get("loss", 0)),
        },
        "gods": gods,
        "maps": _serialize_counter(map_counts, total_matches, limit=10),
        "match_type_breakdown": _serialize_counter(match_type_counts, total_matches),
        "results": dict(result_counts),
        "matches": all_matches,
    }
