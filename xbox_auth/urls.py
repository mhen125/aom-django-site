from django.urls import path

from . import views

app_name = "xbox_auth"

urlpatterns = [
    path("login/", views.xbox_login, name="login"),
    path("callback/", views.xbox_callback, name="callback"),
    path("logout/", views.xbox_logout, name="logout"),
    path("profile/", views.xbox_profile, name="profile"),
]
