from django.conf import settings
from django.db import models
from django.utils import timezone


class AgoraIdentity(models.Model):
    """Browser-level identity used for guest moderation and Steam-linked chat state."""

    browser_token_hash = models.CharField(max_length=128, unique=True)
    ip_hash = models.CharField(max_length=128, blank=True)
    display_name = models.CharField(max_length=32, default="Villager")
    name_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    is_muted = models.BooleanField(default=False)
    muted_until = models.DateTimeField(null=True, blank=True)
    mute_reason = models.CharField(max_length=255, blank=True)

    is_banned = models.BooleanField(default=False)
    banned_until = models.DateTimeField(null=True, blank=True)
    ban_reason = models.CharField(max_length=255, blank=True)

    severe_filter_hits = models.PositiveIntegerField(default=0)
    last_filter_hit_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]
        verbose_name_plural = "Agora identities"

    def __str__(self):
        return f"{self.display_name} ({self.browser_token_hash[:10]})"

    def muted_active(self):
        if not self.is_muted:
            return False
        return self.muted_until is None or self.muted_until > timezone.now()

    def banned_active(self):
        if not self.is_banned:
            return False
        return self.banned_until is None or self.banned_until > timezone.now()

    def clear_expired_restrictions(self):
        now = timezone.now()
        changed = False

        if self.is_muted and self.muted_until and self.muted_until <= now:
            self.is_muted = False
            self.muted_until = None
            self.mute_reason = ""
            changed = True

        if self.is_banned and self.banned_until and self.banned_until <= now:
            self.is_banned = False
            self.banned_until = None
            self.ban_reason = ""
            changed = True

        if changed:
            self.save(update_fields=["is_muted", "muted_until", "mute_reason", "is_banned", "banned_until", "ban_reason"])

        return changed


class ChatMessage(models.Model):
    identity = models.ForeignKey(
        AgoraIdentity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agora_messages",
    )

    display_name = models.CharField(max_length=32)
    body_original = models.TextField(max_length=500)
    body_clean = models.TextField(max_length=700)
    was_filtered = models.BooleanField(default=False)
    filter_hits = models.JSONField(default=list, blank=True)

    ip_hash = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["ip_hash", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.display_name}: {self.body_clean[:60]}"
