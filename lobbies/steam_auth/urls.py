from django.urls import path

from . import views

app_name = "steam_auth"

urlpatterns = [
    path("login/", views.steam_login, name="login"),
    path("callback/", views.steam_callback, name="callback"),
    path("logout/", views.steam_logout, name="logout"),
    path("profile/", views.steam_profile, name="profile"),
]
