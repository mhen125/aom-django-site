# Add these to config/settings.py

INSTALLED_APPS += [
    "xbox_auth",
]

MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_AUTH_TENANT = os.environ.get("MICROSOFT_AUTH_TENANT", "consumers")
MICROSOFT_REDIRECT_URI = os.environ.get("MICROSOFT_REDIRECT_URI", "")
