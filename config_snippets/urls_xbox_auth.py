# Add this to config/urls.py

from django.urls import include, path

urlpatterns += [
    path("auth/xbox/", include("xbox_auth.urls")),
]
