from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import zipfile

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Match, MatchParticipant, ReplayParse, ReplayPlayerSummary, UnitProductionSummary
from .replay_builds import evaluate_replay_build
from .replay_acquisition import (
    attach_replay_url,
    fetch_recent_history_replay_url,
    get_replay_download_headers,
    get_replay_download_timeout,
    resolve_api_match_replay_url,
    resolve_replay_download_url,
)
from .replay_filters import ReplayPipelineFilters, apply_replay_parse_filters


DEFAULT_RESTORATION_TIMEOUT = 120

AGE_TECH_LABELS = {
    "classical": "ClassicalAge",
    "heroic": "HeroicAge",
    "mythic": "MythicAge",
}

NON_MILITARY_UNIT_KEYWORDS = (
    "villager",
    "villageratlantean",
    "oxcart",
    "oracle",
    "pharaoh",
    "priest",
    "warriorpriest",
    "miko",
    "kuafu",
    "spy",
    "servant",
    "scout",
    "caravan",
    "fishing",
    "fishingship",
    "transport",
)


class ReplayParserError(Exception):
    pass


@dataclass
class ReplayArtifact:
    local_path: Path
    cleanup_path: Path | None = None

    def cleanup(self):
        if self.cleanup_path and self.cleanup_path.exists():
            self.cleanup_path.unlink()


@dataclass
class ReplayUrlCandidate:
    url: str
    source_label: str


def get_restoration_binary_path() -> str:
    configured = getattr(settings, "RESTORATION_BINARY_PATH", "") or os.getenv("RESTORATION_BINARY_PATH", "")
    if configured:
        return configured
    return "restoration"


def get_restoration_timeout() -> int:
    configured = getattr(settings, "RESTORATION_COMMAND_TIMEOUT", DEFAULT_RESTORATION_TIMEOUT)
    try:
        return max(10, int(configured))
    except (TypeError, ValueError):
        return DEFAULT_RESTORATION_TIMEOUT


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_name(value: Any) -> str:
    return str(value or "").strip()


def _is_probably_gzip(path: Path) -> bool:
    return path.suffix.lower() == ".gz"


def _write_temp_replay_bytes(content: bytes, *, suffix: str) -> ReplayArtifact:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    return ReplayArtifact(local_path=temp_path, cleanup_path=temp_path)


def _extract_replay_from_zip_bytes(content: bytes) -> ReplayArtifact:
    archive = zipfile.ZipFile(io.BytesIO(content))
    candidates = [
        name for name in archive.namelist()
        if name.lower().endswith(".mythrec") or name.lower().endswith(".mythrec.gz")
    ]
    if not candidates:
        raise ReplayParserError("Replay zip did not contain a .mythrec or .mythrec.gz file.")

    preferred_name = candidates[0]
    replay_bytes = archive.read(preferred_name)
    suffix = ".mythrec.gz" if preferred_name.lower().endswith(".mythrec.gz") else ".mythrec"
    return _write_temp_replay_bytes(replay_bytes, suffix=suffix)


def _download_replay_to_temp(replay_url: str) -> ReplayArtifact:
    parsed = urlparse(replay_url)
    if parsed.scheme in {"", "file"}:
        local_path = Path(parsed.path if parsed.scheme == "file" else replay_url).expanduser()
        if not local_path.exists():
            raise ReplayParserError(f"Replay file does not exist: {local_path}")
        return ReplayArtifact(local_path=local_path)

    response = requests.get(
        replay_url,
        timeout=get_replay_download_timeout(),
        headers=get_replay_download_headers(),
    )
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    content_disposition = (response.headers.get("content-disposition") or "").lower()
    content = response.content

    if (
        "application/zip" in content_type
        or ".zip" in content_disposition
        or content[:4] == b"PK\x03\x04"
    ):
        return _extract_replay_from_zip_bytes(content)

    suffix = Path(parsed.path).suffix or ".mythrec"
    if parsed.path.endswith(".mythrec.gz") and not suffix.endswith(".gz"):
        suffix = ".mythrec.gz"
    return _write_temp_replay_bytes(content, suffix=suffix)


def _build_replay_url_candidates(
    replay_parse: ReplayParse,
    *,
    resolve_live_history: bool = False,
    refresh_live_history: bool = False,
) -> list[ReplayUrlCandidate]:
    candidates: list[ReplayUrlCandidate] = []
    seen: set[str] = set()

    def add_candidate(url: str, source_label: str):
        normalized = _safe_name(url)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(ReplayUrlCandidate(url=normalized, source_label=source_label))

    add_candidate(replay_parse.replay_url or "", "replay_parse")
    add_candidate(replay_parse.match.replay_url or "", "match")
    add_candidate(resolve_replay_download_url(replay_parse.match), "resolved_match")

    if resolve_live_history:
        recent_history_candidate = fetch_recent_history_replay_url(
            replay_parse.match,
            refresh=refresh_live_history,
        )
        if recent_history_candidate and recent_history_candidate.get("url"):
            add_candidate(
                str(recent_history_candidate["url"]).strip(),
                str(recent_history_candidate.get("source") or "recent_match_history"),
            )

    add_candidate(resolve_api_match_replay_url(replay_parse.match), "api_match_replay")
    return candidates


def _run_restoration_parse(local_path: Path) -> tuple[dict[str, Any], str]:
    binary_path = get_restoration_binary_path()
    if not shutil.which(binary_path) and not Path(binary_path).exists():
        raise ReplayParserError(
            "Restoration parser binary was not found. Set RESTORATION_BINARY_PATH to the downloaded binary."
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as handle:
        output_path = Path(handle.name)

    command = [binary_path]
    if _is_probably_gzip(local_path):
        command.append("--is-gzip")
    command.extend(
        [
            "parse",
            str(local_path),
            "--stats",
            "--quiet",
            "--output",
            str(output_path),
        ]
    )

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=get_restoration_timeout(),
            check=False,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise ReplayParserError(stderr or f"restoration parse exited with code {completed.returncode}")

        with output_path.open("r", encoding="utf-8") as handle:
            parsed_json = json.load(handle)
        return parsed_json, binary_path
    finally:
        if output_path.exists():
            output_path.unlink()


def _find_age_time(player_stats: dict[str, Any], age_key: str) -> int | None:
    techs = (((player_stats or {}).get("Timelines") or {}).get("TechsPrequeued")) or []
    expected_prefix = AGE_TECH_LABELS.get(age_key, "")
    for item in techs:
        name = _safe_name(item.get("Name"))
        if name.startswith(expected_prefix):
            return _coerce_int(item.get("GameTimeSecs"))
    return None


def _extract_first_timing_from_counts(timeline_counts: list[dict[str, Any]] | None, keywords: tuple[str, ...]) -> int | None:
    if not isinstance(timeline_counts, list):
        return None

    for minute_index, bucket in enumerate(timeline_counts):
        if not isinstance(bucket, dict):
            continue
        for unit_name, count in bucket.items():
            normalized_name = _safe_name(unit_name).casefold()
            matches = any(keyword in normalized_name for keyword in keywords) if keywords else _is_military_unit(unit_name)
            if count and matches:
                return minute_index * 60
    return None


def _is_military_unit(unit_name: str) -> bool:
    normalized = _safe_name(unit_name).replace("_", "").replace(" ", "").casefold()
    if not normalized:
        return False
    return not any(keyword in normalized for keyword in NON_MILITARY_UNIT_KEYWORDS)


def _primary_unit_from_counts(unit_counts: dict[str, Any]) -> str:
    candidates = [
        (name, _coerce_int(count) or 0)
        for name, count in (unit_counts or {}).items()
        if _is_military_unit(name)
    ]
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[1], item[0].casefold()))
    return candidates[0][0]


def _infer_strategy(player_summary: dict[str, Any], unit_counts: dict[str, Any]) -> str:
    classical = player_summary.get("age_up_classical_seconds")
    heroic = player_summary.get("age_up_heroic_seconds")
    mythic = player_summary.get("age_up_mythic_seconds")
    primary_unit = _safe_name(player_summary.get("primary_unit")).casefold()
    total_military = sum((_coerce_int(count) or 0) for name, count in (unit_counts or {}).items() if _is_military_unit(name))

    if heroic is not None and heroic <= 600:
        return "Fast Heroic"
    if mythic is not None and mythic <= 900:
        return "Fast Mythic"
    if heroic is not None and heroic >= 840 and total_military >= 20:
        return "Long Classical"
    if "eagle" in primary_unit:
        return "Eagle Warrior Core"
    if any(keyword in primary_unit for keyword in ("toxotes", "arcus", "archer", "slinger")) and total_military >= 25:
        return "Archer Deathball"
    if total_military >= 35:
        return "Early Pressure"
    if classical is not None and classical >= 300:
        return "Boom"
    return ""


def _build_player_summary_payload(player_entry: dict[str, Any], player_stats: dict[str, Any]) -> dict[str, Any]:
    timelines = (player_stats or {}).get("Timelines") or {}
    unit_counts = (player_stats or {}).get("UnitCounts") or {}
    building_counts_timeline = timelines.get("BuildingCounts") or []

    summary = {
        "eapm": _coerce_float(player_entry.get("EAPM")),
        "age_up_classical_seconds": _find_age_time(player_stats, "classical"),
        "age_up_heroic_seconds": _find_age_time(player_stats, "heroic"),
        "age_up_mythic_seconds": _find_age_time(player_stats, "mythic"),
        "first_military_seconds": _extract_first_timing_from_counts(
            timelines.get("UnitCounts") or [],
            tuple(),
        ),
        "first_tc_seconds": _extract_first_timing_from_counts(building_counts_timeline, ("towncenter",)),
        "first_dock_seconds": _extract_first_timing_from_counts(building_counts_timeline, ("dock",)),
        "first_market_seconds": _extract_first_timing_from_counts(building_counts_timeline, ("market",)),
        "primary_unit": _primary_unit_from_counts(unit_counts),
        "primary_strategy": "",
        "raw_summary": {
            "player": player_entry,
            "stats": player_stats,
        },
    }
    summary["primary_strategy"] = _infer_strategy(summary, unit_counts)
    return summary


def _extract_unit_rows(player_stats: dict[str, Any]) -> list[dict[str, Any]]:
    timelines = (player_stats or {}).get("Timelines") or {}
    timeline_counts = timelines.get("UnitCounts") or []
    final_counts = (player_stats or {}).get("UnitCounts") or {}
    first_seen: dict[str, int] = {}
    last_seen: dict[str, int] = {}

    if isinstance(timeline_counts, list):
        for minute_index, bucket in enumerate(timeline_counts):
            if not isinstance(bucket, dict):
                continue
            for unit_name, count in bucket.items():
                produced = _coerce_int(count) or 0
                if produced <= 0:
                    continue
                first_seen.setdefault(unit_name, minute_index * 60)
                last_seen[unit_name] = minute_index * 60

    rows = []
    for unit_name, count in final_counts.items():
        produced_count = _coerce_int(count) or 0
        if produced_count <= 0 or not _is_military_unit(unit_name):
            continue
        rows.append(
            {
                "unit_name": unit_name,
                "produced_count": produced_count,
                "lost_count": 0,
                "killed_count": 0,
                "first_created_seconds": first_seen.get(unit_name),
                "last_created_seconds": last_seen.get(unit_name),
            }
        )

    rows.sort(key=lambda item: (-item["produced_count"], item["unit_name"].casefold()))
    return rows


def _extract_match_level_facts(parsed_json: dict[str, Any]) -> dict[str, Any]:
    players = parsed_json.get("Players") or []
    gods = Counter(_safe_name(player.get("God")) for player in players if _safe_name(player.get("God")))
    return {
        "map_name": _safe_name(parsed_json.get("MapName")),
        "build_number": _coerce_int(parsed_json.get("BuildNumber")),
        "build_string": _safe_name(parsed_json.get("BuildString")),
        "parser_version": _safe_name(parsed_json.get("ParserVersion")),
        "game_length_secs": _coerce_float(parsed_json.get("GameLengthSecs")),
        "winning_team": _coerce_int(parsed_json.get("WinningTeam")),
        "player_count": len(players),
        "gods": dict(gods),
    }


def _find_participant_for_player(replay_parse: ReplayParse, player_entry: dict[str, Any]) -> MatchParticipant | None:
    profile_id = _coerce_int(player_entry.get("ProfileId"))
    if profile_id is not None:
        participant = replay_parse.match.participants.filter(profile_id=profile_id).first()
        if participant is not None:
            return participant

    name = _safe_name(player_entry.get("Name"))
    if name:
        lowered = name.casefold()
        for participant in replay_parse.match.participants.all():
            if _safe_name(participant.alias).casefold() == lowered:
                return participant
    return None


def extract_replay_enrichment(parsed_json: dict[str, Any], replay_parse: ReplayParse) -> dict[str, Any]:
    players = parsed_json.get("Players") or []
    stats_map = parsed_json.get("Stats") or {}
    player_summaries: list[dict[str, Any]] = []

    for player_entry in players:
        participant = _find_participant_for_player(replay_parse, player_entry)
        if participant is None:
            continue

        player_num = str(player_entry.get("PlayerNum"))
        player_stats = stats_map.get(player_num) or {}
        summary = _build_player_summary_payload(player_entry, player_stats)
        unit_rows = _extract_unit_rows(player_stats)
        player_summaries.append(
            {
                "participant": participant,
                "summary": summary,
                "unit_rows": unit_rows,
                "player_entry": player_entry,
            }
        )

    return {
        "match_facts": _extract_match_level_facts(parsed_json),
        "player_summaries": player_summaries,
    }


def _sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_replay_file(local_path: str | Path) -> tuple[dict[str, Any], str, str]:
    replay_path = Path(local_path)
    parsed_json, binary_path = _run_restoration_parse(replay_path)
    return parsed_json, binary_path, _sha256_for_file(replay_path)


@transaction.atomic
def upsert_match_from_parsed_replay(
    *,
    parsed_json: dict[str, Any],
    replay_file_path: str | Path,
    external_match_id: str,
) -> ReplayParse:
    replay_path = Path(replay_file_path).expanduser().resolve()
    game_length_secs = _coerce_int(parsed_json.get("GameLengthSecs"))
    parser_timestamp = parsed_json.get("ParsedAt")
    started_at = timezone.now()
    if parser_timestamp:
        try:
            parsed_at = timezone.datetime.fromisoformat(str(parser_timestamp))
            if parsed_at.tzinfo is None:
                parsed_at = parsed_at.replace(tzinfo=timezone.utc)
            started_at = parsed_at - timedelta(seconds=game_length_secs or 0)
        except Exception:
            started_at = timezone.now()

    match, _created = Match.objects.update_or_create(
        external_match_id=str(external_match_id),
        defaults={
            "source": Match.SOURCE_WORLDSEDGE,
            "match_type_id": 1,
            "match_type_label": "Local Replay Import",
            "leaderboard_id": None,
            "is_ranked": False,
            "is_team_game": len({player.get("TeamId") for player in (parsed_json.get("Players") or [])}) > 1,
            "team_size": None,
            "map_name": _safe_name(parsed_json.get("MapName")),
            "started_at": started_at,
            "completed_at": started_at + timedelta(seconds=game_length_secs or 0),
            "duration_seconds": game_length_secs,
            "winning_team": _coerce_int(parsed_json.get("WinningTeam")),
            "patch_label": str(parsed_json.get("BuildNumber") or ""),
            "replay_url": replay_path.as_uri(),
            "replay_available": True,
            "raw_payload": {
                "source": "local_replay_import",
                "replay_file_path": str(replay_path),
                "parsed_preview": {
                    "MapName": parsed_json.get("MapName"),
                    "BuildNumber": parsed_json.get("BuildNumber"),
                    "PlayerCount": len(parsed_json.get("Players") or []),
                },
            },
        },
    )

    for index, player_entry in enumerate(parsed_json.get("Players") or []):
        team_id = _coerce_int(player_entry.get("TeamId"))
        slot = index + 1
        winner = bool(player_entry.get("Winner"))
        MatchParticipant.objects.update_or_create(
            match=match,
            team=team_id,
            slot=slot,
            defaults={
                "player": None,
                "profile_id": _coerce_int(player_entry.get("ProfileId")),
                "alias": _safe_name(player_entry.get("Name")),
                "civilization": _safe_name(player_entry.get("God")),
                "faction": "",
                "result": MatchParticipant.RESULT_WIN if winner else MatchParticipant.RESULT_LOSS,
                "won": winner,
                "rating": None,
                "rating_change": None,
                "raw_payload": player_entry,
            },
        )

    replay_parse, _created = ReplayParse.objects.update_or_create(
        match=match,
        defaults={
            "status": ReplayParse.STATUS_PENDING,
            "replay_url": replay_path.as_uri(),
            "error_text": "",
        },
    )
    return replay_parse


@transaction.atomic
def enrich_replay_parse_from_json(
    replay_parse: ReplayParse,
    *,
    parsed_json: dict[str, Any],
    parser_binary: str = "",
    replay_sha256: str = "",
):
    enrichment = extract_replay_enrichment(parsed_json, replay_parse)

    replay_parse.parsed_json = parsed_json
    replay_parse.extracted_facts = enrichment["match_facts"]
    replay_parse.parser_version = _safe_name(parsed_json.get("ParserVersion"))
    replay_parse.parser_binary = parser_binary or replay_parse.parser_binary
    replay_parse.replay_sha256 = replay_sha256 or replay_parse.replay_sha256
    replay_parse.status = ReplayParse.STATUS_PARSED
    replay_parse.finished_at = timezone.now()
    replay_parse.enriched_at = timezone.now()
    replay_parse.error_text = ""
    replay_parse.save(
        update_fields=[
            "parsed_json",
            "extracted_facts",
            "parser_version",
            "parser_binary",
            "replay_sha256",
            "status",
            "finished_at",
            "enriched_at",
            "error_text",
            "updated_at",
        ]
    )

    ReplayPlayerSummary.objects.filter(replay_parse=replay_parse).delete()

    for item in enrichment["player_summaries"]:
        replay_summary = ReplayPlayerSummary.objects.create(
            replay_parse=replay_parse,
            participant=item["participant"],
            **item["summary"],
        )
        UnitProductionSummary.objects.bulk_create(
            [
                UnitProductionSummary(
                    replay_player_summary=replay_summary,
                    **unit_row,
                )
                for unit_row in item["unit_rows"]
            ]
        )


def process_replay_parse(
    replay_parse: ReplayParse,
    *,
    replay_file_path: str | Path | None = None,
    resolve_live_history: bool = False,
    refresh_live_history: bool = False,
) -> ReplayParse:
    replay_parse.status = ReplayParse.STATUS_PROCESSING
    replay_parse.started_at = timezone.now()
    replay_parse.error_text = ""
    replay_parse.save(update_fields=["status", "started_at", "error_text", "updated_at"])

    artifact: ReplayArtifact | None = None
    attempted_sources: list[str] = []

    try:
        if replay_file_path is not None:
            artifact = ReplayArtifact(local_path=Path(replay_file_path))
        else:
            candidates = _build_replay_url_candidates(
                replay_parse,
                resolve_live_history=resolve_live_history,
                refresh_live_history=refresh_live_history,
            )
            last_error: Exception | None = None
            for candidate in candidates:
                attempted_sources.append(candidate.source_label)
                attach_replay_url(
                    match=replay_parse.match,
                    replay_parse=replay_parse,
                    replay_url=candidate.url,
                    source_label=candidate.source_label,
                    dry_run=False,
                )
                try:
                    artifact = _download_replay_to_temp(candidate.url)
                    break
                except Exception as error:
                    last_error = error
                    continue

            if artifact is None:
                if last_error is not None:
                    raise ReplayParserError(
                        f"{last_error} | attempted sources: {', '.join(attempted_sources) or 'none'}"
                    )
                raise ReplayParserError("ReplayParse has no replay file path or replay_url to parse.")

        parsed_json, parser_binary, replay_sha256 = parse_replay_file(artifact.local_path)
        enrich_replay_parse_from_json(
            replay_parse,
            parsed_json=parsed_json,
            parser_binary=parser_binary,
            replay_sha256=replay_sha256,
        )
    except Exception as error:
        replay_parse.status = ReplayParse.STATUS_FAILED
        replay_parse.finished_at = timezone.now()
        replay_parse.error_text = str(error)
        replay_parse.save(update_fields=["status", "finished_at", "error_text", "updated_at"])
        raise
    finally:
        if artifact is not None:
            artifact.cleanup()

    replay_parse.refresh_from_db()
    return replay_parse


def parse_replay_queue_batch(
    *,
    limit: int = 25,
    match_id: str = "",
    replay_file_path: str | Path | None = None,
    ranked_only: bool = False,
    replay_available_only: bool = True,
    match_type_ids: list[int] | None = None,
    one_v_one_only: bool = False,
    started_after=None,
    supported_builds: list[str] | None = None,
    allow_unknown_builds: bool | None = None,
    resolve_live_history: bool = False,
    refresh_live_history: bool = False,
) -> dict[str, Any]:
    filters = ReplayPipelineFilters(
        match_ids=[str(match_id).strip()] if str(match_id).strip() else [],
        ranked_only=ranked_only,
        replay_available_only=replay_available_only,
        match_type_ids=[int(match_type_id) for match_type_id in (match_type_ids or [])],
        one_v_one_only=one_v_one_only,
        started_after=started_after,
    )
    queryset = ReplayParse.objects.select_related("match").order_by("created_at")
    queryset = apply_replay_parse_filters(queryset, filters)
    if match_id:
        queryset = queryset.filter(match__external_match_id=str(match_id).strip())
    else:
        queryset = queryset.filter(status__in=[ReplayParse.STATUS_PENDING, ReplayParse.STATUS_FAILED])

    rows: list[ReplayParse] = []
    skipped_count = 0
    for replay_parse in queryset.iterator(chunk_size=100):
        build_policy = evaluate_replay_build(
            replay_parse.match,
            replay_parse,
            supported_builds=supported_builds,
            allow_unknown=allow_unknown_builds,
        )
        if not build_policy["eligible"]:
            skipped_count += 1
            continue
        rows.append(replay_parse)
        if len(rows) >= max(1, int(limit)):
            break
    if replay_file_path and len(rows) != 1:
        raise ReplayParserError("--replay-file can only be used when exactly one replay row is targeted.")

    summary = {
        "ok": True,
        "limit": max(1, int(limit)),
        "match_id": str(match_id or "").strip(),
        "match_type_ids": filters.match_type_ids,
        "one_v_one_only": one_v_one_only,
        "started_after": started_after.isoformat() if started_after else None,
        "supported_builds": [str(value).strip() for value in (supported_builds or []) if str(value).strip()],
        "allow_unknown_builds": allow_unknown_builds,
        "requested_rows": len(rows),
        "parsed_count": 0,
        "failed_count": 0,
        "skipped_count": skipped_count,
        "events": [],
    }

    for replay_parse in rows:
        try:
            process_replay_parse(
                replay_parse,
                replay_file_path=replay_file_path,
                resolve_live_history=resolve_live_history,
                refresh_live_history=refresh_live_history,
            )
            summary["parsed_count"] += 1
            summary["events"].append(
                {
                    "match_id": replay_parse.match.external_match_id,
                    "ok": True,
                    "status": replay_parse.status,
                    "parser_version": replay_parse.parser_version,
                }
            )
        except Exception as error:
            summary["failed_count"] += 1
            summary["events"].append(
                {
                    "match_id": replay_parse.match.external_match_id,
                    "ok": False,
                    "error": str(error),
                }
            )

    return summary
