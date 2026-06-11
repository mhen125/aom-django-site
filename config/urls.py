from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from builds import views as build_views
from config import views as config_views

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Steam authentication routes.
    path("auth/steam/", include("steam_auth.urls")),
    
    # Xbox authentication routes.
    path("auth/xbox/", include("xbox_auth.urls")),

    # Crawlable metadata endpoints.
    path("robots.txt", config_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", config_views.sitemap_xml, name="sitemap_xml"),

    # Community/chat section.
    path("agora/", include("agora.urls")),


    # Lightweight launch info pages.
    path(
        "about/",
        TemplateView.as_view(template_name="builds/pages/about.html"),
        name="about",
    ),
    path(
        "faq/",
        TemplateView.as_view(template_name="builds/pages/faq.html"),
        name="faq",
    ),

    # Landing page, live lobby/API routes, and activity dashboard.
    path("", include("lobbies.urls")),

    # Canonical build-order section URL.
    path("build_orders/", include("builds.urls")),

    # Human-friendly alias: redirect, don't duplicate canonical pages.
    path(
        "build-orders/",
        RedirectView.as_view(pattern_name="builds:home", permanent=True),
        name="build_orders_alias",
    ),

    # Backward-compatible public build-order routes used by existing JS links.
    path("gods/<slug:god_slug>/", build_views.god_detail, name="legacy_god_detail"),
    path("builds/<slug:build_slug>/", build_views.build_detail, name="legacy_build_detail"),
    path("editor/", build_views.editor, name="legacy_editor"),
    path("data.json", build_views.data_js, name="legacy_build_data"),
    path("api/builds/save/", build_views.api_save_build, name="legacy_api_save_build"),
    path("api/builds/delete/", build_views.api_delete_build, name="legacy_api_delete_build"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
