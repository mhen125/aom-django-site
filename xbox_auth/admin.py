from django.contrib import admin

from .models import XboxProfile


@admin.register(XboxProfile)
class XboxProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "user",
        "xuid",
        "microsoft_email",
        "last_synced_at",
        "updated_at",
    )
    search_fields = (
        "user__username",
        "microsoft_sub",
        "microsoft_email",
        "microsoft_name",
        "xuid",
        "gamertag",
    )
    readonly_fields = ("created_at", "updated_at", "last_synced_at")
