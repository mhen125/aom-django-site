from django.conf import settings
from django.db import models
from django.utils import timezone


class SteamProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="steam_profile",
        on_delete=models.CASCADE,
    )
    steam_id = models.CharField(max_length=32, unique=True, db_index=True)
    persona_name = models.CharField(max_length=128, blank=True)
    profile_url = models.URLField(blank=True)
    avatar = models.URLField(blank=True)
    avatar_medium = models.URLField(blank=True)
    avatar_full = models.URLField(blank=True)
    country_code = models.CharField(max_length=8, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["persona_name", "steam_id"]

    def __str__(self):
        return self.persona_name or self.steam_id

    @property
    def display_name(self):
        return self.persona_name or f"Steam {self.steam_id}"

    def apply_player_summary(self, player_summary):
        if not player_summary:
            return

        self.persona_name = player_summary.get("personaname") or self.persona_name
        self.profile_url = player_summary.get("profileurl") or self.profile_url
        self.avatar = player_summary.get("avatar") or self.avatar
        self.avatar_medium = player_summary.get("avatarmedium") or self.avatar_medium
        self.avatar_full = player_summary.get("avatarfull") or self.avatar_full
        self.country_code = player_summary.get("loccountrycode") or self.country_code
        self.last_synced_at = timezone.now()
