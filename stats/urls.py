from django.urls import path

from lobbies import views as lobby_views
from . import views

app_name = "stats"

urlpatterns = [
    path("", views.stats_home, name="home"),
    path("me/", lobby_views.my_player_stats_redirect, name="my_player_stats"),
    path("player/", views.player_stats_home, name="player_stats_home"),
    path("players/<int:profile_id>/", views.player_profile, name="player_profile"),
    path("meta/", views.meta_dashboard, name="meta_dashboard"),
    path("replays/", views.replay_discovery, name="replay_discovery"),
]
