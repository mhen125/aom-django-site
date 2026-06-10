from django.contrib import admin

from .models import SteamProfile


@admin.register(SteamProfile)
class SteamProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "steam_id",
        "user",
        "country_code",
        "last_synced_at",
        "created_at",
    )
    search_fields = ("steam_id", "persona_name", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at", "last_synced_at")
