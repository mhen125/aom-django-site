from django.core.management.base import BaseCommand

from builds.models import MajorGod, Pantheon
from builds.views import GOD_DETAILS, GOD_META, PANTHEON_META, normalize_slug


class Command(BaseCommand):
    help = (
        "Seed or update MajorGod focus/bonus details from the Prostagma fallback data. "
        "By default this only fills empty fields; use --overwrite to replace existing values."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing title, focus, and bonuses values on matching gods.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        overwrite = options["overwrite"]
        dry_run = options["dry_run"]

        created_pantheons = 0
        created_gods = 0
        updated_gods = 0
        skipped_gods = 0

        for raw_god_slug, details in GOD_DETAILS.items():
            god_slug = normalize_slug(raw_god_slug)
            god_meta = GOD_META.get(god_slug)

            if not god_meta:
                self.stdout.write(
                    self.style.WARNING(f"Skipping {raw_god_slug}: no GOD_META entry found.")
                )
                skipped_gods += 1
                continue

            pantheon_slug = normalize_slug(god_meta.get("pantheon"))
            pantheon_meta = PANTHEON_META.get(pantheon_slug, {})

            pantheon_defaults = {
                "name": pantheon_meta.get("name") or pantheon_slug.replace("-", " ").title(),
                "description": pantheon_meta.get("description", ""),
                "icon": pantheon_meta.get("icon", ""),
                "background": pantheon_meta.get("background", ""),
            }

            pantheon = Pantheon.objects.filter(slug=pantheon_slug).first()
            if not pantheon:
                created_pantheons += 1
                if not dry_run:
                    pantheon = Pantheon.objects.create(slug=pantheon_slug, **pantheon_defaults)
                self.stdout.write(self.style.SUCCESS(f"Create pantheon: {pantheon_slug}"))
            elif overwrite:
                changed = False
                for field, value in pantheon_defaults.items():
                    if value and getattr(pantheon, field) != value:
                        setattr(pantheon, field, value)
                        changed = True
                if changed and not dry_run:
                    pantheon.save(update_fields=list(pantheon_defaults.keys()))

            god_defaults = {
                "pantheon": pantheon,
                "name": god_meta.get("name") or god_slug.replace("-", " ").title(),
                "subtitle": god_meta.get("subtitle", ""),
                "title": god_meta.get("title") or god_meta.get("name") or god_slug.replace("-", " ").title(),
                "focus": details.get("focus", ""),
                "bonuses": details.get("bonuses", []),
                "portrait": f"assets/images/gods/{god_slug}_portrait.png",
                "breakout_portrait": f"assets/images/gods/{god_slug}_breakoutportrait.png",
            }

            god = MajorGod.objects.filter(slug=god_slug).first()

            if not god:
                created_gods += 1
                if not dry_run:
                    MajorGod.objects.create(slug=god_slug, **god_defaults)
                self.stdout.write(self.style.SUCCESS(f"Create god details: {god_slug}"))
                continue

            fields_to_update = []

            # Keep pantheon/name/subtitle art paths healthy without overwriting hand-edited values
            # unless --overwrite is explicitly requested.
            soft_fields = [
                "name",
                "subtitle",
                "title",
                "portrait",
                "breakout_portrait",
            ]

            for field in soft_fields:
                new_value = god_defaults[field]
                current_value = getattr(god, field)
                if overwrite or not current_value:
                    if new_value and current_value != new_value:
                        setattr(god, field, new_value)
                        fields_to_update.append(field)

            if god.pantheon_id != getattr(pantheon, "id", None):
                if overwrite or not god.pantheon_id:
                    god.pantheon = pantheon
                    fields_to_update.append("pantheon")

            current_focus = (god.focus or "").strip()
            current_bonuses = god.bonuses or []
            new_focus = (details.get("focus") or "").strip()
            new_bonuses = details.get("bonuses") or []

            if overwrite or not current_focus:
                if new_focus and current_focus != new_focus:
                    god.focus = new_focus
                    fields_to_update.append("focus")

            if overwrite or not current_bonuses:
                if new_bonuses and current_bonuses != new_bonuses:
                    god.bonuses = new_bonuses
                    fields_to_update.append("bonuses")

            if fields_to_update:
                updated_gods += 1
                unique_fields = sorted(set(fields_to_update))
                if not dry_run:
                    god.save(update_fields=unique_fields)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Update god details: {god_slug} ({', '.join(unique_fields)})"
                    )
                )
            else:
                skipped_gods += 1
                self.stdout.write(f"No changes: {god_slug}")

        summary = (
            f"Done. Pantheons created: {created_pantheons}. "
            f"Gods created: {created_gods}. Gods updated: {updated_gods}. "
            f"Gods skipped/no changes: {skipped_gods}."
        )

        if dry_run:
            summary = f"Dry run complete. {summary}"

        self.stdout.write(self.style.SUCCESS(summary))
