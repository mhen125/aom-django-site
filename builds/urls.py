from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "builds"

urlpatterns = [
    path("api/builds/save/", views.api_save_build, name="api_save_build"),
    path("api/builds/delete/", views.api_delete_build, name="api_delete_build"),
    path("data.json", views.data_js, name="data_json"),
    path("", views.home, name="home"),

    # Keep /build_orders/ as the canonical build-order hub.
    # Detail/editor URLs stay at their shorter public paths to avoid duplicate pages.
    path("gods/<slug:god_slug>/", RedirectView.as_view(url="/gods/%(god_slug)s/", permanent=True), name="god_detail_redirect"),
    path("builds/<slug:build_slug>/", RedirectView.as_view(url="/builds/%(build_slug)s/", permanent=True), name="build_detail_redirect"),
    path("editor/", RedirectView.as_view(url="/editor/", permanent=True), name="editor_redirect"),
]
