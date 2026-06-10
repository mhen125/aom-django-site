import hashlib
import json
import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import AgoraIdentity, ChatMessage

MESSAGE_LIMIT = 80
MAX_BODY_LENGTH = 500
MAX_NAME_LENGTH = 32
NAME_CHANGE_COOLDOWN = timedelta(hours=1)
POST_COOLDOWN = timedelta(seconds=2)
SPAM_WINDOW = timedelta(seconds=10)
SPAM_MESSAGE_LIMIT = 10
SPAM_BAN_DURATION = timedelta(minutes=30)
FILTER_MUTE_DURATION = timedelta(minutes=30)
FILTER_MUTE_THRESHOLD = 3

SEVERE_PATTERNS = [
    (re.compile(r"\bn[\W_]*[i1!][\W_]*[gq][\W_]*[gq][\W_]*[e3][\W_]*r?s?\b", re.I), "[Removed: severe anti-Black slur]", "severe anti-Black slur"),
    (re.compile(r"\bk[\W_]*[i1!][\W_]*k[\W_]*[e3]s?\b", re.I), "[Removed: severe antisemitic slur]", "severe antisemitic slur"),
    (re.compile(r"\bch[\W_]*[i1!][\W_]*nk?s?\b", re.I), "[Removed: severe anti-Asian slur]", "severe anti-Asian slur"),
    (re.compile(r"\bsp[\W_]*[i1!][\W_]*c?s?\b", re.I), "[Removed: severe anti-Latino slur]", "severe anti-Latino slur"),
]

LIGHT_PATTERNS = [
    (re.compile(r"\bfag\b", re.I), "f*g", "masked slur"),
    (re.compile(r"\bfaggot\b", re.I), "f*ggot", "masked slur"),
    (re.compile(r"\basshole\b", re.I), "ass****", "masked profanity"),
]


def agora_room(request):
    return render(request, "agora/agora.html")


def _hash_value(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _get_payload(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST


def _get_or_create_identity(request, payload):
    browser_token = (
        request.headers.get("X-Agora-Client-Id")
        or payload.get("clientId")
        or payload.get("client_id")
        or "anonymous"
    )
    ip_hash = _hash_value(_get_client_ip(request))
    token_hash = _hash_value(browser_token)
    identity, _created = AgoraIdentity.objects.get_or_create(
        browser_token_hash=token_hash,
        defaults={"ip_hash": ip_hash},
    )
    identity.ip_hash = ip_hash
    identity.last_seen_at = timezone.now()
    identity.clear_expired_restrictions()
    identity.save(update_fields=["ip_hash", "last_seen_at"])
    return identity


def _get_steam_profile(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "steam_profile", None)


def get_agora_display_name(request, submitted_name=""):
    if request.user.is_authenticated:
        steam_profile = _get_steam_profile(request.user)
        if steam_profile and getattr(steam_profile, "persona_name", ""):
            return steam_profile.persona_name.strip()[:MAX_NAME_LENGTH]
        return request.user.username.strip()[:MAX_NAME_LENGTH]

    clean_name = (submitted_name or "Villager").strip()[:MAX_NAME_LENGTH]
    return clean_name or "Villager"


def _format_message(message):
    steam_profile = _get_steam_profile(message.user)
    avatar_url = getattr(steam_profile, "avatar_url", "") if steam_profile else ""
    profile_url = getattr(steam_profile, "profile_url", "") if steam_profile else ""

    return {
        "id": message.id,
        "displayName": message.display_name,
        "body": message.body_clean,
        "createdAt": message.created_at.isoformat(),
        "wasFiltered": message.was_filtered,
        "filterHits": message.filter_hits or [],
        "isSteamUser": bool(message.user_id),
        "avatarUrl": avatar_url,
        "profileUrl": profile_url,
    }


def filter_message_body(body):
    filtered = str(body or "")[:MAX_BODY_LENGTH]
    hits = []

    for pattern, replacement, label in SEVERE_PATTERNS:
        filtered, count = pattern.subn(replacement, filtered)
        if count:
            hits.extend([label] * count)

    for pattern, replacement, label in LIGHT_PATTERNS:
        filtered, count = pattern.subn(replacement, filtered)
        if count:
            hits.extend([label] * count)

    return filtered.strip(), hits


def _restriction_response(identity):
    identity.clear_expired_restrictions()

    if identity.banned_active():
        return JsonResponse(
            {
                "ok": False,
                "error": "You are temporarily banned from posting.",
                "restrictedUntil": identity.banned_until.isoformat() if identity.banned_until else None,
            },
            status=429,
        )

    if identity.muted_active():
        return JsonResponse(
            {
                "ok": False,
                "error": "You are temporarily muted from posting.",
                "restrictedUntil": identity.muted_until.isoformat() if identity.muted_until else None,
            },
            status=429,
        )

    return None


def _enforce_name_cooldown(identity, new_display_name):
    if not new_display_name or new_display_name == identity.display_name:
        return None

    now = timezone.now()
    if identity.name_changed_at and now - identity.name_changed_at < NAME_CHANGE_COOLDOWN:
        remaining = NAME_CHANGE_COOLDOWN - (now - identity.name_changed_at)
        minutes = max(1, int(remaining.total_seconds() // 60))
        return f"Display name changes are limited to once per hour. Try again in about {minutes} minute(s)."

    identity.display_name = new_display_name
    identity.name_changed_at = now
    identity.save(update_fields=["display_name", "name_changed_at"])
    return None


def _enforce_rate_limits(identity):
    now = timezone.now()
    recent_messages = ChatMessage.objects.filter(identity=identity, created_at__gte=now - SPAM_WINDOW)

    if recent_messages.count() >= SPAM_MESSAGE_LIMIT:
        identity.is_banned = True
        identity.banned_until = now + SPAM_BAN_DURATION
        identity.ban_reason = "Automatic temporary ban for message spam."
        identity.save(update_fields=["is_banned", "banned_until", "ban_reason"])
        return "Too many messages too quickly. You are temporarily banned from posting."

    latest_message = ChatMessage.objects.filter(identity=identity).order_by("-created_at").first()
    if latest_message and now - latest_message.created_at < POST_COOLDOWN:
        return "Slow down a little before sending another message."

    return None


def _apply_filter_penalty(identity, hits):
    severe_hits = [hit for hit in hits if hit.startswith("severe")]
    if not severe_hits:
        return

    now = timezone.now()
    identity.severe_filter_hits += len(severe_hits)
    identity.last_filter_hit_at = now

    if identity.severe_filter_hits >= FILTER_MUTE_THRESHOLD:
        identity.is_muted = True
        identity.muted_until = now + FILTER_MUTE_DURATION
        identity.mute_reason = "Automatic temporary mute for repeated severe filtered words."

    identity.save(update_fields=[
        "severe_filter_hits",
        "last_filter_hit_at",
        "is_muted",
        "muted_until",
        "mute_reason",
    ])


@require_GET
def api_messages(request):
    messages = list(
        ChatMessage.objects
        .filter(is_deleted=False)
        .select_related("user")
        .order_by("-created_at")[:MESSAGE_LIMIT]
    )
    messages.reverse()

    return JsonResponse({
        "ok": True,
        "messages": [_format_message(message) for message in messages],
        "serverTime": timezone.now().isoformat(),
    })


@require_POST
def api_post_message(request):
    payload = _get_payload(request)
    identity = _get_or_create_identity(request, payload)

    restriction = _restriction_response(identity)
    if restriction:
        return restriction

    submitted_name = str(payload.get("displayName") or payload.get("display_name") or "").strip()
    display_name = get_agora_display_name(request, submitted_name)

    if not request.user.is_authenticated:
        cooldown_error = _enforce_name_cooldown(identity, display_name)
        if cooldown_error:
            return JsonResponse({"ok": False, "error": cooldown_error}, status=429)
    else:
        if identity.display_name != display_name:
            identity.display_name = display_name
            identity.save(update_fields=["display_name"])

    rate_error = _enforce_rate_limits(identity)
    if rate_error:
        return JsonResponse({"ok": False, "error": rate_error}, status=429)

    body_original = str(payload.get("body") or "").strip()[:MAX_BODY_LENGTH]
    if not body_original:
        return JsonResponse({"ok": False, "error": "Message cannot be empty."}, status=400)

    body_clean, hits = filter_message_body(body_original)
    if not body_clean:
        return JsonResponse({"ok": False, "error": "Message cannot be empty after filtering."}, status=400)

    message = ChatMessage.objects.create(
        identity=identity,
        user=request.user if request.user.is_authenticated else None,
        display_name=display_name,
        body_original=body_original,
        body_clean=body_clean,
        was_filtered=bool(hits),
        filter_hits=hits,
        ip_hash=identity.ip_hash,
    )

    _apply_filter_penalty(identity, hits)

    return JsonResponse({"ok": True, "message": _format_message(message)})
