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
                output_dir = output_root / relative_parent.relative_to("assets")
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
    def format_bytes(value):
        size = float(max(0, value))
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}"
            size /= 1024
