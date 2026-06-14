from django.urls import path

from . import views

app_name = "lobbies"

urlpatterns = [
    path("", views.landing_home, name="landing_home"),
    path("activity/", views.live_activity_home, name="live_activity_home"),
    path("lobbies/", views.lobby_browser, name="browser"),
    path("leaderboards/", views.leaderboard_home, name="leaderboard_home"),
    path("leaderboards/me/", views.my_player_stats_redirect, name="my_player_stats"),
    path("leaderboards/player/", views.player_stats_home, name="player_stats_home"),

    path("api/lobbies/", views.api_lobbies, name="api_lobbies"),
    path("api/activity/live", views.api_live_activity, name="api_live_activity"),
    path("api/home/news/", views.api_home_news, name="api_home_news"),
    path("api/active-matches/", views.api_active_matches, name="api_active_matches"),
    path(
        "api/active-custom-matches/",
        views.api_active_custom_matches,
        name="api_active_custom_matches",
    ),

    path("api/player/rating", views.api_player_rating, name="api_player_rating"),
    path("api/leaderboards/search", views.api_leaderboard_search, name="api_leaderboard_search"),
    path("api/leaderboards/metadata", views.api_leaderboard_metadata, name="api_leaderboard_metadata"),
    path("api/player/summary", views.api_player_summary, name="api_player_summary"),
    path("api/player/god-stats", views.api_player_god_stats, name="api_player_god_stats"),
]
