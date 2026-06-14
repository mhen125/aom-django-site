import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from builds.models import BuildOrder, BuildOrderStep, MajorGod, Pantheon
from builds.views import strip_manifest_hash


class Command(BaseCommand):
    help = "Import AoM static data from static/data/seed_data.json into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="static/data/seed_data.json",
            help="Path to seed data JSON file.",
        )

        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing Pantheon, MajorGod, BuildOrder, and BuildOrderStep data before importing.",
        )

    def handle(self, *args, **options):
        seed_path = Path(settings.BASE_DIR) / options["path"]

        if not seed_path.exists():
            self.stderr.write(self.style.ERROR(f"Seed file not found: {seed_path}"))
            return

        with seed_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        pantheons_data = data.get("pantheons", [])
        build_orders_data = data.get("buildOrders", {})
        major_god_info = data.get("majorGodInfo", {})

        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            BuildOrderStep.objects.all().delete()
            BuildOrder.objects.all().delete()
            MajorGod.objects.all().delete()
            Pantheon.objects.all().delete()

        pantheon_count = 0
        god_count = 0
        build_count = 0
        step_count = 0

        for pantheon_data in pantheons_data:
            pantheon_slug = pantheon_data.get("id") or pantheon_data.get("slug") or slugify(pantheon_data.get("name", "pantheon"))

            pantheon, _created = Pantheon.objects.update_or_create(
                slug=pantheon_slug,
                defaults={
                    "name": pantheon_data.get("name", pantheon_slug.title()),
                    "description": pantheon_data.get("description") or pantheon_data.get("subtitle") or "",
                    "icon": self.clean_static_path(
                        pantheon_data.get("icon")
                        or pantheon_data.get("image")
                        or pantheon_data.get("iconPath")
                        or ""
                    ),
                    "background": self.clean_static_path(
                        pantheon_data.get("background")
                        or pantheon_data.get("backgroundImage")
                        or pantheon_data.get("bg")
                        or ""
                    ),
                },
            )

            pantheon_count += 1

            gods_data = (
                pantheon_data.get("gods")
                or pantheon_data.get("majorGods")
                or pantheon_data.get("major_gods")
                or []
            )

            for god_data in gods_data:
                god_slug = god_data.get("id") or god_data.get("slug") or slugify(god_data.get("name", "god"))
                info = major_god_info.get(god_slug, {})
                details = god_data.get("details") or {}

                bonuses = (
                    details.get("bonuses")
                    or info.get("bonuses")
                    or god_data.get("bonuses")
                    or []
                )

                if not isinstance(bonuses, list):
                    bonuses = []

                god, _created = MajorGod.objects.update_or_create(
                    slug=god_slug,
                    defaults={
                        "pantheon": pantheon,
                        "name": god_data.get("name") or info.get("name") or god_slug.title(),
                        "subtitle": god_data.get("subtitle") or "",
                        "title": details.get("title") or info.get("title") or "",
                        "focus": details.get("focus") or info.get("focus") or "",
                        "bonuses": bonuses,
                        "portrait": self.clean_static_path(
                            god_data.get("portrait")
                            or f"assets/images/gods/{god_slug}_portrait.png"
                        ),
                        "breakout_portrait": self.clean_static_path(
                            god_data.get("breakoutPortrait")
                            or god_data.get("breakout_portrait")
                            or f"assets/images/gods/{god_slug}_breakoutportrait.png"
                        ),
                        "hud_ring": self.clean_static_path(god_data.get("hudRing") or ""),
                    },
                )

                god_count += 1

                god_builds = build_orders_data.get(god_slug, [])

                for build_data in god_builds:
                    build_slug = build_data.get("id") or build_data.get("slug") or slugify(build_data.get("title", "build"))

                    build, _created = BuildOrder.objects.update_or_create(
                        major_god=god,
                        slug=build_slug,
                        defaults={
                            "title": build_data.get("title") or build_slug.replace("-", " ").title(),
                            "subtitle": build_data.get("detailSubtitle") or build_data.get("subtitle") or "",
                            "summary": build_data.get("summary") or "",
                            "meta": build_data.get("meta") or "",
                            "goal_label": build_data.get("goalLabel") or "Goal",
                            "goal_text": build_data.get("goalText") or build_data.get("meta") or "",
                            "goal_icon": self.clean_static_path(
                                build_data.get("goalIcon") or "assets/images/score_age_2.png"
                            ),
                            "portrait": self.clean_static_path(
                                build_data.get("portrait") or f"assets/images/gods/{god_slug}_portrait.png"
                            ),
                            "is_published": True,
                        },
                    )

                    build_count += 1

                    build.steps.all().delete()

                    steps = build_data.get("steps") or []

                    for index, step_data in enumerate(steps, start=1):
                        split = step_data.get("split") or {}

                        BuildOrderStep.objects.create(
                            build_order=build,
                            order=index,
                            type=step_data.get("type") or "",
                            label=step_data.get("label") or "",
                            time=step_data.get("time") or "",
                            food=step_data.get("food") or "",
                            wood=step_data.get("wood") or "",
                            gold=step_data.get("gold") or "",
                            favor=step_data.get("favor") or "",
                            pop=step_data.get("pop") or "",
                            action=step_data.get("action") or "",
                            note=step_data.get("note") or "",
                            split_food=self.safe_int(split.get("food")),
                            split_wood=self.safe_int(split.get("wood")),
                            split_gold=self.safe_int(split.get("gold")),
                            split_favor=self.safe_int(split.get("favor")),
                            split_pop=str(split.get("pop") or ""),
                        )

                        step_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {pantheon_count} pantheons, "
                f"{god_count} gods, "
                f"{build_count} build orders, "
                f"and {step_count} build steps."
            )
        )

    def clean_static_path(self, value):
        value = str(value or "").strip()

        if not value:
            return ""

        for prefix in ("/static/", "static/"):
            if value.startswith(prefix):
                return strip_manifest_hash(value.replace(prefix, "", 1))

        while value.startswith("../"):
            value = value[3:]

        if value.startswith("/"):
            value = value[1:]

        return strip_manifest_hash(value)

    def safe_int(self, value):
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0

        return max(number, 0)
