from django.db.models import Prefetch
from django.shortcuts import redirect, render
from django.urls import reverse

from lobbies.leaderboard_metadata import build_leaderboard_metadata_payload, get_ranked_queues

from .models import GodMetaSnapshot, Match, MetaClaim, ReplayParse, ReplayPlayerSummary, ReplayTag, StatWindow, UnitProductionSummary


def _player_stats_context(
    request,
    *,
    canonical_url: str,
    initial_player: str = "",
    initial_profile_id: str = "",
    initial_match_type: str = "1",
):
    return {
        "canonical_url": canonical_url,
        "meta_description": (
            "View Age of Mythology: Retold player ratings, recent matches, god usage, "
            "and queue-specific performance on Prostagma."
        ),
        "leaderboard_metadata": build_leaderboard_metadata_payload(),
        "default_ranked_match_types": get_ranked_queues(),
        "initial_player": initial_player,
        "initial_profile_id": initial_profile_id,
        "initial_match_type": initial_match_type or "1",
    }


def stats_home(request):
    return redirect("stats:meta_dashboard")


def player_stats_home(request):
    return render(
        request,
        "player_stats.html",
        _player_stats_context(
            request,
            canonical_url=request.build_absolute_uri(reverse("stats:player_stats_home")),
            initial_player=request.GET.get("player", "").strip(),
            initial_profile_id=request.GET.get("profile_id", "").strip(),
            initial_match_type=request.GET.get("match_type", "1").strip(),
        ),
    )


def player_profile(request, profile_id: int):
    return render(
        request,
        "player_stats.html",
        _player_stats_context(
            request,
            canonical_url=request.build_absolute_uri(reverse("stats:player_profile", args=[profile_id])),
            initial_player=request.GET.get("player", "").strip(),
            initial_profile_id=str(profile_id),
            initial_match_type=request.GET.get("match_type", "1").strip(),
        ),
    )


def meta_dashboard(request):
    active_window = StatWindow.objects.filter(scope=StatWindow.SCOPE_META, is_active=True).order_by("-started_at", "slug").first()
    featured_claims = list(
        MetaClaim.objects
        .filter(is_public=True)
        .select_related("stat_window")
        .order_by("-published_at", "claim_key")[:6]
    )
    recent_snapshots = list(
        GodMetaSnapshot.objects
        .select_related("stat_window")
        .order_by("-updated_at", "god_name")[:8]
    )

    context = {
        "canonical_url": request.build_absolute_uri(reverse("stats:meta_dashboard")),
        "meta_description": (
            "Read Prostagma's emerging Age of Mythology: Retold meta calls, "
            "god trends, and future ranked-stat verdicts."
        ),
        "active_window": active_window,
        "featured_claims": featured_claims,
        "recent_snapshots": recent_snapshots,
        "match_count": Match.objects.count(),
        "claim_count": MetaClaim.objects.filter(is_public=True).count(),
        "snapshot_count": GodMetaSnapshot.objects.count(),
        "badge_catalog": [
            "META DEFINING",
            "UNDERPERFORMING",
            "LOW-ELO STOMPER",
            "HIGH-ELO SPECIALIST",
            "MAP DEPENDENT",
            "VOLATILE",
            "RISING",
            "FALLING",
            "MATCHUP NIGHTMARE",
            "ARCHER DEATHBALL",
            "LONG CLASSICAL",
        ],
    }
    return render(request, "stats/meta_dashboard.html", context)


def replay_discovery(request):
    pending_parses = ReplayParse.objects.filter(status=ReplayParse.STATUS_PENDING).count()
    parsed_replays = ReplayParse.objects.filter(status=ReplayParse.STATUS_PARSED).count()
    tagged_matches = ReplayTag.objects.values("match_id").distinct().count()
    parsed_rows = list(
        ReplayParse.objects
        .filter(status=ReplayParse.STATUS_PARSED)
        .select_related("match")
        .prefetch_related(
            Prefetch(
                "player_summaries",
                queryset=ReplayPlayerSummary.objects.select_related("participant").prefetch_related(
                    Prefetch(
                        "unit_summaries",
                        queryset=UnitProductionSummary.objects.order_by("-produced_count", "unit_name"),
                    )
                ),
            )
        )
        .order_by("-finished_at", "-updated_at")[:8]
    )
    pending_rows = list(
        ReplayParse.objects
        .filter(status=ReplayParse.STATUS_PENDING)
        .select_related("match")
        .order_by("-match__started_at", "-created_at")[:12]
    )

    context = {
        "canonical_url": request.build_absolute_uri(reverse("stats:replay_discovery")),
        "meta_description": (
            "Discover replay-driven Age of Mythology: Retold strategy patterns, "
            "parse coverage, and future study filters on Prostagma."
        ),
        "pending_parses": pending_parses,
        "parsed_replays": parsed_replays,
        "tagged_matches": tagged_matches,
        "parsed_rows": parsed_rows,
        "pending_rows": pending_rows,
        "strategy_tags": [
            "Fast Heroic",
            "Fast Mythic",
            "Boom",
            "Long Classical",
            "Early Pressure",
            "Archer Deathball",
            "Eagle Warrior Core",
            "Water Boom",
            "God Power Swing",
            "Upset Win",
            "High EAPM",
            "Long Macro Game",
        ],
    }
    return render(request, "stats/replay_discovery.html", context)
