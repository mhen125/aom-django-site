# Steam authentication install notes

This pack adds a small local Django app named `steam_auth`. Steam uses OpenID 2.0 for web sign-in; the returned claimed ID contains the user's 64-bit SteamID.

## 1. Add the app

In `config/settings.py`, add `steam_auth` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "builds",
    "lobbies",
    "agora",
    "steam_auth",
]
```

Optional, if you want avatars/display names from Steam's Web API:

```python
STEAM_WEB_API_KEY = os.environ.get("STEAM_WEB_API_KEY", "")
STEAM_OPENID_REALM = os.environ.get("STEAM_OPENID_REALM", "")
LOGIN_URL = "/auth/steam/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
```

If your settings file does not already import `os`, add:

```python
import os
```

## 2. Add routes

In `config/urls.py`, add:

```python
path("auth/steam/", include("steam_auth.urls")),
```

Example:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/steam/", include("steam_auth.urls")),
    path("agora/", include("agora.urls")),
    path("build_orders/", include("builds.urls")),
    path("build-orders/", include("builds.urls")),
    path("lobbies/", include("lobbies.urls")),
    path("", include("lobbies.urls")),
]
```

## 3. Load the Steam auth CSS

In `base.html`, add this after `site_brand.css` or your shared CSS links:

```django
<link rel="stylesheet" href="{% static 'css/steam_auth.css' %}">
```

## 4. Header

This pack includes an updated `lobbies/templates/partials/header.html` based on the current shared header. It adds a desktop/mobile "Sign in with Steam" control.

## 5. Migrate

```bash
python manage.py migrate
```

## 6. Test

Open:

```text
/auth/steam/login/
/auth/steam/profile/
```

The login flow itself works without `STEAM_WEB_API_KEY`; the API key is only used to fetch persona name/avatar/profile URL.
