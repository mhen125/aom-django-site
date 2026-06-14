from collections import Counter
from datetime import datetime, timezone
from typing import Any

from asgiref.sync import async_to_sync
from django.db import transaction

from lobbies.leaderboard import (
    fetch_community_leaderboard2,
    fetch_match_detail_raw,
    fetch_recent_match_history,
    fetch_player_match_list,
    normalize_match_detail_for_player,
)
from lobbies.leaderboard_metadata import get_match_type_label, get_match_type_meta

from .models import Match, MatchParticipant, Player, ReplayParse
from .replay_filters import ReplayPipelineFilters, apply_match_filters


def parse_upstream_datetime(value: Any):
    if value in (None, ""):
        return None

    text = str(value).strip()

    for fmt in [
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            parsed = datetime.strptime(text.split(".")[0], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_player_payload(base: dict[str, Any] | None = None, override: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if isinstance(base, dict):
        payload.update(base)
    if isinstance(override, dict):
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(payload.get(key), dict):
                payload[key] = _normalize_player_payload(payload.get(key), value)
            elif value not in (None, "", {}, []):
                payload[key] = value
    return payload


def _upsert_player_from_identity(
    *,
    profile_id: int | None,
    alias: str = "",
    display_name: str = "",
    avatar_url: str = "",
    country_code: str = "",
    raw_identity: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> Player | None:
    if not profile_id:
        return None

    if dry_run:
        return None

    existing = Player.objects.filter(profile_id=int(profile_id)).first()
    merged_raw_identity = _normalize_player_payload(
        existing.raw_identity if existing else {},
        raw_identity or {},
    )

    defaults = {
        "platform": Player.PLATFORM_UNKNOWN,
        "platform_id": "",
        "alias": alias or display_name or "",
        "display_name": display_name or alias or "",
        "avatar_url": avatar_url or "",
        "country_code": country_code or "",
        "raw_identity": merged_raw_identity,
        "last_seen_at": datetime.now(timezone.utc),
    }
    player, _created = Player.objects.update_or_create(
        profile_id=int(profile_id),
        defaults=defaults,
    )
    return player


def _build_match_defaults(
    *,
    external_match_id: str,
    requested_match_type: int,
    match_row: dict[str, Any],
    detail_match: dict[str, Any],
    detail_raw: dict[str, Any] | None,
) -> dict[str, Any]:
    players = detail_match.get("players") or []
    teams = [player.get("team") for player in players if player.get("team") is not None]
    team_counts = Counter(teams)
    winning_team = None

    for player in players:
        if str(player.get("result") or "").casefold() == "win" and player.get("team") is not None:
            winning_team = int(player["team"])
            break

    distinct_teams = len(team_counts)
    max_team_size = max(team_counts.values()) if team_counts else None
    is_team_game = bool(max_team_size and max_team_size > 1)
    match_type_meta = get_match_type_meta(detail_match.get("match_type") or requested_match_type) or {}

    started_at = parse_upstream_datetime(detail_match.get("date_time") or match_row.get("date_time"))
    duration_seconds = detail_match.get("match_length") or match_row.get("duration")
    try:
        duration_seconds = int(float(duration_seconds)) if duration_seconds not in (None, "") else None
    except (TypeError, ValueError):
        duration_seconds = None

    raw_payload = detail_raw if isinstance(detail_raw, dict) and detail_raw else (match_row.get("raw") or {})

    return {
        "source": Match.SOURCE_WORLDSEDGE,
        "match_type_id": int(detail_match.get("match_type") or requested_match_type),
        "match_type_label": detail_match.get("match_type_label") or get_match_type_label(requested_match_type),
        "leaderboard_id": match_type_meta.get("leaderboard_id"),
        "is_ranked": bool(match_type_meta.get("is_ranked", True)),
        "is_team_game": is_team_game,
        "team_size": max_team_size if is_team_game else 1 if distinct_teams == 2 else None,
        "map_name": detail_match.get("map") or match_row.get("map") or "",
        "started_at": started_at,
        "completed_at": started_at,
        "duration_seconds": duration_seconds,
        "winning_team": winning_team,
        "patch_label": "",
        "replay_url": _extract_replay_url(match_row=match_row, detail_match=detail_match, detail_raw=detail_raw),
        "replay_available": any(bool(player.get("match_replay_available")) for player in players),
        "raw_payload": raw_payload,
    }


def _extract_replay_url(
    *,
    match_row: dict[str, Any],
    detail_match: dict[str, Any],
    detail_raw: dict[str, Any] | None,
) -> str:
    candidates = [
        match_row,
        detail_match,
        detail_raw if isinstance(detail_raw, dict) else {},
        (detail_raw or {}).get("replay") if isinstance(detail_raw, dict) else {},
    ]

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in [
            "replay_url",
            "replayUrl",
            "match_replay_url",
            "matchReplayUrl",
            "download_replay_url",
            "downloadReplayUrl",
            "url",
        ]:
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _seed_replay_parse(match: Match):
    replay_url = match.replay_url or ""
    replay_parse, created = ReplayParse.objects.get_or_create(
        match=match,
        defaults={
            "status": ReplayParse.STATUS_PENDING,
            "replay_url": replay_url,
            "extracted_facts": {
                "replay_available": bool(match.replay_available),
            },
        },
    )

    if created:
        return

    changed_fields: list[str] = []

    if replay_url and replay_parse.replay_url != replay_url:
        replay_parse.replay_url = replay_url
        changed_fields.append("replay_url")

    extracted_facts = replay_parse.extracted_facts if isinstance(replay_parse.extracted_facts, dict) else {}
    if match.replay_available and not extracted_facts.get("replay_available"):
        replay_parse.extracted_facts = {
            **extracted_facts,
            "replay_available": True,
        }
        changed_fields.append("extracted_facts")

    if changed_fields:
        changed_fields.append("updated_at")
        replay_parse.save(update_fields=changed_fields)


def backfill_replay_parses(
    *,
    match_ids: list[str] | None = None,
    limit: int | None = None,
    ranked_only: bool = False,
    replay_available_only: bool = True,
    match_type_ids: list[int] | None = None,
    one_v_one_only: bool = False,
    started_after=None,
    missing_replay_url_only: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    filters = ReplayPipelineFilters(
        match_ids=[str(match_id) for match_id in (match_ids or []) if str(match_id).strip()],
        ranked_only=ranked_only,
        replay_available_only=replay_available_only,
        match_type_ids=[int(match_type_id) for match_type_id in (match_type_ids or [])],
        one_v_one_only=one_v_one_only,
        started_after=started_after,
        missing_replay_url_only=missing_replay_url_only,
    )
    queryset = apply_match_filters(Match.objects.order_by("-started_at", "-id"), filters)

    if limit is not None and int(limit) > 0:
        queryset = queryset[: int(limit)]

    matches = list(queryset)
    results = {
        "ok": True,
        "dry_run": dry_run,
        "ranked_only": ranked_only,
        "replay_available_only": replay_available_only,
        "match_type_ids": filters.match_type_ids,
        "one_v_one_only": one_v_one_only,
        "started_after": started_after.isoformat() if started_after else None,
        "missing_replay_url_only": missing_replay_url_only,
        "requested_match_ids": [str(match_id) for match_id in (match_ids or []) if str(match_id).strip()],
        "matches_scanned": len(matches),
        "rows_created": 0,
        "rows_updated": 0,
        "rows_unchanged": 0,
        "events": [],
    }

    for match in matches:
        before = ReplayParse.objects.filter(match=match).first()
        before_status = before.status if before else None
        before_replay_url = before.replay_url if before else ""
        before_facts = before.extracted_facts if before and isinstance(before.extracted_facts, dict) else {}

        if not dry_run:
            _seed_replay_parse(match)

        after_exists = bool(before) or (match.replay_available or match.replay_url)
        after_status = before_status or ReplayParse.STATUS_PENDING
        changed = False
        created = before is None

        if created:
            results["rows_created"] += 1
            changed = True
        else:
            expected_replay_available = bool(match.replay_available)
            expected_replay_url = match.replay_url or ""
            replay_available_changed = expected_replay_available and not bool(before_facts.get("replay_available"))
            replay_url_changed = bool(expected_replay_url and expected_replay_url != before_replay_url)
            if replay_available_changed or replay_url_changed:
                results["rows_updated"] += 1
                changed = True
            else:
                results["rows_unchanged"] += 1

        results["events"].append(
            {
                "match_id": match.external_match_id,
                "created": created,
                "changed": changed,
                "status": after_status,
                "replay_available": bool(match.replay_available),
                "replay_url_present": bool(match.replay_url),
                "row_expected": after_exists,
                "dry_run": dry_run,
            }
        )

    return results


def _upsert_match_with_participants(
    *,
    external_match_id: str,
    requested_match_type: int,
    match_row: dict[str, Any],
    detail_match: dict[str, Any],
    detail_raw: dict[str, Any] | None,
    dry_run: bool = False,
) -> tuple[Match | None, int]:
    defaults = _build_match_defaults(
        external_match_id=external_match_id,
        requested_match_type=requested_match_type,
        match_row=match_row,
        detail_match=detail_match,
        detail_raw=detail_raw,
    )

    if dry_run:
        participants = detail_match.get("players") or []
        return None, len(participants) if participants else 1

    with transaction.atomic():
        match, _created = Match.objects.update_or_create(
            external_match_id=str(external_match_id),
            defaults=defaults,
        )

        participants = detail_match.get("players") or []
        imported_participants = 0

        if participants:
            for index, participant in enumerate(participants):
                participant_profile_id = participant.get("profile_id") or participant.get("user_id")
                player = _upsert_player_from_identity(
                    profile_id=participant_profile_id,
                    alias=participant.get("name") or "",
                    display_name=participant.get("name") or "",
                    avatar_url=participant.get("avatar_url") or "",
                    raw_identity=participant,
                    dry_run=dry_run,
                )

                result_value = str(participant.get("result") or "").casefold()
                if result_value == "win":
                    result = MatchParticipant.RESULT_WIN
                    won = True
                elif result_value == "loss":
                    result = MatchParticipant.RESULT_LOSS
                    won = False
                else:
                    result = MatchParticipant.RESULT_UNKNOWN
                    won = None

                slot_value = participant.get("slot")
                if slot_value in (None, ""):
                    slot_value = index + 1

                MatchParticipant.objects.update_or_create(
                    match=match,
                    team=participant.get("team"),
                    slot=slot_value,
                    defaults={
                        "player": player,
                        "profile_id": int(participant_profile_id) if participant_profile_id not in (None, "") else None,
                        "alias": participant.get("name") or "",
                        "civilization": participant.get("god") or "",
                        "faction": "",
                        "result": result,
                        "won": won,
                        "rating": participant.get("elo"),
                        "rating_change": participant.get("rating_change"),
                        "raw_payload": participant,
                    },
                )
                imported_participants += 1
        else:
            current_profile_id = detail_match.get("current_player", {}).get("profile_id")
            player = _upsert_player_from_identity(
                profile_id=current_profile_id,
                alias=detail_match.get("current_player", {}).get("name") or "",
                display_name=detail_match.get("current_player", {}).get("name") or "",
                raw_identity=detail_match.get("current_player") or {},
                dry_run=dry_run,
            )
            MatchParticipant.objects.update_or_create(
                match=match,
                team=1,
                slot=1,
                defaults={
                    "player": player,
                    "profile_id": current_profile_id,
                    "alias": detail_match.get("current_player", {}).get("name") or "",
                    "civilization": detail_match.get("civilization") or "",
                    "faction": "",
                    "result": MatchParticipant.RESULT_UNKNOWN,
                    "won": None,
                    "rating": detail_match.get("rating"),
                    "rating_change": detail_match.get("rating_change"),
                    "raw_payload": detail_match.get("current_player") or {},
                },
            )
            imported_participants = 1

        _seed_replay_parse(match)

    return match, imported_participants


def import_recent_matches(
    *,
    match_type: int = 1,
    leaderboard_pages: int = 1,
    leaderboard_count: int = 25,
    player_limit: int | None = None,
    recent_count: int = 10,
    seed_profile_id: int | None = None,
    seed_player: str = "",
    dry_run: bool = False,
    refresh: bool = False,
    transport: str = "curl",
) -> dict[str, Any]:
    leaderboard_players: list[dict[str, Any]] = []
    seen_profile_ids: set[int] = set()
    leaderboard_failures = 0

    if seed_profile_id:
        leaderboard_players.append(
            {
                "profile_id": int(seed_profile_id),
                "name": seed_player or "",
                "avatar_url": "",
                "country": "",
            }
        )

    if not seed_profile_id:
        for page in range(1, max(1, leaderboard_pages) + 1):
            leaderboard_meta = get_match_type_meta(match_type) or {}
            leaderboard_id = leaderboard_meta.get("leaderboard_id")
            if leaderboard_id is None:
                leaderboard_failures += 1
                break

            leaderboard_response = async_to_sync(fetch_community_leaderboard2)(
                leaderboard_id=int(leaderboard_id),
                page=page,
                count=leaderboard_count,
                refresh=refresh,
            )

            if not leaderboard_response.get("ok"):
                leaderboard_failures += 1

            for row in leaderboard_response.get("matches", []):
                profile_id = row.get("profile_id")
                if not profile_id or int(profile_id) in seen_profile_ids:
                    continue

                seen_profile_ids.add(int(profile_id))
                leaderboard_players.append(row)

                if player_limit and len(leaderboard_players) >= player_limit:
                    break

            if player_limit and len(leaderboard_players) >= player_limit:
                break

    imported_matches: set[str] = set()
    persisted_match_ids: set[int] = set()
    totals = {
        "players_seen": 0,
        "players_persisted": 0,
        "matches_seen": 0,
        "matches_persisted": 0,
        "participants_persisted": 0,
        "match_list_failures": 0,
        "detail_failures": 0,
    }
    events: list[dict[str, Any]] = []

    for leaderboard_row in leaderboard_players:
        profile_id = int(leaderboard_row["profile_id"])
        player_name = leaderboard_row.get("name") or ""
        totals["players_seen"] += 1

        player = _upsert_player_from_identity(
            profile_id=profile_id,
            alias=leaderboard_row.get("name") or "",
            display_name=leaderboard_row.get("name") or "",
            avatar_url=leaderboard_row.get("avatar_url") or "",
            country_code=leaderboard_row.get("country") or "",
            raw_identity=leaderboard_row,
            dry_run=dry_run,
        )
        if player is not None or dry_run:
            totals["players_persisted"] += 1
        events.append(
            {
                "stage": "player_seeded",
                "profile_id": profile_id,
                "player": player_name,
                "dry_run": dry_run,
            }
        )

        profile_names = []
        raw_name = leaderboard_row.get("raw_name") or leaderboard_row.get("platform_name")
        if raw_name:
            profile_names.append(str(raw_name))

        match_list_response = async_to_sync(fetch_recent_match_history)(
            profile_ids=[profile_id],
            profile_names=profile_names,
            requested_profile_id=profile_id,
            match_type=match_type,
            start=1,
            count=recent_count,
            refresh=refresh,
        )

        if not match_list_response.get("ok"):
            totals["match_list_failures"] += 1
            events.append(
                {
                    "stage": "match_list_failed",
                    "profile_id": profile_id,
                    "player": player_name,
                    "status_code": match_list_response.get("status_code"),
                    "shape": match_list_response.get("shape"),
                }
            )

        match_rows = match_list_response.get("matches", [])
        if not match_rows:
            match_list_response = async_to_sync(fetch_player_match_list)(
                profile_id=profile_id,
                player=player_name or "unknown user",
                match_type=match_type,
                page=1,
                record_count=recent_count,
                refresh=refresh,
                force_transport=transport,
            )
            match_rows = match_list_response.get("matches", [])

        for match_row in match_rows:
            external_match_id = str(match_row.get("match_id") or "").strip()
            if not external_match_id:
                continue

            totals["matches_seen"] += 1

            if external_match_id in imported_matches:
                continue

            detail_response = async_to_sync(fetch_match_detail_raw)(
                profile_id=profile_id,
                match_id=external_match_id,
                refresh=refresh,
                force_transport=transport,
            )

            if not detail_response.get("ok"):
                totals["detail_failures"] += 1
                events.append(
                    {
                        "stage": "match_detail_failed",
                        "profile_id": profile_id,
                        "player": player_name,
                        "match_id": external_match_id,
                        "status_code": detail_response.get("status_code"),
                        "shape": detail_response.get("shape"),
                    }
                )
                continue

            detail_match = normalize_match_detail_for_player(
                raw_detail=detail_response.get("raw"),
                profile_id=profile_id,
                match_id=external_match_id,
                requested_match_type=match_type,
            )

            match, imported_participants = _upsert_match_with_participants(
                external_match_id=external_match_id,
                requested_match_type=match_type,
                match_row=match_row,
                detail_match=detail_match,
                detail_raw=detail_response.get("raw"),
                dry_run=dry_run,
            )
            imported_matches.add(external_match_id)
            totals["participants_persisted"] += imported_participants

            if dry_run:
                totals["matches_persisted"] += 1
            elif match is not None and match.id not in persisted_match_ids:
                persisted_match_ids.add(match.id)
                totals["matches_persisted"] += 1

            events.append(
                {
                    "stage": "match_imported",
                    "profile_id": profile_id,
                    "player": player_name,
                    "match_id": external_match_id,
                    "participant_count": imported_participants,
                    "dry_run": dry_run,
                }
            )

    return {
        "ok": True,
        "match_type": match_type,
        "match_type_label": get_match_type_label(match_type),
        "leaderboard_pages": leaderboard_pages,
        "leaderboard_count": leaderboard_count,
        "recent_count": recent_count,
        "player_limit": player_limit,
        "seed_profile_id": seed_profile_id,
        "seed_player": seed_player,
        "seed_mode": "direct_player" if seed_profile_id else "leaderboard",
        "dry_run": dry_run,
        "leaderboard_failures": leaderboard_failures,
        "refresh": refresh,
        "transport": transport,
        "events": events,
        **totals,
    }
