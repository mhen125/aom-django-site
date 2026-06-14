import html
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .services import CACHE_SECONDS, get_live_activity, get_normalized_lobbies
from .leaderboard import fetch_community_leaderboard2, fetch_player_rating, fetch_player_summary, search_leaderboard
from .leaderboard_metadata import build_leaderboard_metadata_payload, get_queue_meta, get_ranked_queues
from .stats import build_player_recent_stats
from .aomstats import get_active_custom_matches, get_active_ranked_matches
from stats.readers import (
    get_imported_leaderboard_rows,
    get_imported_player_rating,
    get_imported_player_recent_stats,
    get_imported_player_summary,
)


def _refresh_requested(request):
    return request.GET.get("refresh") in {"1", "true", "yes"}


def _json_cache_response(payload, *, status=200, refresh=False, max_age=CACHE_SECONDS):
    response = JsonResponse(payload, status=status)

    if refresh or status >= 400:
        response["Cache-Control"] = "no-store"
    else:
        response["Cache-Control"] = f"public, max-age={max_age}, stale-while-revalidate={max_age}"

    return response


STEAM_APP_ID = 1934680
STEAM_RSS_URL = "https://steamcommunity.com/games/1934680/rss"
STEAM_NEWS_URL = (
    "https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/"
    "?appid=1934680&count=5&maxlength=500&format=json"
)
HOME_NEWS_CACHE_SECONDS = 60 * 30
HOME_NEWS_FRESH_DAYS = 14

_home_news_cache = {
    "created_at": 0.0,
    "data": None,
}


def _fetch_text(url, timeout=5):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Prostagma/1.0 (+https://prostagma.live)",
            "Accept": "application/rss+xml, application/json, text/xml;q=0.9, */*;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_steam_date(value):
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _plain_text_from_html(value, max_length=220):
    unescaped = html.unescape(value or "")
    without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", unescaped, flags=re.I | re.S)
    with_breaks = re.sub(r"<\s*(br|/p|/div|/li|/blockquote|hr)[^>]*>", " ", without_scripts, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", with_breaks)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()

    if len(text) <= max_length:
        return text

    trimmed = text[: max_length - 1].rsplit(" ", 1)[0].strip()
    return f"{trimmed}..."


def _first_image_from_html(value):
    unescaped = html.unescape(value or "")
    match = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", unescaped, flags=re.I)
    return html.unescape(match.group(1)) if match else ""


def _normalize_news_item(index, title, link, published_at, summary_html, author="Steam"):
    now = datetime.now(timezone.utc)
    age_days = None

    if published_at is not None:
        age_days = max(0, (now - published_at).days)

    return {
        "id": f"steam-news-{index}",
        "title": title or "Age of Mythology: Retold News",
        "url": link or "https://steamcommunity.com/games/1934680",
        "author": author or "Steam",
        "publishedAt": published_at.isoformat() if published_at else None,
        "ageDays": age_days,
        "isFresh": age_days is not None and age_days <= HOME_NEWS_FRESH_DAYS,
        "imageUrl": _first_image_from_html(summary_html),
        "summary": _plain_text_from_html(summary_html),
    }


def _parse_steam_rss(xml_text):
    root = ET.fromstring(xml_text)
    items = []

    for index, item in enumerate(root.findall("./channel/item")):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        published_at = _parse_steam_date(item.findtext("pubDate"))
        description = item.findtext("description") or ""
        author = item.findtext("author") or "Steam"
        items.append(_normalize_news_item(index, title, link, published_at, description, author))

    return items


def _parse_steam_news_json(json_text):
    payload = json.loads(json_text)
    news_items = payload.get("appnews", {}).get("newsitems", [])
    items = []

    for index, item in enumerate(news_items):
        published_at = None
        raw_date = item.get("date")

        if raw_date:
            try:
                published_at = datetime.fromtimestamp(int(raw_date), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                published_at = None

        items.append(
            _normalize_news_item(
                index,
                item.get("title") or "",
                item.get("url") or "",
                published_at,
                item.get("contents") or "",
                item.get("author") or "Steam",
            )
        )

    return items


def _get_home_news(force_refresh=False):
    now = time.time()

    if (
        not force_refresh
        and _home_news_cache["data"] is not None
        and now - _home_news_cache["created_at"] < HOME_NEWS_CACHE_SECONDS
    ):
        return _home_news_cache["data"]

    source = "steam_rss"
    error = None

    try:
        items = _parse_steam_rss(_fetch_text(STEAM_RSS_URL))
    except (ET.ParseError, urllib.error.URLError, TimeoutError, OSError, ValueError) as rss_error:
        source = "steam_news_api"
        error = str(rss_error)

        try:
            items = _parse_steam_news_json(_fetch_text(STEAM_NEWS_URL))
        except (json.JSONDecodeError, urllib.error.URLError, TimeoutError, OSError, ValueError) as news_error:
            items = []
            error = str(news_error)

    fresh_items = [item for item in items if item["isFresh"]]
    featured = fresh_items[0] if fresh_items else (items[0] if items else None)

    payload = {
        "ok": bool(items),
        "source": source,
        "freshDays": HOME_NEWS_FRESH_DAYS,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "featured": featured,
        "items": items[:6],
        "error": error,
    }

    _home_news_cache["created_at"] = now
    _home_news_cache["data"] = payload
    return payload


def live_activity_home(request):
    return render(
        request,
        "live_activity.html",
        {
            "canonical_url": request.build_absolute_uri("/activity/"),
            "meta_description": (
                "Live Age of Mythology: Retold activity dashboard for Steam players online, "
                "ranked queues, custom matches, open lobbies, and active server regions."
            ),
        },
    )


def landing_home(request):
    return render(
        request,
        "landing.html",
        {
            "canonical_url": request.build_absolute_uri("/"),
            "meta_description": (
                "Prostagma is an Age of Mythology: Retold hub for live lobbies, global activity, "
                "build orders, and community tools."
            ),
        },
    )


def _get_authenticated_player_identity(user):
    for relation_name in ["steam_profile", "xbox_profile"]:
        try:
            profile = getattr(user, relation_name)
        except ObjectDoesNotExist:
            profile = None

        if not profile:
            continue

        profile_id = getattr(profile, "aom_profile_id", None)
        if not profile_id:
            continue

        player_name = getattr(profile, "aom_alias", "") or getattr(profile, "display_name", "") or ""
        return {
            "profile_id": int(profile_id),
            "player": player_name.strip(),
        }

    return None


def leaderboard_home(request):
    return render(
        request,
        "leaderboards.html",
        {
            "canonical_url": request.build_absolute_uri("/leaderboards/"),
            "meta_description": (
                "Browse Age of Mythology: Retold ranked ladders, search player profiles, "
                "and review recent god and match statistics on Prostagma."
            ),
            "leaderboard_metadata": build_leaderboard_metadata_payload(),
            "default_ranked_match_types": get_ranked_queues(),
        },
    )


@login_required
def my_player_stats_redirect(request):
    identity = _get_authenticated_player_identity(request.user)

    if identity is None:
        messages.error(request, "Your account does not have a linked Age of Mythology profile yet.")

        try:
            request.user.steam_profile
            return redirect(reverse("steam_auth:profile"))
        except ObjectDoesNotExist:
            pass

        try:
            request.user.xbox_profile
            return redirect(reverse("xbox_auth:profile"))
        except ObjectDoesNotExist:
            pass

        return redirect(reverse("lobbies:leaderboard_home"))

    params = {
        "profile_id": identity["profile_id"],
        "player": identity["player"],
    }
    target = f"{reverse('stats:player_stats_home')}?{urlencode(params)}"
    return redirect(target)


def player_stats_home(request):
    return render(
        request,
        "player_stats.html",
        {
            "canonical_url": request.build_absolute_uri("/stats/player/"),
            "meta_description": (
                "View Age of Mythology: Retold player ratings, recent matches, god usage, "
                "and queue-specific performance on Prostagma."
            ),
            "leaderboard_metadata": build_leaderboard_metadata_payload(),
            "default_ranked_match_types": get_ranked_queues(),
            "initial_player": request.GET.get("player", "").strip(),
            "initial_profile_id": request.GET.get("profile_id", "").strip(),
            "initial_match_type": request.GET.get("match_type", "1").strip() or "1",
        },
    )


def api_home_news(request):
    refresh = _refresh_requested(request)
    payload = _get_home_news(force_refresh=refresh)
    return _json_cache_response(payload, refresh=refresh, max_age=HOME_NEWS_CACHE_SECONDS)


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
        payload = {
            "ok": False,
            "error": str(error),
            "rating": None,
            "ratings": [],
        }

    if payload.get("ok") and payload.get("rating"):
        return JsonResponse(payload)

    imported_payload = await sync_to_async(get_imported_player_rating)(
        profile_id=profile_id,
        player=player,
        match_type=match_type,
    )
    if imported_payload is not None:
        return JsonResponse(imported_payload)

    if payload.get("error"):
        return JsonResponse(payload, status=502)

    return JsonResponse(payload)


async def api_leaderboard_search(request):
    player = request.GET.get("player", "").strip()
    raw_match_type = request.GET.get("match_type", "1")
    raw_page = request.GET.get("page", "1")
    raw_count = request.GET.get("count", "25")
    refresh = _refresh_requested(request)
    transport = request.GET.get("transport", "auto")

    try:
        match_type = int(raw_match_type)
    except ValueError:
        match_type = 1

    try:
        page = int(raw_page)
    except ValueError:
        page = 1

    try:
        count = int(raw_count)
    except ValueError:
        count = 25

    page = max(1, min(page, 50))
    count = max(1, min(count, 100))

    try:
        if not player:
            queue_meta = get_queue_meta(match_type) or {}
            leaderboard_id = queue_meta.get("id")
            if leaderboard_id is not None:
                payload = await fetch_community_leaderboard2(
                    leaderboard_id=int(leaderboard_id),
                    page=page,
                    count=count,
                    refresh=refresh,
                )
            else:
                payload = await search_leaderboard(
                    player=player,
                    match_type=match_type,
                    page=page,
                    count=count,
                    refresh=refresh,
                    force_transport=transport,
                )
        else:
            payload = await search_leaderboard(
                player=player,
                match_type=match_type,
                page=page,
                count=count,
                refresh=refresh,
                force_transport=transport,
            )
    except Exception as error:
        payload = {
            "ok": False,
            "error": str(error),
            "matches": [],
        }

    if payload.get("ok") and payload.get("match_count"):
        return JsonResponse(payload)

    imported_payload = await sync_to_async(get_imported_leaderboard_rows)(
        match_type=match_type,
        page=page,
        count=count,
        player=player,
    )
    if imported_payload.get("match_count"):
        return JsonResponse(imported_payload)

    if payload.get("error"):
        return JsonResponse(payload, status=502)

    return JsonResponse(payload)


def api_leaderboard_metadata(request):
    refresh = _refresh_requested(request)
    payload = {
        "ok": True,
        **build_leaderboard_metadata_payload(),
    }
    return _json_cache_response(payload, refresh=refresh, max_age=HOME_NEWS_CACHE_SECONDS)


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

    recent_count = max(1, min(recent_count, 100))

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
        payload = {
            "ok": False,
            "error": str(error),
            "summary": None,
            "ratings": [],
            "recent_matches": [],
        }

    if payload.get("ok") and (payload.get("ratings") or payload.get("recent_matches", {}).get("match_count")):
        return JsonResponse(payload)

    imported_payload = await sync_to_async(get_imported_player_summary)(
        profile_id=profile_id,
        player=player,
        recent_match_type=recent_match_type,
        recent_count=recent_count,
    )
    if imported_payload is not None:
        return JsonResponse(imported_payload)

    if payload.get("error"):
        return JsonResponse(payload, status=502)

    return JsonResponse(payload)

async def api_player_god_stats(request):
    raw_profile_id = request.GET.get("profile_id")
    player = request.GET.get("player", "unknown user")
    raw_recent_count = request.GET.get("recent_count", "25")
    raw_match_type = request.GET.get("match_type", "")
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
    match_types = None

    if raw_match_type not in (None, ""):
        try:
            match_types = [int(raw_match_type)]
        except ValueError:
            match_types = None

    try:
        payload = await build_player_recent_stats(
            profile_id=profile_id,
            player=player,
            recent_count=recent_count,
            match_types=match_types,
            refresh=refresh,
            force_transport=transport,
        )
    except Exception as error:
        payload = {
            "ok": False,
            "error": str(error),
            "summary": {},
            "gods": [],
            "maps": [],
            "match_type_breakdown": [],
        }

    if payload.get("ok") and (payload.get("gods") or payload.get("maps") or payload.get("summary")):
        return JsonResponse(payload)

    if match_types:
        imported_payload = await sync_to_async(get_imported_player_recent_stats)(
            profile_id=profile_id,
            player=player,
            recent_count=recent_count,
            match_types=match_types,
        )
        if imported_payload is not None:
            return JsonResponse(imported_payload)

    if payload.get("error"):
        return JsonResponse(payload, status=502)

    return JsonResponse(payload)
