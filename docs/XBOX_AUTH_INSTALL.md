# Xbox / Microsoft sign-in install notes

This integration adds a `Sign in with Xbox` button through Microsoft account OAuth/OpenID Connect, then attempts a best-effort Xbox Live token exchange so the site can store gamertag/XUID when Microsoft returns the Xbox claims.

## 1. Copy files

Copy these into your project:

```text
xbox_auth/
lobbies/templates/base.html
lobbies/templates/partials/header.html
static/css/site_auth.css
static/css/editor.css
```

`static/css/editor.css` is included only for the modal-width v6 tweak. If you already changed editor CSS after v5, merge just the `.editor-confirm-*` rules.

## 2. Add app/settings

In `config/settings.py`:

```python
INSTALLED_APPS += [
    "xbox_auth",
]

MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_AUTH_TENANT = os.environ.get("MICROSOFT_AUTH_TENANT", "consumers")
MICROSOFT_REDIRECT_URI = os.environ.get("MICROSOFT_REDIRECT_URI", "")
```

## 3. Add URLs

In `config/urls.py`:

```python
path("auth/xbox/", include("xbox_auth.urls")),
```

## 4. Add .env values

For local development:

```env
MICROSOFT_CLIENT_ID=your-azure-app-client-id
MICROSOFT_CLIENT_SECRET=your-azure-app-client-secret
MICROSOFT_AUTH_TENANT=consumers
MICROSOFT_REDIRECT_URI=http://127.0.0.1:8000/auth/xbox/callback/
```

Your Microsoft app registration needs this redirect URI exactly:

```text
http://127.0.0.1:8000/auth/xbox/callback/
```

For production, add the HTTPS production callback too, for example:

```text
https://prostagma.example/auth/xbox/callback/
```

## 5. Migrate

```bash
python manage.py migrate
```

## 6. Test

```text
/auth/xbox/login/
/auth/xbox/profile/
```

The shared header now shows:

- Steam sign-in
- Xbox sign-in
- a signed-in user dropdown
- Connect Steam / Connect Xbox options
- Django Admin link for staff users
- Sign out

## Notes

The OAuth/OpenID Connect portion is the reliable sign-in identity. The Xbox profile metadata lookup is best-effort. If Microsoft/Xbox does not return XSTS display claims for the account/app, the user can still sign in with Microsoft, but gamertag/XUID may show as “Not returned.”
