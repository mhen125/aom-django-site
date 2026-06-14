from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import Count, Q, QuerySet
from django.utils import timezone


@dataclass
class ReplayPipelineFilters:
    match_ids: list[str] = field(default_factory=list)
    ranked_only: bool = False
    replay_available_only: bool = True
    match_type_ids: list[int] = field(default_factory=list)
    one_v_one_only: bool = False
    started_after: datetime | None = None
    missing_replay_url_only: bool = False


def build_started_after(*, started_after: datetime | None = None, since_days: int | None = None) -> datetime | None:
    if started_after is not None:
        return started_after
    if since_days is None:
        return None
    return timezone.now() - timedelta(days=max(0, int(since_days)))


def apply_match_filters(queryset: QuerySet, filters: ReplayPipelineFilters) -> QuerySet:
    if filters.match_ids:
        queryset = queryset.filter(
            external_match_id__in=[str(match_id) for match_id in filters.match_ids if str(match_id).strip()]
        )
    if filters.ranked_only:
        queryset = queryset.filter(is_ranked=True)
    if filters.replay_available_only:
        queryset = queryset.filter(replay_available=True)
    if filters.match_type_ids:
        queryset = queryset.filter(match_type_id__in=filters.match_type_ids)
    if filters.started_after is not None:
        queryset = queryset.filter(started_at__gte=filters.started_after)
    if filters.one_v_one_only:
        queryset = queryset.annotate(participant_total=Count("participants")).filter(
            is_team_game=False,
            participant_total=2,
        )
    if filters.missing_replay_url_only:
        queryset = queryset.filter(Q(replay_url="") | Q(replay_url__isnull=True))
    return queryset


def apply_replay_parse_filters(queryset: QuerySet, filters: ReplayPipelineFilters) -> QuerySet:
    if filters.match_ids:
        queryset = queryset.filter(
            match__external_match_id__in=[str(match_id) for match_id in filters.match_ids if str(match_id).strip()]
        )
    if filters.ranked_only:
        queryset = queryset.filter(match__is_ranked=True)
    if filters.replay_available_only:
        queryset = queryset.filter(Q(extracted_facts__replay_available=True) | Q(match__replay_available=True))
    if filters.match_type_ids:
        queryset = queryset.filter(match__match_type_id__in=filters.match_type_ids)
    if filters.started_after is not None:
        queryset = queryset.filter(match__started_at__gte=filters.started_after)
    if filters.one_v_one_only:
        queryset = queryset.annotate(participant_total=Count("match__participants")).filter(
            match__is_team_game=False,
            participant_total=2,
        )
    return queryset
