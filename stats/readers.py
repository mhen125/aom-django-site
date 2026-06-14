from __future__ import annotations

from typing import Any

from django.db.models import Prefetch

from lobbies.leaderboard_metadata import get_match_type_label, get_match_type_meta, get_ranked_match_type_ids

from .models import MatchParticipant, Player


def _percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((count / total) * 100, 2)


def _player_name(player_row: Player) -> str:
    return (
        player_row.alias
        or player_row.display_name
        or str(player_row.profile_id or player_row.pk)
    )


def _get_personal_stat_ratings(player_row: Player) -> list[dict[str, Any]]:
    raw = player_row.raw_identity or {}
    if not isinstance(raw, dict):
        return []

    ratings = raw.get("personal_stat_ratings")
    if not isinstance(ratings, list):
        return []

    return [item for item in ratings if isinstance(item, dict)]


def _get_queue_rating_from_identity(player_row: Player, match_type: int) -> dict[str, Any] | None:
    leaderboard_id = get_match_type_meta(match_type).get("leaderboard_id") if get_match_type_meta(match_type) else None

    for item in _get_personal_stat_ratings(player_row):
        queue_id = item.get("queue_id") or item.get("leaderboard_id") or item.get("match_type")
        if leaderboard_id is not None and int(queue_id or 0) == int(leaderboard_id):
            return item

    return None


def _rating_row_from_identity(player_row: Player, match_type: int | None = None) -> dict[str, Any]:
    raw = player_row.raw_identity or {}
    if not isinstance(raw, dict):
        raw = {}

    if match_type is not None:
        queue_rating = _get_queue_rating_from_identity(player_row, match_type)
        if queue_rating:
            return {
                "rank": queue_rating.get("rank"),
                "rank_total": queue_rating.get("rank_total"),
                "rating": queue_rating.get("rating"),
                "elo": queue_rating.get("elo"),
                "highest_rating": queue_rating.get("highest_rating"),
                "wins": queue_rating.get("wins"),
                "losses": queue_rating.get("losses"),
                "games": queue_rating.get("games"),
                "win_rate": queue_rating.get("win_rate"),
                "streak": queue_rating.get("streak"),
                "country": queue_rating.get("country") or raw.get("country"),
                "region": queue_rating.get("region") or raw.get("region"),
                "avatar_url": queue_rating.get("avatar_url") or raw.get("avatar_url"),
                "raw": queue_rating.get("raw") if isinstance(queue_rating.get("raw"), dict) else queue_rating,
            }

    return {
        "rank": raw.get("rank"),
        "rank_total": raw.get("rank_total"),
        "rating": raw.get("rating"),
        "elo": raw.get("elo"),
        "highest_rating": raw.get("highest_rating"),
        "wins": raw.get("wins"),
        "losses": raw.get("losses"),
        "games": raw.get("games"),
        "win_rate": raw.get("win_rate"),
        "streak": raw.get("streak"),
        "country": raw.get("country"),
        "region": raw.get("region"),
        "avatar_url": raw.get("avatar_url"),
        "raw": raw,
    }


def _player_matches_queue(player_row: Player, match_type: int) -> bool:
    if _get_queue_rating_from_identity(player_row, match_type):
        return True

    raw = player_row.raw_identity or {}
    if not isinstance(raw, dict):
        return False

    leaderboard_id = get_match_type_meta(match_type).get("leaderboard_id") if get_match_type_meta(match_type) else None
    raw_stats = raw.get("raw", {}).get("leaderboard_stats") if isinstance(raw.get("raw"), dict) else None
    if isinstance(raw_stats, dict) and leaderboard_id is not None:
        return int(raw_stats.get("leaderboard_id") or 0) == int(leaderboard_id)

    return True


def _player_has_imported_ladder_row(player_row: Player) -> bool:
    if _get_personal_stat_ratings(player_row):
        return True

    raw = player_row.raw_identity or {}
    if not isinstance(raw, dict):
        return False
    return raw.get("rank") is not None and raw.get("rating") is not None


def get_imported_leaderboard_rows(
    *,
    match_type: int,
    page: int = 1,
    count: int = 25,
    player: str = "",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    query = player.strip().casefold()

    for item in Player.objects.exclude(profile_id__isnull=True).order_by("id"):
        raw = item.raw_identity or {}
        if not isinstance(raw, dict):
            continue
        if not _player_has_imported_ladder_row(item):
            continue
        if not _player_matches_queue(item, match_type):
            continue

        name = _player_name(item)
        if query and query not in name.casefold():
            continue

        rows.append(
            {
                "name": name,
                "profile_id": item.profile_id,
                **_rating_row_from_identity(item, match_type),
                "source": "imported_stats",
                "raw": raw,
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("rank") if row.get("rank") is not None else 999999999,
            str(row.get("name") or "").casefold(),
        )
    )

    start_index = max(0, (max(1, int(page)) - 1) * int(count))
    end_index = start_index + int(count)
    paged_rows = rows[start_index:end_index]

    return {
        "query": player,
        "source": "imported_stats",
        "status_code": 200,
        "ok": True,
        "cached": False,
        "shape": {
            "type": "imported_stats",
            "player_count": len(rows),
        },
        "match_count": len(paged_rows),
        "total_count": len(rows),
        "matches": paged_rows,
    }


def get_imported_player_rating(
    *,
    profile_id: int | None = None,
    player: str = "",
    match_type: int = 1,
) -> dict[str, Any] | None:
    player_row = None

    if profile_id is not None:
        player_row = Player.objects.filter(profile_id=profile_id).first()
    elif player:
        player_row = Player.objects.filter(alias__iexact=player).first() or Player.objects.filter(display_name__iexact=player).first()

    resolved_profile_id = player_row.profile_id if player_row and player_row.profile_id is not None else profile_id
    if resolved_profile_id is None:
        return None

    participant_qs = MatchParticipant.objects.filter(profile_id=resolved_profile_id, match__match_type_id=match_type)
    latest_participant = (
        participant_qs
        .select_related("match")
        .order_by("-match__started_at", "-match_id")
        .first()
    )

    if player_row is None and latest_participant is None:
        return None

    has_ladder_row = bool(player_row and _player_has_imported_ladder_row(player_row))

    if latest_participant is None and not (has_ladder_row and player_row is not None and _player_matches_queue(player_row, match_type)):
        return None

    raw = player_row.raw_identity if player_row and isinstance(player_row.raw_identity, dict) else {}
    rating_row = _rating_row_from_identity(player_row, match_type) if player_row else {}

    derived_rating = latest_participant.rating if latest_participant and latest_participant.rating is not None else None
    derived_games = participant_qs.count()
    derived_wins = participant_qs.filter(result=MatchParticipant.RESULT_WIN).count()
    derived_losses = participant_qs.filter(result=MatchParticipant.RESULT_LOSS).count()
    display_name = _player_name(player_row) if player_row else (latest_participant.alias if latest_participant else player)
    avatar_url = rating_row.get("avatar_url") or (player_row.avatar_url if player_row else "")
    country = rating_row.get("country") or (player_row.country_code if player_row else "")

    rating = {
        "source": "imported_stats",
        "name": display_name,
        "raw_name": raw.get("raw_name") or display_name,
        "profile_id": resolved_profile_id,
        "rl_user_id": resolved_profile_id,
        "match_type": match_type,
        "match_type_label": get_match_type_label(match_type),
        "rating": rating_row.get("rating") if rating_row.get("rating") is not None else derived_rating,
        "elo": rating_row.get("elo") if rating_row.get("elo") is not None else derived_rating,
        "highest_rating": rating_row.get("highest_rating") if rating_row.get("highest_rating") is not None else derived_rating,
        "rank": rating_row.get("rank") if has_ladder_row else None,
        "rank_total": rating_row.get("rank_total") if has_ladder_row else None,
        "wins": rating_row.get("wins") if rating_row.get("wins") is not None else derived_wins,
        "losses": rating_row.get("losses") if rating_row.get("losses") is not None else derived_losses,
        "games": rating_row.get("games") if rating_row.get("games") is not None else derived_games,
        "win_rate": rating_row.get("win_rate") if rating_row.get("win_rate") is not None else _percent(derived_wins, derived_wins + derived_losses),
        "streak": rating_row.get("streak") if has_ladder_row else None,
        "avatar_url": avatar_url,
        "country": country,
        "raw": raw,
    }

    return {
        "ok": True,
        "source": "imported_stats",
        "profile_id": resolved_profile_id,
        "player": display_name,
        "requested_match_type": match_type,
        "requested_match_type_label": get_match_type_label(match_type),
        "rating": rating,
        "ratings": [rating],
        "leaderboard_fallback_used": False,
    }


def _collect_imported_player_ratings(
    *,
    profile_id: int,
    player: str = "",
) -> list[dict[str, Any]]:
    player_row = Player.objects.filter(profile_id=profile_id).first()
    if player_row is not None:
        personal_stat_ratings = _get_personal_stat_ratings(player_row)
        if personal_stat_ratings:
            rows: list[dict[str, Any]] = []
            seen_match_types: set[int] = set()
            for rating in personal_stat_ratings:
                match_type = int(rating.get("match_type") or rating.get("queue_id") or 0)
                if match_type <= 0 or match_type in seen_match_types:
                    continue
                seen_match_types.add(match_type)
                rows.append(
                    {
                        "match_type": match_type,
                        "match_type_label": rating.get("match_type_label") or rating.get("queue_label") or get_match_type_label(match_type),
                        "ok": rating.get("rating") is not None,
                        "source": "imported_stats",
                        "rating": rating,
                        "reason": None if rating.get("rating") is not None else "No rating returned.",
                    }
                )
            if rows:
                rows.sort(key=lambda item: item["match_type"])
                return rows

    ratings: list[dict[str, Any]] = []

    for match_type in get_ranked_match_type_ids():
        rating_response = get_imported_player_rating(
            profile_id=profile_id,
            player=player,
            match_type=match_type,
        )
        ratings.append(
            {
                "match_type": match_type,
                "match_type_label": get_match_type_label(match_type),
                "ok": bool(rating_response.get("ok")) if isinstance(rating_response, dict) else False,
                "source": rating_response.get("source") if isinstance(rating_response, dict) else None,
                "rating": rating_response.get("rating") if isinstance(rating_response, dict) else None,
                "reason": rating_response.get("reason") if isinstance(rating_response, dict) else None,
            }
        )

    return ratings


def _serialize_imported_match(participant: MatchParticipant, current_profile_id: int) -> dict[str, Any]:
    match = participant.match
    players = list(match.participants.all())
    result = "Unknown"
    if participant.result == MatchParticipant.RESULT_WIN:
        result = "Win"
    elif participant.result == MatchParticipant.RESULT_LOSS:
        result = "Loss"

    return {
        "match_id": match.external_match_id,
        "date_time": match.started_at.isoformat() if match.started_at else None,
        "map": match.map_name,
        "result": result,
        "match_type": match.match_type_id,
        "match_type_label": match.match_type_label or get_match_type_label(match.match_type_id),
        "rating": participant.rating,
        "rating_change": participant.rating_change,
        "civilization": participant.civilization,
        "match_length": match.duration_seconds,
        "players": [
            {
                "profile_id": item.profile_id,
                "user_id": item.profile_id,
                "name": item.alias,
                "team": item.team,
                "god": item.civilization,
                "result": "Win" if item.result == MatchParticipant.RESULT_WIN else "Loss" if item.result == MatchParticipant.RESULT_LOSS else "Unknown",
            }
            for item in players
        ],
        "current_player": {
            "profile_id": current_profile_id,
            "user_id": current_profile_id,
            "name": participant.alias,
            "god": participant.civilization,
            "result": result,
        },
        "detail_available": True,
        "source": "imported_stats",
    }


def get_imported_player_summary(
    *,
    profile_id: int,
    player: str = "unknown user",
    recent_match_type: int = 1,
    recent_count: int = 10,
) -> dict[str, Any] | None:
    player_row = Player.objects.filter(profile_id=profile_id).first()
    participant_qs = (
        MatchParticipant.objects
        .filter(profile_id=profile_id, match__match_type_id=recent_match_type)
        .select_related("match", "player")
        .prefetch_related(Prefetch("match__participants", queryset=MatchParticipant.objects.all()))
        .order_by("-match__started_at", "-match_id")[:recent_count]
    )
    participants = list(participant_qs)

    if player_row is None and not participants:
        return None

    rating_payload = get_imported_player_rating(
        profile_id=profile_id,
        player=player,
        match_type=recent_match_type,
    )
    ratings = _collect_imported_player_ratings(
        profile_id=profile_id,
        player=player,
    )

    recent_matches = [_serialize_imported_match(item, profile_id) for item in participants]

    return {
        "ok": True,
        "source": "imported_stats",
        "profile_id": profile_id,
        "player": player,
        "display_name": _player_name(player_row) if player_row else (participants[0].alias if participants else player),
        "avatar_url": player_row.avatar_url if player_row else None,
        "ratings": ratings,
        "active_rating": rating_payload.get("rating") if rating_payload else None,
        "recent_match_type": recent_match_type,
        "recent_match_type_label": get_match_type_label(recent_match_type),
        "recent_matches": {
            "ok": True,
            "source": "imported_stats",
            "profile_id": profile_id,
            "player": player,
            "match_type": recent_match_type,
            "match_type_label": get_match_type_label(recent_match_type),
            "status_code": 200,
            "cached": False,
            "shape": {"type": "imported_stats", "participant_count": len(participants)},
            "match_count": len(recent_matches),
            "matches": recent_matches,
        },
    }


def get_imported_player_recent_stats(
    *,
    profile_id: int,
    player: str = "unknown user",
    recent_count: int = 25,
    match_types: list[int] | None = None,
) -> dict[str, Any] | None:
    selected_match_types = match_types or []
    participant_qs = (
        MatchParticipant.objects
        .filter(profile_id=profile_id, match__match_type_id__in=selected_match_types)
        .select_related("match")
        .order_by("-match__started_at", "-match_id")[: max(1, int(recent_count)) * max(1, len(selected_match_types))]
    )
    participants = list(participant_qs)
    if not participants:
        return None

    matches = [_serialize_imported_match(item, profile_id) for item in participants]
    total_matches = len(matches)
    wins = sum(1 for item in participants if item.result == MatchParticipant.RESULT_WIN)
    losses = sum(1 for item in participants if item.result == MatchParticipant.RESULT_LOSS)

    god_counts: dict[str, int] = {}
    god_wins: dict[str, int] = {}
    map_counts: dict[str, int] = {}
    match_type_counts: dict[str, int] = {}

    for item in participants:
        god_name = item.civilization or "Unknown"
        map_name = item.match.map_name or "Unknown"
        queue_label = item.match.match_type_label or get_match_type_label(item.match.match_type_id)

        god_counts[god_name] = god_counts.get(god_name, 0) + 1
        map_counts[map_name] = map_counts.get(map_name, 0) + 1
        match_type_counts[queue_label] = match_type_counts.get(queue_label, 0) + 1
        if item.result == MatchParticipant.RESULT_WIN:
            god_wins[god_name] = god_wins.get(god_name, 0) + 1

    gods = []
    for god_name, count in sorted(god_counts.items(), key=lambda item: (-item[1], item[0].casefold())):
        gods.append(
            {
                "name": god_name,
                "count": count,
                "percent": _percent(count, total_matches),
                "wins": god_wins.get(god_name, 0),
                "losses": count - god_wins.get(god_name, 0),
                "win_rate": _percent(god_wins.get(god_name, 0), count),
                "match_types": [],
            }
        )

    maps = [
        {"name": name, "count": count, "percent": _percent(count, total_matches)}
        for name, count in sorted(map_counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    ]
    breakdown = [
        {"name": name, "count": count, "percent": _percent(count, total_matches)}
        for name, count in sorted(match_type_counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    ]

    return {
        "ok": True,
        "source": "imported_stats",
        "profile_id": profile_id,
        "player": player,
        "recent_count_per_match_type": recent_count,
        "match_types": selected_match_types,
        "total_matches": total_matches,
        "sources": [{"source": "imported_stats", "match_count": total_matches}],
        "summary": {
            "unique_gods": len(god_counts),
            "wins": wins,
            "losses": losses,
            "unknown_results": total_matches - wins - losses,
            "win_rate": _percent(wins, wins + losses),
        },
        "gods": gods,
        "maps": maps[:10],
        "match_type_breakdown": breakdown,
        "results": {"win": wins, "loss": losses, "unknown": total_matches - wins - losses},
        "matches": matches,
    }
