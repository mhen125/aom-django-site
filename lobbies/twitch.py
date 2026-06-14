import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta, timezone as datetime_timezone

from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime


TWITCH_GAME_ID = os.getenv("TWITCH_GAME_ID", "1260")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_ACCESS_TOKEN = os.getenv("TWITCH_ACCESS_TOKEN", "")

TWITCH_HELIX_VIDEOS_URL = "https://api.twitch.tv/helix/videos"
TWITCH_CACHE_SECONDS = int(os.getenv("TWITCH_CACHE_SECONDS", "1800"))
TWITCH_TIMEOUT_SECONDS = float(os.getenv("TWITCH_TIMEOUT_SECONDS", "4.5"))

TWITCH_THUMBNAIL_WIDTH = os.getenv("TWITCH_THUMBNAIL_WIDTH", "640")
TWITCH_THUMBNAIL_HEIGHT = os.getenv("TWITCH_THUMBNAIL_HEIGHT", "360")


def _has_twitch_credentials():
    return bool(TWITCH_CLIENT_ID and TWITCH_ACCESS_TOKEN)


def _format_view_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        return "0 views"

    if count >= 1_000_000:
        formatted = f"{count / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}M views"

    if count >= 1_000:
        formatted = f"{count / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}K views"

    return f"{count:,} views"


def _format_relative_date(value):
    if value is None:
        return "Recently"

    now = timezone.now()

    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone=datetime_timezone.utc)

    delta = now - value

    if delta < timedelta(minutes=1):
        return "Just now"

    if delta < timedelta(hours=1):
        minutes = max(1, int(delta.total_seconds() // 60))
        return f"{minutes}m ago"

    if delta < timedelta(days=1):
        hours = max(1, int(delta.total_seconds() // 3600))
        return f"{hours}h ago"

    if delta < timedelta(days=30):
        days = max(1, delta.days)
        return f"{days}d ago"

    if delta < timedelta(days=365):
        months = max(1, delta.days // 30)
        return f"{months}mo ago"

    years = max(1, delta.days // 365)
    return f"{years}y ago"


def _normalize_thumbnail_url(value):
    thumbnail_url = value or ""

    return (
        thumbnail_url
        .replace("%{width}", TWITCH_THUMBNAIL_WIDTH)
        .replace("%{height}", TWITCH_THUMBNAIL_HEIGHT)
    )


def _parse_twitch_datetime(value):
    if not value:
        return None

    parsed = parse_datetime(value)

    if parsed is None:
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)

    return parsed


def _normalize_twitch_video(video):
    published_at = _parse_twitch_datetime(video.get("published_at") or video.get("created_at"))

    return {
        "id": video.get("id") or "",
        "stream_id": video.get("stream_id") or "",
        "user_id": video.get("user_id") or "",
        "user_login": video.get("user_login") or "",
        "creator": video.get("user_name") or video.get("user_login") or "AoM Creator",
        "title": video.get("title") or "Age of Mythology: Retold broadcast",
        "description": video.get("description") or "",
        "published_at": published_at,
        "published_label": _format_relative_date(published_at),
        "url": video.get("url") or "https://www.twitch.tv/directory/category/age-of-mythology-retold/videos/all",
        "thumbnail_url": _normalize_thumbnail_url(video.get("thumbnail_url")),
        "view_count": int(video.get("view_count") or 0),
        "view_count_label": _format_view_count(video.get("view_count")),
        "language": (video.get("language") or "").upper(),
        "type": video.get("type") or "",
        "duration": video.get("duration") or "",
    }


def _fetch_twitch_videos(limit=6):
    query = urllib.parse.urlencode(
        {
            "game_id": TWITCH_GAME_ID,
            "period": "month",
            "sort": "views",
            "first": max(1, min(int(limit), 20)),
        }
    )

    request = urllib.request.Request(
        f"{TWITCH_HELIX_VIDEOS_URL}?{query}",
        headers={
            "Client-Id": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {TWITCH_ACCESS_TOKEN}",
            "Accept": "application/json",
            "User-Agent": "Prostagma/1.0 (+https://prostagma.live)",
        },
    )

    with urllib.request.urlopen(request, timeout=TWITCH_TIMEOUT_SECONDS) as response:
        raw_body = response.read().decode("utf-8", errors="replace")

    payload = json.loads(raw_body)
    videos = payload.get("data", [])

    if not isinstance(videos, list):
        videos = []

    return [_normalize_twitch_video(video) for video in videos if isinstance(video, dict)]


def get_twitch_spotlight(limit=6, force_refresh=False):
    safe_limit = max(1, min(int(limit or 6), 12))
    cache_key = f"prostagma:twitch:videos:{TWITCH_GAME_ID}:month:views:{safe_limit}"

    if not force_refresh:
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

    if not _has_twitch_credentials():
        payload = {
            "ok": False,
            "source": "twitch",
            "configured": False,
            "generated_at": timezone.now(),
            "videos": [],
            "error": "Missing TWITCH_CLIENT_ID or TWITCH_ACCESS_TOKEN.",
        }
        cache.set(cache_key, payload, min(TWITCH_CACHE_SECONDS, 300))
        return payload

    try:
        videos = _fetch_twitch_videos(limit=safe_limit)
        payload = {
            "ok": bool(videos),
            "source": "twitch",
            "configured": True,
            "generated_at": timezone.now(),
            "videos": videos,
            "error": "",
        }
        cache.set(cache_key, payload, TWITCH_CACHE_SECONDS)
        return payload

    except (
        json.JSONDecodeError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        payload = {
            "ok": False,
            "source": "twitch",
            "configured": True,
            "generated_at": timezone.now(),
            "videos": [],
            "error": str(error),
        }
        cache.set(cache_key, payload, min(TWITCH_CACHE_SECONDS, 300))
        return payload
