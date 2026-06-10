from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone

from .models import AgoraIdentity, ChatMessage


@admin.action(description="Mute selected identities for 30 minutes")
def mute_identities(modeladmin, request, queryset):
    until = timezone.now() + timedelta(minutes=30)
    updated = queryset.update(
        is_muted=True,
        muted_until=until,
        mute_reason="Muted from Django admin.",
    )
    modeladmin.message_user(request, f"Muted {updated} identity/identities for 30 minutes.", messages.SUCCESS)


@admin.action(description="Temp-ban selected identities for 30 minutes")
def temp_ban_identities(modeladmin, request, queryset):
    until = timezone.now() + timedelta(minutes=30)
    updated = queryset.update(
        is_banned=True,
        banned_until=until,
        ban_reason="Temporary ban from Django admin.",
    )
    modeladmin.message_user(request, f"Temp-banned {updated} identity/identities for 30 minutes.", messages.SUCCESS)


@admin.action(description="Clear posting restrictions")
def clear_restrictions(modeladmin, request, queryset):
    updated = queryset.update(
        is_muted=False,
        muted_until=None,
        mute_reason="",
        is_banned=False,
        banned_until=None,
        ban_reason="",
        severe_filter_hits=0,
        last_filter_hit_at=None,
    )
    modeladmin.message_user(request, f"Cleared restrictions for {updated} identity/identities.", messages.SUCCESS)


@admin.action(description="Clear display-name cooldown")
def clear_name_cooldown(modeladmin, request, queryset):
    updated = queryset.update(name_changed_at=None)
    modeladmin.message_user(request, f"Cleared display-name cooldown for {updated} identity/identities.", messages.SUCCESS)


@admin.register(AgoraIdentity)
class AgoraIdentityAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "last_seen_at",
        "is_muted",
        "muted_until",
        "is_banned",
        "banned_until",
        "severe_filter_hits",
    )
    search_fields = ("display_name", "browser_token_hash", "ip_hash")
    list_filter = ("is_muted", "is_banned", "created_at", "last_seen_at")
    readonly_fields = ("browser_token_hash", "ip_hash", "created_at", "last_seen_at")
    actions = [mute_identities, temp_ban_identities, clear_restrictions, clear_name_cooldown]


@admin.action(description="Soft-delete selected messages")
def soft_delete_messages(modeladmin, request, queryset):
    updated = queryset.update(
        is_deleted=True,
        deleted_at=timezone.now(),
        deleted_reason="Deleted from Django admin.",
    )
    modeladmin.message_user(request, f"Soft-deleted {updated} message(s).", messages.SUCCESS)


@admin.action(description="Restore selected messages")
def restore_messages(modeladmin, request, queryset):
    updated = queryset.update(
        is_deleted=False,
        deleted_at=None,
        deleted_reason="",
    )
    modeladmin.message_user(request, f"Restored {updated} message(s).", messages.SUCCESS)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "created_at",
        "was_filtered",
        "is_deleted",
        "user",
    )
    search_fields = ("display_name", "body_original", "body_clean", "ip_hash")
    list_filter = ("was_filtered", "is_deleted", "created_at")
    readonly_fields = ("identity", "user", "ip_hash", "created_at", "body_original", "body_clean", "filter_hits")
    actions = [soft_delete_messages, restore_messages]
