import os
import re
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from lobbies.leaderboard import resolve_worldsedge_identity_sync

from .models import SteamProfile

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
STEAM_CLAIMED_ID_PATTERN = re.compile(r"^https://steamcommunity\.com/openid/id/(?P<steam_id>\d+)$")


def get_safe_next_url(request, fallback="/"):
    next_url = request.GET.get("next") or request.POST.get("next") or fallback

    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return fallback


def get_site_realm(request):
    configured_realm = getattr(settings, "STEAM_OPENID_REALM", "")

    if configured_realm:
        return configured_realm.rstrip("/") + "/"

    return request.build_absolute_uri("/")


def get_steam_web_api_key():
    return getattr(settings, "STEAM_WEB_API_KEY", "") or os.environ.get("STEAM_WEB_API_KEY", "")


def fetch_steam_player_summary(steam_id):
    api_key = get_steam_web_api_key()

    if not api_key:
        return None

    params = {
        "key": api_key,
        "steamids": steam_id,
        "format": "json",
    }

    try:
        response = httpx.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/",
            params=params,
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    players = payload.get("response", {}).get("players", [])

    if not players:
        return None

    return players[0]


@require_GET
def steam_login(request):
    request.session["steam_auth_next"] = get_safe_next_url(request)

    return_to = request.build_absolute_uri(reverse("steam_auth:callback"))
    realm = get_site_realm(request)

    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }

    return redirect(f"{STEAM_OPENID_ENDPOINT}?{urlencode(params)}")


@require_GET
def steam_callback(request):
    if request.GET.get("openid.mode") != "id_res":
        messages.error(request, "Steam sign-in was cancelled or did not complete.")
        return redirect("/")

    verification_params = request.GET.copy()
    verification_params["openid.mode"] = "check_authentication"

    try:
        response = httpx.post(
            STEAM_OPENID_ENDPOINT,
            data=verification_params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=8,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return render(
            request,
            "steam_auth/login_failed.html",
            {"message": "Steam could not verify the sign-in response."},
            status=400,
        )

    if "is_valid:true" not in response.text:
        return render(
            request,
            "steam_auth/login_failed.html",
            {"message": "Steam rejected the sign-in verification."},
            status=400,
        )

    claimed_id = request.GET.get("openid.claimed_id", "")
    match = STEAM_CLAIMED_ID_PATTERN.match(claimed_id)

    if not match:
        return HttpResponseBadRequest("Steam did not return a valid SteamID.")

    steam_id = match.group("steam_id")
    player_summary = fetch_steam_player_summary(steam_id)
    display_name = player_summary.get("personaname") if player_summary else ""

    User = get_user_model()
    username = f"steam_{steam_id}"
    user, _created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": display_name[:150] if display_name else "",
        },
    )

    if display_name and user.first_name != display_name[:150]:
        user.first_name = display_name[:150]
        user.save(update_fields=["first_name"])

    steam_profile, _created = SteamProfile.objects.get_or_create(
        steam_id=steam_id,
        defaults={"user": user},
    )

    if steam_profile.user_id != user.id:
        steam_profile.user = user

    if player_summary:
        steam_profile.apply_player_summary(player_summary)

    try:
        aom_identity = resolve_worldsedge_identity_sync(
            platform="steam",
            platform_id=steam_id,
            fallback_name=display_name or steam_profile.persona_name or "unknown user",
        )
        if aom_identity.get("ok"):
            steam_profile.apply_aom_identity(aom_identity)
    except Exception:
        # AoM identity lookup is nice-to-have. Steam sign-in should still work
        # even if Worlds Edge/Athens endpoints are unavailable or change shape.
        pass

    steam_profile.save()

    preferred_name = steam_profile.display_name
    if preferred_name and user.first_name != preferred_name[:150]:
        user.first_name = preferred_name[:150]
        user.save(update_fields=["first_name"])

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Signed in with Steam.")

    next_url = request.session.pop("steam_auth_next", "/")

    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/"

    return redirect(next_url)


@require_http_methods(["GET", "POST"])
def steam_logout(request):
    logout(request)
    messages.success(request, "Signed out.")
    return redirect(get_safe_next_url(request))


@login_required
@require_GET
def steam_profile(request):
    return render(request, "steam_auth/profile.html")
