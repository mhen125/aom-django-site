from __future__ import annotations

import json
import os
from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings

from .models import Match, ReplayParse
from .replay_filters import ReplayPipelineFilters, apply_match_filters
from lobbies.leaderboard import fetch_recent_match_history_raw


def get_replay_download_url_template() -> str:
    return (
        getattr(settings, "REPLAY_DOWNLOAD_URL_TEMPLATE", "")
        or os.getenv("REPLAY_DOWNLOAD_URL_TEMPLATE", "")
        or ""
    ).strip()


def get_api_match_replay_url_template() -> str:
    return (
        getattr(settings, "API_MATCH_REPLAY_URL_TEMPLATE", "")
        or os.getenv("API_MATCH_REPLAY_URL_TEMPLATE", "")
        or "https://api.ageofempires.com/api/GameStats/AgeMyth/GetMatchReplay/?matchId={match_id}&profileId={profile_id}"
    ).strip()


def get_replay_download_headers() -> dict[str, str]:
    raw_value = (
        getattr(settings, "REPLAY_DOWNLOAD_HEADERS_JSON", "")
        or os.getenv("REPLAY_DOWNLOAD_HEADERS_JSON", "")
        or ""
    ).strip()
    if not raw_value:
        return {}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}

    if not isinstance(parsed, dict):
        return {}

    headers: dict[str, str] = {}
    for key, value in parsed.items():
        if not key or value in (None, ""):
            continue
        headers[str(key)] = str(value)
    return headers


def get_replay_download_timeout() -> int:
    configured = getattr(settings, "REPLAY_DOWNLOAD_TIMEOUT", 30)
    try:
        return max(5, int(configured))
    except (TypeError, ValueError):
        return 30


def get_recent_history_lookup_count() -> int:
    configured = getattr(settings, "REPLAY_RECENT_HISTORY_LOOKUP_COUNT", 25)
    try:
        return max(1, int(configured))
    except (TypeError, ValueError):
        return 25


def _participant_profile_ids(match: Match) -> list[int]:
    return [
        int(profile_id)
        for profile_id in match.participants.exclude(profile_id__isnull=True)
        .order_by("team", "slot", "id")
        .values_list("profile_id", flat=True)
        if profile_id is not None
    ]


def _preferred_profile_id(match: Match) -> int | None:
    profile_ids = _participant_profile_ids(match)
    return profile_ids[0] if profile_ids else None


def _normalize_match_id(value: Any) -> str:
    return str(value or "").strip()


def _extract_replay_url_candidates(matchurls: Any) -> list[dict[str, Any]]:
    if not isinstance(matchurls, list):
        return []

    candidates: list[dict[str, Any]] = []
    for item in matchurls:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        candidates.append(
            {
                "profile_id": int(item["profile_id"]) if item.get("profile_id") not in (None, "") else None,
                "url": url,
                "size": int(item["size"]) if item.get("size") not in (None, "") and str(item.get("size")).lstrip("-").isdigit() else None,
                "datatype": item.get("datatype"),
            }
        )
    return candidates


def _choose_best_replay_url(candidates: list[dict[str, Any]], preferred_profile_id: int | None) -> dict[str, Any] | None:
    if not candidates:
        return None

    if preferred_profile_id is not None:
        exact = [candidate for candidate in candidates if candidate.get("profile_id") == preferred_profile_id]
        if exact:
            exact.sort(key=lambda item: (-(item.get("size") or -1), str(item.get("url") or "")))
            return exact[0]

    sized = [candidate for candidate in candidates if (candidate.get("size") or -1) >= 0]
    if sized:
        sized.sort(key=lambda item: (-(item.get("size") or -1), str(item.get("url") or "")))
        return sized[0]

    return candidates[0]


def extract_replay_url_from_match_payload(match: Match) -> dict[str, Any] | None:
    raw_payload = match.raw_payload if isinstance(match.raw_payload, dict) else {}
    candidates = _extract_replay_url_candidates(raw_payload.get("matchurls"))
    best = _choose_best_replay_url(candidates, _preferred_profile_id(match))
    if best is None:
        return None
    return {
        **best,
        "source": "stored_matchurls",
    }


def _find_recent_history_record(raw_payload: Any, match: Match) -> dict[str, Any] | None:
    if not isinstance(raw_payload, dict):
        return None

    for item in raw_payload.get("matchHistoryStats", []) if isinstance(raw_payload.get("matchHistoryStats"), list) else []:
        if not isinstance(item, dict):
            continue
        if _normalize_match_id(item.get("id")) == _normalize_match_id(match.external_match_id):
            return item
    return None


def fetch_recent_history_replay_url(match: Match, *, refresh: bool = False) -> dict[str, Any] | None:
    profile_ids = _participant_profile_ids(match)
    if not profile_ids:
        return None

    raw_response = async_to_sync(fetch_recent_match_history_raw)(
        profile_ids=profile_ids,
        count=get_recent_history_lookup_count(),
        start=1,
        refresh=refresh,
    )
    if not raw_response.get("ok"):
        return None

    record = _find_recent_history_record(raw_response.get("raw"), match)
    if not isinstance(record, dict):
        return None

    best = _choose_best_replay_url(
        _extract_replay_url_candidates(record.get("matchurls")),
        _preferred_profile_id(match),
    )
    if best is None:
        return None

    return {
        **best,
        "source": "recent_match_history",
    }


def resolve_replay_download_url(match: Match) -> str:
    if match.replay_url:
        return str(match.replay_url).strip()

    payload_candidate = extract_replay_url_from_match_payload(match)
    if payload_candidate and payload_candidate.get("url"):
        return str(payload_candidate["url"]).strip()

    template = get_replay_download_url_template()
    profile_id = _preferred_profile_id(match)
    return template.format(
        match_id=str(match.external_match_id),
        external_match_id=str(match.external_match_id),
        profile_id=str(profile_id or ""),
        source=str(match.source or ""),
    ).strip()


def resolve_api_match_replay_url(match: Match) -> str:
    template = get_api_match_replay_url_template()
    profile_id = _preferred_profile_id(match)
    if not template or profile_id is None:
        return ""
    return template.format(
        match_id=str(match.external_match_id),
        external_match_id=str(match.external_match_id),
        profile_id=str(profile_id),
        source=str(match.source or ""),
    ).strip()


def attach_replay_url(
    *,
    match: Match,
    replay_parse: ReplayParse | None = None,
    replay_url: str,
    source_label: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    replay_url = str(replay_url or "").strip()
    if not replay_url:
        return {
            "ok": False,
            "changed": False,
            "reason": "missing_replay_url",
        }

    row = replay_parse or ReplayParse.objects.filter(match=match).first()
    extracted_facts = row.extracted_facts if row and isinstance(row.extracted_facts, dict) else {}
    changed = False

    if dry_run:
        return {
            "ok": True,
            "changed": replay_url != (row.replay_url if row else match.replay_url),
            "reason": "dry_run",
        }

    if match.replay_url != replay_url:
        match.replay_url = replay_url
        match.save(update_fields=["replay_url", "updated_at"])
        changed = True

    if row is not None:
        changed_fields: list[str] = []
        if row.replay_url != replay_url:
            row.replay_url = replay_url
            changed_fields.append("replay_url")

        updated_facts = {
            **extracted_facts,
            "replay_url_ready": True,
            "replay_acquisition_source": source_label,
        }
        if updated_facts != extracted_facts:
            row.extracted_facts = updated_facts
            changed_fields.append("extracted_facts")

        if changed_fields:
            changed_fields.append("updated_at")
            row.save(update_fields=changed_fields)
            changed = True

    return {
        "ok": True,
        "changed": changed,
        "reason": "attached",
    }


def backfill_replay_sources(
    *,
    match_ids: list[str] | None = None,
    limit: int | None = None,
    ranked_only: bool = False,
    replay_available_only: bool = True,
    match_type_ids: list[int] | None = None,
    one_v_one_only: bool = False,
    started_after=None,
    missing_replay_url_only: bool = False,
    live_recent_history: bool = False,
    refresh_live_history: bool = False,
    allow_api_fallback: bool = True,
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
    template = get_replay_download_url_template()
    results = {
        "ok": True,
        "dry_run": dry_run,
        "template_configured": bool(template),
        "match_type_ids": filters.match_type_ids,
        "one_v_one_only": one_v_one_only,
        "started_after": started_after.isoformat() if started_after else None,
        "missing_replay_url_only": missing_replay_url_only,
        "live_recent_history": live_recent_history,
        "allow_api_fallback": allow_api_fallback,
        "matches_scanned": len(matches),
        "rows_url_attached": 0,
        "rows_url_unchanged": 0,
        "rows_missing_template": 0,
        "events": [],
    }

    for match in matches:
        replay_parse = ReplayParse.objects.filter(match=match).first()
        existing_url = (replay_parse.replay_url if replay_parse else "") or match.replay_url or ""
        resolved_url = ""
        source_label = ""

        payload_candidate = extract_replay_url_from_match_payload(match)
        if payload_candidate and payload_candidate.get("url"):
            resolved_url = str(payload_candidate["url"]).strip()
            source_label = str(payload_candidate.get("source") or "stored_matchurls")

        if not resolved_url and live_recent_history:
            history_candidate = fetch_recent_history_replay_url(match, refresh=refresh_live_history)
            if history_candidate and history_candidate.get("url"):
                resolved_url = str(history_candidate["url"]).strip()
                source_label = str(history_candidate.get("source") or "recent_match_history")

        if not resolved_url:
            resolved_url = resolve_replay_download_url(match)
            if resolved_url:
                source_label = "url_template"

        if not resolved_url and allow_api_fallback:
            resolved_url = resolve_api_match_replay_url(match)
            if resolved_url:
                source_label = "api_match_replay"

        if not resolved_url:
            results["rows_missing_template"] += 1
            results["events"].append(
                {
                    "match_id": match.external_match_id,
                    "changed": False,
                    "reason": "missing_template_or_url",
                    "replay_available": bool(match.replay_available),
                    "existing_url": bool(existing_url),
                }
            )
            continue

        attach_result = attach_replay_url(
            match=match,
            replay_parse=replay_parse,
            replay_url=resolved_url,
            source_label=source_label or ("existing_url" if existing_url else "resolved"),
            dry_run=dry_run,
        )

        if attach_result["changed"]:
            results["rows_url_attached"] += 1
        else:
            results["rows_url_unchanged"] += 1

        results["events"].append(
            {
                "match_id": match.external_match_id,
                "changed": bool(attach_result["changed"]),
                "reason": attach_result["reason"],
                "replay_available": bool(match.replay_available),
                "resolved_url": bool(resolved_url),
                "source": source_label,
            }
        )

    return results
