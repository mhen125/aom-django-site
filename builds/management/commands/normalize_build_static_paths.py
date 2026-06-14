from django.core.management.base import BaseCommand

from builds.models import BuildOrder, MajorGod, Pantheon
from builds.views import strip_manifest_hash


class Command(BaseCommand):
    help = "Normalize stored build-order static asset paths by removing manifest hashes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing them to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        summary = {
            "pantheons": self.normalize_pantheons(dry_run=dry_run),
            "major_gods": self.normalize_major_gods(dry_run=dry_run),
            "build_orders": self.normalize_build_orders(dry_run=dry_run),
        }

        self.stdout.write(
            self.style.SUCCESS(
                "Normalized static asset paths"
                f" | dry_run={dry_run}"
                f" | pantheons={summary['pantheons']}"
                f" | major_gods={summary['major_gods']}"
                f" | build_orders={summary['build_orders']}"
            )
        )

    def normalize_pantheons(self, *, dry_run):
        changed = 0

        for pantheon in Pantheon.objects.all():
            updates = {}

            normalized_icon = strip_manifest_hash(pantheon.icon)
            normalized_background = strip_manifest_hash(pantheon.background)

            if normalized_icon != pantheon.icon:
                updates["icon"] = normalized_icon

            if normalized_background != pantheon.background:
                updates["background"] = normalized_background

            if updates:
                changed += 1
                if not dry_run:
                    for field, value in updates.items():
                        setattr(pantheon, field, value)
                    pantheon.save(update_fields=list(updates.keys()))

        return changed

    def normalize_major_gods(self, *, dry_run):
        changed = 0

        for god in MajorGod.objects.all():
            updates = {}

            normalized_portrait = strip_manifest_hash(god.portrait)
            normalized_breakout = strip_manifest_hash(god.breakout_portrait)
            normalized_hud_ring = strip_manifest_hash(god.hud_ring)

            if normalized_portrait != god.portrait:
                updates["portrait"] = normalized_portrait

            if normalized_breakout != god.breakout_portrait:
                updates["breakout_portrait"] = normalized_breakout

            if normalized_hud_ring != god.hud_ring:
                updates["hud_ring"] = normalized_hud_ring

            if updates:
                changed += 1
                if not dry_run:
                    for field, value in updates.items():
                        setattr(god, field, value)
                    god.save(update_fields=list(updates.keys()))

        return changed

    def normalize_build_orders(self, *, dry_run):
        changed = 0

        for build in BuildOrder.objects.all():
            updates = {}

            normalized_goal_icon = strip_manifest_hash(build.goal_icon)
            normalized_portrait = strip_manifest_hash(build.portrait)

            if normalized_goal_icon != build.goal_icon:
                updates["goal_icon"] = normalized_goal_icon

            if normalized_portrait != build.portrait:
                updates["portrait"] = normalized_portrait

            if updates:
                changed += 1
                if not dry_run:
                    for field, value in updates.items():
                        setattr(build, field, value)
                    build.save(update_fields=list(updates.keys()))

        return changed
