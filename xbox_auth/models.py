from django.conf import settings
from django.db import models
from django.utils import timezone


class XboxProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="xbox_profile",
        on_delete=models.CASCADE,
    )

    microsoft_sub = models.CharField(max_length=128, unique=True, db_index=True)
    microsoft_email = models.EmailField(blank=True)
    microsoft_name = models.CharField(max_length=160, blank=True)

    xuid = models.CharField(max_length=32, blank=True, db_index=True)
    user_hash = models.CharField(max_length=128, blank=True)
    gamertag = models.CharField(max_length=128, blank=True)
    gamerpic_url = models.URLField(blank=True)

    aom_profile_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    aom_alias = models.CharField(max_length=128, blank=True)
    aom_avatar_url = models.URLField(blank=True)
    aom_last_synced_at = models.DateTimeField(null=True, blank=True)

    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["gamertag", "microsoft_name", "microsoft_sub"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.aom_alias or self.gamertag or self.microsoft_name or self.microsoft_email or "Xbox Player"

    @property
    def avatar_url(self):
        return self.aom_avatar_url or self.gamerpic_url

    def apply_microsoft_claims(self, claims):
        self.microsoft_name = claims.get("name") or self.microsoft_name
        self.microsoft_email = (
            claims.get("preferred_username")
            or claims.get("email")
            or self.microsoft_email
        )

    def apply_xbox_claims(self, xbox_claims):
        if not xbox_claims:
            return

        self.xuid = str(xbox_claims.get("xuid") or self.xuid or "")
        self.user_hash = str(xbox_claims.get("user_hash") or self.user_hash or "")
        self.gamertag = str(xbox_claims.get("gamertag") or self.gamertag or "")
        self.gamerpic_url = str(xbox_claims.get("gamerpic_url") or self.gamerpic_url or "")
        self.last_synced_at = timezone.now()


    def apply_aom_identity(self, identity):
        if not identity:
            return

        profile_id = identity.get("profile_id")
        if profile_id is not None:
            self.aom_profile_id = int(profile_id)

        self.aom_alias = identity.get("alias") or self.aom_alias
        self.aom_avatar_url = identity.get("avatar_url") or self.aom_avatar_url
        self.aom_last_synced_at = timezone.now()
