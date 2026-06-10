from django.core.management.base import BaseCommand

from lobbies.leaderboard import resolve_worldsedge_identity_sync
from steam_auth.models import SteamProfile

try:
    from xbox_auth.models import XboxProfile
except Exception:  # pragma: no cover - xbox_auth may not be installed yet
    XboxProfile = None


class Command(BaseCommand):
    help = "Resolve linked Steam/Xbox accounts to AoM profile IDs and aliases."

    def add_arguments(self, parser):
        parser.add_argument("--steam", action="store_true", help="Sync Steam profiles only.")
        parser.add_argument("--xbox", action="store_true", help="Sync Xbox profiles only.")
        parser.add_argument("--force", action="store_true", help="Re-sync profiles that already have an AoM profile ID.")

    def handle(self, *args, **options):
        sync_steam = options["steam"] or not options["xbox"]
        sync_xbox = options["xbox"] or not options["steam"]
        force = options["force"]

        if sync_steam:
            self.sync_steam(force=force)

        if sync_xbox:
            self.sync_xbox(force=force)

    def sync_steam(self, *, force):
        queryset = SteamProfile.objects.select_related("user").all()
        if not force:
            queryset = queryset.filter(aom_profile_id__isnull=True)

        for profile in queryset:
            identity = resolve_worldsedge_identity_sync(
                platform="steam",
                platform_id=profile.steam_id,
                fallback_name=profile.persona_name or profile.user.first_name or "unknown user",
            )

            if identity.get("ok"):
                profile.apply_aom_identity(identity)
                profile.save()
                self.stdout.write(self.style.SUCCESS(
                    f"Steam {profile.steam_id} -> {profile.aom_profile_id} {profile.aom_alias or ''}".strip()
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Steam {profile.steam_id} could not be resolved."
                ))

    def sync_xbox(self, *, force):
        if XboxProfile is None:
            self.stdout.write(self.style.WARNING("xbox_auth is not available."))
            return

        queryset = XboxProfile.objects.select_related("user").exclude(xuid="")
        if not force:
            queryset = queryset.filter(aom_profile_id__isnull=True)

        for profile in queryset:
            identity = resolve_worldsedge_identity_sync(
                platform="xbox",
                platform_id=profile.xuid,
                fallback_name=profile.gamertag or profile.microsoft_name or profile.user.first_name or "unknown user",
            )

            if identity.get("ok"):
                profile.apply_aom_identity(identity)
                profile.save()
                self.stdout.write(self.style.SUCCESS(
                    f"Xbox {profile.xuid} -> {profile.aom_profile_id} {profile.aom_alias or ''}".strip()
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Xbox {profile.xuid} could not be resolved."
                ))
