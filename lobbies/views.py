from django.http import JsonResponse
from django.shortcuts import render

from .services import CACHE_SECONDS, get_live_activity, get_normalized_lobbies
from .leaderboard import fetch_player_rating, fetch_player_summary
from .stats import build_player_recent_stats
from .aomstats import get_active_custom_matches, get_active_ranked_matches


def _refresh_requested(request):
    return request.GET.get("refresh") in {"1", "true", "yes"}


def _json_cache_response(payload, *, status=200, refresh=False, max_age=CACHE_SECONDS):
    response = JsonResponse(payload, status=status)

    if refresh or status >= 400:
        response["Cache-Control"] = "no-store"
    else:
        response["Cache-Control"] = f"public, max-age={max_age}, stale-while-revalidate={max_age}"

    return response


def live_activity_home(request):
    return render(
        request,
        "live_activity.html",
        {
            "canonical_url": request.build_absolute_uri("/"),
            "meta_description": (
                "Live Age of Mythology: Retold activity dashboard for Steam players online, "
                "ranked queues, custom matches, open lobbies, and active server regions."
            ),
        },
    )


def lobby_browser(request):
    return render(
        request,
        "lobbies.html",
        {
            "canonical_url": request.build_absolute_uri("/lobbies/"),
            "meta_description": (
                "Browse live Age of Mythology: Retold custom lobbies, in-progress custom games, "
                "and ranked matches with maps, player slots, regions, and lobby details."
            ),
        },
    )


async def api_lobbies(request):
    refresh = _refresh_requested(request)
    raw_pages = request.GET.get("pages", "4")

    try:
        pages = int(raw_pages)
    except ValueError:
        pages = 4

    pages = max(1, min(pages, 10))
    start_values = [index * 25 for index in range(pages)]

    try:
        lobbies = await get_normalized_lobbies(
            force_refresh=refresh,
            start_values=start_values,
        )
    except Exception as error:
        return _json_cache_response(
            {
                "ok": False,
                "error": str(error),
                "lobbies": [],
            },
            status=502,
            refresh=True,
        )

    return _json_cache_response(
        {
            "ok": True,
            "cache_seconds": CACHE_SECONDS,
            "count": len(lobbies),
            "lobbies": lobbies,
        },
        refresh=refresh,
    )


async def api_live_activity(request):
    refresh = _refresh_requested(request)

    try:
        activity = await get_live_activity(force_refresh=refresh)
    except Exception as error:
        return _json_cache_response(
            {
                "generatedAt": None,
                "source": "error",
                "status": {
                    "label": "Error",
                    "busynessLabel": "Unavailable",
                    "ratio": None,
                    "percentDifference": None,
                    "currentPlayersInLobbies": 0,
                    "typicalPlayersInLobbies": None,
                    "baselineSampleCount": 0,
                    "baselineWindowMinutes": 45,
                },
                "summary": {
                    "openLobbies": 0,
                    "publicMpLobbies": 0,
                    "activeMatches": 0,
                    "playersInLobbies": 0,
                    "activePlayers": 0,
                    "topRegion": None,
                    "steamPlayersOnline": None,
                },
                "regions": [],
                "modes": [],
                "error": str(error),
            },
            status=502,
            refresh=True,
        )

    return _json_cache_response(activity, refresh=refresh)


def api_active_matches(request):
    refresh = _refresh_requested(request)

    try:
        matches = get_active_ranked_matches(force_refresh=refresh)
    except Exception as error:
        return _json_cache_response(
            {
                "ok": False,
                "source": "aomstats_ranked",
                "error": str(error),
                "matches": [],
            },
            status=502,
            refresh=True,
        )

    return _json_cache_response(
        {
            "ok": True,
            "source": "aomstats_ranked",
            "count": len(matches),
            "matches": matches,
        },
        refresh=refresh,
    )


def api_active_custom_matches(request):
    refresh = _refresh_requested(request)

    try:
        matches = get_active_custom_matches(force_refresh=refresh)
    except Exception as error:
        return _json_cache_response(
            {
                "ok": False,
                "source": "aomstats_customs",
                "error": str(error),
                "matches": [],
            },
            status=502,
            refresh=True,
        )

    return _json_cache_response(
        {
            "ok": True,
            "source": "aomstats_customs",
            "count": len(matches),
            "matches": matches,
        },
        refresh=refresh,
    )


async def api_player_rating(request):
    raw_profile_id = request.GET.get("profile_id")
    player = request.GET.get("player", "")
    raw_match_type = request.GET.get("match_type", "1")
    refresh = _refresh_requested(request)
    transport = request.GET.get("transport", "curl")

    profile_id = None

    if raw_profile_id not in (None, ""):
        try:
            profile_id = int(raw_profile_id)
        except ValueError:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "profile_id must be an integer.",
                },
                status=400,
            )

    if profile_id is None and not player:
        return JsonResponse(
            {
                "ok": False,
                "error": "Provide profile_id, player, or both.",
            },
            status=400,
        )

    try:
        match_type = int(raw_match_type)
    except ValueError:
        match_type = 1

    try:
        payload = await fetch_player_rating(
            profile_id=profile_id,
            player=player,
            match_type=match_type,
            refresh=refresh,
            force_transport=transport,
        )
    except Exception as error:
        return JsonResponse(
            {
                "ok": False,
                "error": str(error),
                "rating": None,
                "ratings": [],
            },
            status=502,
        )

    return JsonResponse(payload)


async def api_player_summary(request):
    raw_profile_id = request.GET.get("profile_id")
    player = request.GET.get("player", "unknown user")
    raw_recent_match_type = request.GET.get("recent_match_type", "1")
    raw_recent_count = request.GET.get("recent_count", "10")
    refresh = _refresh_requested(request)
    transport = request.GET.get("transport", "curl")

    if raw_profile_id in (None, ""):
        return JsonResponse(
            {
                "ok": False,
                "error": "profile_id is required.",
                "summary": None,
                "ratings": [],
                "recent_matches": [],
            },
            status=400,
        )

    try:
        profile_id = int(raw_profile_id)
    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "profile_id must be an integer.",
                "summary": None,
                "ratings": [],
                "recent_matches": [],
            },
            status=400,
        )

    try:
        recent_match_type = int(raw_recent_match_type)
    except ValueError:
        recent_match_type = 1

    try:
        recent_count = int(raw_recent_count)
    except ValueError:
        recent_count = 10

    recent_count = max(1, min(recent_count, 25))

    try:
        payload = await fetch_player_summary(
            profile_id=profile_id,
            player=player,
            recent_match_type=recent_match_type,
            recent_count=recent_count,
            refresh=refresh,
            force_transport=transport,
        )
    except Exception as error:
        return JsonResponse(
            {
                "ok": False,
                "error": str(error),
                "summary": None,
                "ratings": [],
                "recent_matches": [],
            },
            status=502,
        )

    return JsonResponse(payload)

async def api_player_god_stats(request):
    raw_profile_id = request.GET.get("profile_id")
    player = request.GET.get("player", "unknown user")
    raw_recent_count = request.GET.get("recent_count", "25")
    refresh = _refresh_requested(request)
    transport = request.GET.get("transport", "curl")

    if raw_profile_id in (None, ""):
        return JsonResponse(
            {
                "ok": False,
                "error": "profile_id is required.",
            },
            status=400,
        )

    try:
        profile_id = int(raw_profile_id)
    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "profile_id must be an integer.",
            },
            status=400,
        )

    try:
        recent_count = int(raw_recent_count)
    except ValueError:
        recent_count = 25

    recent_count = max(1, min(recent_count, 50))

    try:
        payload = await build_player_recent_stats(
            profile_id=profile_id,
            player=player,
            recent_count=recent_count,
            refresh=refresh,
            force_transport=transport,
        )
    except Exception as error:
        return JsonResponse(
            {
                "ok": False,
                "error": str(error),
                "summary": {},
                "gods": [],
                "maps": [],
                "match_type_breakdown": [],
            },
            status=502,
        )

    return JsonResponse(payload)
