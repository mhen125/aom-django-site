from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image


class Command(BaseCommand):
    help = "Generate production WebP variants for large static art while preserving source PNGs."

    TARGETS = [
        {
            "label": "god card portraits",
            "glob": "assets/images/gods/*_portrait.png",
            "suffix": ".card.webp",
            "max_size": (640, 820),
            "quality": 82,
        },
        {
            "label": "god hero portraits",
            "glob": "assets/images/gods/*_breakoutportrait.png",
            "suffix": ".hero.webp",
            "max_size": (960, 1200),
            "quality": 84,
        },
        {
            "label": "pantheon backgrounds",
            "glob": "assets/images/backgrounds/*.png",
            "suffix": ".webp",
            "max_size": (1600, 900),
            "quality": 78,
        },
        {
            "label": "site background",
            "glob": "assets/images/Background.png",
            "suffix": ".webp",
            "max_size": (1920, 1080),
            "quality": 78,
        },
        {
            "label": "header brand art",
            "glob": "assets/images/ui/prostagma_arkantos.png",
            "suffix": ".brand.webp",
            "max_size": (320, 320),
            "quality": 82,
        },
        {
            "label": "pantheon emblems",
            "glob": "assets/images/pantheons/*.png",
            "suffix": ".emblem.webp",
            "max_size": (420, 488),
            "quality": 82,
        },
        {
            "label": "lobby frame fills",
            "glob": "assets/images/*_Frame_Fill.png",
            "suffix": ".webp",
            "max_size": (1024, 1024),
            "quality": 78,
        },
        {
            "label": "small ornate buttons",
            "glob": "assets/images/BtnOrnate_Sml_*.png",
            "suffix": ".webp",
            "max_size": (512, 160),
            "quality": 82,
        },
        {
            "label": "selection frame",
            "glob": "assets/images/misc/Party_God_Icon_Frame_Temp.png",
            "suffix": ".webp",
            "max_size": (512, 512),
            "quality": 82,
        },
        {
            "label": "large ornate buttons",
            "glob": "assets/images/ui/BtnOrnate_Large_*.png",
            "suffix": ".webp",
            "max_size": (640, 220),
            "quality": 82,
        },
        {
            "label": "platform icons",
            "glob": "assets/images/auth/*_icon.png",
            "suffix": ".webp",
            "max_size": (128, 128),
            "quality": 82,
        },
        {
            "label": "shortcode icons",
            "glob": "assets/images/*_icon.png",
            "suffix": ".webp",
            "max_size": (128, 128),
            "quality": 82,
        },
        {
            "label": "shortcode economic building icons",
            "glob": "assets/images/eco_builds/*_icon.png",
            "suffix": ".webp",
            "max_size": (128, 128),
            "quality": 82,
        },
        {
            "label": "shortcode hero icons",
            "glob": "assets/images/heroes/*_icon.png",
            "suffix": ".webp",
            "max_size": (128, 128),
            "quality": 82,
        },
        {
            "label": "shortcode hunt icon",
            "glob": "assets/images/hunt.png",
            "suffix": ".webp",
            "max_size": (128, 128),
            "quality": 82,
        },
        {
            "label": "top logo art",
            "glob": "assets/images/Top_Logo.png",
            "suffix": ".webp",
            "max_size": (778, 128),
            "quality": 84,
        },
        {
            "label": "god HUD rings",
            "glob": "assets/images/pantheons/major_gods/hud/*.png",
            "suffix": ".webp",
            "max_size": (302, 105),
            "quality": 82,
        },
        {
            "label": "info footer decorations",
            "glob": "assets/images/easter_eggs/master_shake*.png",
            "suffix": ".webp",
            "max_size": (420, 420),
            "quality": 82,
        },
        {
            "label": "map thumbnails",
            "glob": "map-icons/*.png",
            "suffix": ".webp",
            "max_size": (384, 384),
            "quality": 78,
        },
        {
            "label": "map previews",
            "glob": "map-icons/previews/*.png",
            "suffix": ".webp",
            "max_size": (720, 405),
            "quality": 76,
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report planned outputs without writing files.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate variants even when the output is newer than the source.",
        )

    def handle(self, *args, **options):
        static_root = Path(settings.BASE_DIR) / "static"
        output_root = static_root / "assets" / "optimized"
        dry_run = options["dry_run"]
        force = options["force"]

        created = 0
        skipped = 0
        bytes_before = 0
        bytes_after = 0

        for target in self.TARGETS:
            sources = sorted(static_root.glob(target["glob"]))

            for source_path in sources:
                if not source_path.is_file():
                    continue

                relative_source = source_path.relative_to(static_root)
                relative_parent = relative_source.parent
                output_dir = self.get_output_dir(output_root, relative_parent)
                output_path = output_dir / f"{source_path.stem}{target['suffix']}"

                if (
                    output_path.exists()
                    and not force
                    and output_path.stat().st_mtime >= source_path.stat().st_mtime
                ):
                    skipped += 1
                    bytes_before += source_path.stat().st_size
                    bytes_after += output_path.stat().st_size
                    continue

                if dry_run:
                    self.stdout.write(f"{target['label']}: {relative_source} -> {output_path.relative_to(static_root)}")
                    continue

                output_dir.mkdir(parents=True, exist_ok=True)

                with Image.open(source_path) as image:
                    optimized = image.copy()
                    optimized.thumbnail(target["max_size"], Image.Resampling.LANCZOS)

                    if optimized.mode not in {"RGB", "RGBA"}:
                        optimized = optimized.convert("RGBA" if "A" in optimized.getbands() else "RGB")

                    optimized.save(
                        output_path,
                        "WEBP",
                        quality=target["quality"],
                        method=6,
                    )

                created += 1
                bytes_before += source_path.stat().st_size
                bytes_after += output_path.stat().st_size

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only; no files written."))
            return

        saved = bytes_before - bytes_after
        ratio = (saved / bytes_before * 100) if bytes_before else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {created} optimized assets, skipped {skipped}; "
                f"served payload savings: {self.format_bytes(saved)} ({ratio:.1f}%)."
            )
        )

    @staticmethod
    def get_output_dir(output_root, relative_parent):
        if relative_parent == Path("assets") or relative_parent.is_relative_to("assets"):
            return output_root / relative_parent.relative_to("assets")

        return output_root / relative_parent

    @staticmethod
    def format_bytes(value):
        size = float(max(0, value))
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}"
            size /= 1024
