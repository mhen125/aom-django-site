from __future__ import annotations

import os
from typing import Any

from django.conf import settings

from .models import Match, ReplayParse


def get_supported_replay_builds() -> list[str]:
    raw_value = getattr(settings, "REPLAY_SUPPORTED_BUILDS", None)
    if raw_value is None:
        raw_value = os.getenv("REPLAY_SUPPORTED_BUILDS", "")

    if isinstance(raw_value, (list, tuple)):
        values = raw_value
    else:
        values = str(raw_value or "").split(",")

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def allow_unknown_replay_builds() -> bool:
    configured = getattr(settings, "REPLAY_ALLOW_UNKNOWN_BUILDS", None)
    if configured is None:
        configured = os.getenv("REPLAY_ALLOW_UNKNOWN_BUILDS", "true")
    return str(configured).strip().lower() in {"1", "true", "yes", "on"}


def get_known_replay_build(match: Match, replay_parse: ReplayParse | None = None) -> str:
    facts = {}
    if replay_parse and isinstance(replay_parse.extracted_facts, dict):
        facts = replay_parse.extracted_facts

    for value in [facts.get("build_number"), match.patch_label]:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def evaluate_replay_build(
    match: Match,
    replay_parse: ReplayParse | None = None,
    *,
    supported_builds: list[str] | None = None,
    allow_unknown: bool | None = None,
) -> dict[str, Any]:
    configured_builds = supported_builds if supported_builds is not None else get_supported_replay_builds()
    normalized_builds = [str(value).strip() for value in configured_builds if str(value).strip()]
    known_build = get_known_replay_build(match, replay_parse)

    if allow_unknown is None:
        allow_unknown = allow_unknown_replay_builds()

    if not normalized_builds:
        return {
            "eligible": True,
            "build": known_build,
            "reason": "no_supported_builds_configured",
            "known": bool(known_build),
        }

    if known_build:
        if known_build in normalized_builds:
            return {
                "eligible": True,
                "build": known_build,
                "reason": "supported_build",
                "known": True,
            }
        return {
            "eligible": False,
            "build": known_build,
            "reason": "unsupported_build",
            "known": True,
        }

    return {
        "eligible": bool(allow_unknown),
        "build": "",
        "reason": "unknown_build_allowed" if allow_unknown else "unknown_build_blocked",
        "known": False,
    }
