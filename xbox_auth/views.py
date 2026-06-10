import base64
import json
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from .models import XboxProfile
from lobbies.leaderboard import resolve_worldsedge_identity_sync

MICROSOFT_AUTHORITY = "https://login.microsoftonline.com"
MICROSOFT_AUTHORIZE_PATH = "/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_PATH = "/oauth2/v2.0/token"
XBOX_USER_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XBOX_XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"


class XboxAuthError(Exception):
    pass


def get_safe_next_url(request, fallback="/"):
    next_url = request.GET.get("next") or request.POST.get("next") or fallback

    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return fallback


def get_tenant():
    return getattr(settings, "MICROSOFT_AUTH_TENANT", "consumers") or "consumers"


def get_client_id():
    return getattr(settings, "MICROSOFT_CLIENT_ID", "")


def get_client_secret():
    return getattr(settings, "MICROSOFT_CLIENT_SECRET", "")


def get_redirect_uri(request):
    configured = getattr(settings, "MICROSOFT_REDIRECT_URI", "")

    if configured:
        return configured

    return request.build_absolute_uri(reverse("xbox_auth:callback"))


def get_authorize_url():
    return f"{MICROSOFT_AUTHORITY}/{get_tenant()}{MICROSOFT_AUTHORIZE_PATH}"


def get_token_url():
    return f"{MICROSOFT_AUTHORITY}/{get_tenant()}{MICROSOFT_TOKEN_PATH}"


def decode_jwt_without_verification(token):
    """
    The token is received directly from Microsoft's token endpoint over HTTPS.
    This helper only decodes claims for account linking/display; it is not used
    to accept arbitrary client-provided tokens.
    """
    try:
        _header, payload, _signature = token.split(".")
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def exchange_code_for_tokens(request, code):
    client_id = get_client_id()
    client_secret = get_client_secret()

    if not client_id or not client_secret:
        raise XboxAuthError("Microsoft/Xbox sign-in is not configured yet.")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": get_redirect_uri(request),
        "scope": "openid profile email XboxLive.signin",
    }

    try:
        response = httpx.post(get_token_url(), data=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise XboxAuthError("Microsoft could not complete the sign-in token exchange.") from exc


def fetch_xbox_claims(access_token):
    """
    Best-effort Xbox services profile lookup.

    Microsoft account OIDC gives us a reliable account identity. The Xbox Live
    token flow adds gamer-facing metadata such as gamertag/XUID when available.
    If this fails, we still let the user sign in with the Microsoft account.
    """
    if not access_token:
        return {}

    user_auth_payload = {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": f"d={access_token}",
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
    }

    try:
        user_response = httpx.post(
            XBOX_USER_AUTH_URL,
            json=user_auth_payload,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        user_response.raise_for_status()
        user_payload = user_response.json()
        user_token = user_payload.get("Token")

        if not user_token:
            return {}

        xsts_payload = {
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [user_token],
            },
            "RelyingParty": "http://xboxlive.com",
            "TokenType": "JWT",
        }

        xsts_response = httpx.post(
            XBOX_XSTS_AUTH_URL,
            json=xsts_payload,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        xsts_response.raise_for_status()
        xsts_payload = xsts_response.json()
    except (httpx.HTTPError, ValueError):
        return {}

    xui = (
        xsts_payload
        .get("DisplayClaims", {})
        .get("xui", [])
    )

    if not xui:
        return {}

    item = xui[0]

    return {
        "xuid": item.get("xid") or item.get("xuid") or "",
        "user_hash": item.get("uhs") or "",
        "gamertag": item.get("gtg") or "",
        "gamerpic_url": item.get("pic") or "",
    }


def unique_username(base_username):
    User = get_user_model()
    base = str(base_username or "xbox_user").lower().replace(" ", "_")[:120]
    username = base
    suffix = 2

    while User.objects.filter(username=username).exists():
        username = f"{base[:112]}_{suffix}"
        suffix += 1

    return username


def get_or_create_user_for_xbox(request, microsoft_sub, display_name, email, xbox_claims):
    User = get_user_model()

    existing_profile = (
        XboxProfile.objects
        .select_related("user")
        .filter(microsoft_sub=microsoft_sub)
        .first()
    )

    if existing_profile:
        return existing_profile.user, existing_profile, False

    if request.user.is_authenticated:
        user = request.user
    else:
        xuid = xbox_claims.get("xuid") if xbox_claims else ""
        if xuid:
            username = unique_username(f"xbox_{xuid}")
        else:
            username = unique_username(f"xbox_{microsoft_sub[:32]}")

        user = User(username=username)
        user.first_name = (display_name or "")[:150]
        if email and hasattr(user, "email"):
            user.email = email
        user.set_unusable_password()
        user.save()

    profile = XboxProfile.objects.create(
        user=user,
        microsoft_sub=microsoft_sub,
    )

    return user, profile, True


@require_GET
def xbox_login(request):
    client_id = get_client_id()

    if not client_id:
        messages.error(request, "Microsoft/Xbox sign-in is not configured yet.")
        return redirect(get_safe_next_url(request))

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    request.session["xbox_auth_state"] = state
    request.session["xbox_auth_nonce"] = nonce
    request.session["xbox_auth_next"] = get_safe_next_url(request)

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": get_redirect_uri(request),
        "response_mode": "query",
        "scope": "openid profile email XboxLive.signin",
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
    }

    return redirect(f"{get_authorize_url()}?{urlencode(params)}")


@require_GET
def xbox_callback(request):
    if request.GET.get("error"):
        message = request.GET.get("error_description") or request.GET.get("error")
        return render(
            request,
            "xbox_auth/login_failed.html",
            {"message": message},
            status=400,
        )

    expected_state = request.session.pop("xbox_auth_state", "")
    expected_nonce = request.session.pop("xbox_auth_nonce", "")
    state = request.GET.get("state", "")
    code = request.GET.get("code", "")

    if not code or not expected_state or state != expected_state:
        return HttpResponseBadRequest("Microsoft/Xbox sign-in state did not validate.")

    try:
        token_payload = exchange_code_for_tokens(request, code)
    except XboxAuthError as exc:
        return render(
            request,
            "xbox_auth/login_failed.html",
            {"message": str(exc)},
            status=400,
        )

    id_token = token_payload.get("id_token", "")
    access_token = token_payload.get("access_token", "")
    claims = decode_jwt_without_verification(id_token)

    if expected_nonce and claims.get("nonce") and claims.get("nonce") != expected_nonce:
        return HttpResponseBadRequest("Microsoft/Xbox sign-in nonce did not validate.")

    microsoft_sub = claims.get("sub") or claims.get("oid")

    if not microsoft_sub:
        return HttpResponseBadRequest("Microsoft did not return an account identifier.")

    display_name = claims.get("name") or claims.get("preferred_username") or ""
    email = claims.get("preferred_username") or claims.get("email") or ""
    xbox_claims = fetch_xbox_claims(access_token)

    user, xbox_profile, _created = get_or_create_user_for_xbox(
        request,
        microsoft_sub=microsoft_sub,
        display_name=display_name,
        email=email,
        xbox_claims=xbox_claims,
    )

    xbox_profile.apply_microsoft_claims(claims)
    xbox_profile.apply_xbox_claims(xbox_claims)

    if xbox_profile.xuid:
        try:
            aom_identity = resolve_worldsedge_identity_sync(
                platform="xbox",
                platform_id=xbox_profile.xuid,
                fallback_name=xbox_profile.gamertag or display_name or "unknown user",
            )
            if aom_identity.get("ok"):
                xbox_profile.apply_aom_identity(aom_identity)
        except Exception:
            # AoM identity lookup is nice-to-have. Xbox sign-in should still work
            # even if Worlds Edge/Athens endpoints are unavailable or return no row.
            pass

    expires_in = token_payload.get("expires_in")
    if expires_in:
        try:
            xbox_profile.access_token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            pass

    xbox_profile.save()

    preferred_name = xbox_profile.display_name
    if preferred_name and user.first_name != preferred_name[:150]:
        user.first_name = preferred_name[:150]
        user.save(update_fields=["first_name"])

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Signed in with Xbox.")

    next_url = request.session.pop("xbox_auth_next", "/")

    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/"

    return redirect(next_url)


@require_http_methods(["GET", "POST"])
def xbox_logout(request):
    logout(request)
    messages.success(request, "Signed out.")
    return redirect(get_safe_next_url(request))


@login_required
@require_GET
def xbox_profile(request):
    return render(request, "xbox_auth/profile.html")
