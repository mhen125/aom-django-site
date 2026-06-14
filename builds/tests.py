import json
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from builds.models import BuildOrder, MajorGod, Pantheon
from builds.views import clean_static_path, safe_static_url, static_relative_path, strip_manifest_hash


class BuildAssetPathNormalizationTests(TestCase):
    def test_strip_manifest_hash_removes_hashed_segment_before_extension(self):
        self.assertEqual(
            strip_manifest_hash("assets/images/gods/hades_portrait.1234567890ab.png"),
            "assets/images/gods/hades_portrait.png",
        )
        self.assertEqual(
            strip_manifest_hash("assets/optimized/images/pantheons/UI_god_pantheon_Aztec.emblem.54e3f7cb3c08.webp"),
            "assets/optimized/images/pantheons/UI_god_pantheon_Aztec.emblem.webp",
        )

    def test_clean_static_path_normalizes_hashed_static_url_to_source_path(self):
        self.assertEqual(
            clean_static_path("/static/assets/images/gods/hades_portrait.1234567890ab.png"),
            "assets/images/gods/hades_portrait.png",
        )

    def test_static_relative_path_normalizes_hashed_relative_path(self):
        self.assertEqual(
            static_relative_path("assets/images/score_age_2.abcdef123456.png"),
            "assets/images/score_age_2.png",
        )

    def test_safe_static_url_returns_empty_string_for_missing_manifest_entry(self):
        with patch("builds.views.static", side_effect=ValueError("Missing staticfiles manifest entry")):
            self.assertEqual(safe_static_url("assets/images/missing.png"), "")


class BuildSaveEndpointTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="builder",
            password="test-pass-123",
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_save_build_strips_manifest_hashes_before_persisting(self):
        response = self.client.post(
            reverse("builds:api_save_build"),
            data=json.dumps(
                {
                    "id": "hades-archer-test",
                    "title": "Hades Archer Test",
                    "sourceGodId": "hades",
                    "portrait": "/static/assets/images/gods/hades_portrait.1234567890ab.png",
                    "goalIcon": "/static/assets/images/score_age_2.abcdef123456.png",
                    "steps": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        build = BuildOrder.objects.get(slug="hades-archer-test", major_god__slug="hades")
        self.assertEqual(build.portrait, "assets/images/gods/hades_portrait.png")
        self.assertEqual(build.goal_icon, "assets/images/score_age_2.png")


class NormalizeBuildStaticPathsCommandTests(TestCase):
    def test_command_normalizes_existing_rows(self):
        pantheon = Pantheon.objects.create(
            name="Greek",
            slug="greek",
            icon="assets/images/pantheons/UI_god_pantheon_Greek.c184eb821a4c.png",
            background="assets/images/backgrounds/background_greek.ab8118f02f0a.png",
        )
        god = MajorGod.objects.create(
            pantheon=pantheon,
            name="Hades",
            slug="hades",
            portrait="assets/images/gods/hades_portrait.2dda9dab00d1.png",
            breakout_portrait="assets/images/gods/hades_breakoutportrait.1234567890ab.png",
            hud_ring="assets/images/pantheons/major_gods/hud/Hud_Ring_Grk_Hades.abcdef123456.png",
        )
        build = BuildOrder.objects.create(
            major_god=god,
            title="Hades Test",
            slug="hades-test",
            goal_icon="assets/images/score_age_2.43c45585cf28.png",
            portrait="assets/images/gods/hades_portrait.2dda9dab00d1.png",
        )

        call_command("normalize_build_static_paths")

        pantheon.refresh_from_db()
        god.refresh_from_db()
        build.refresh_from_db()

        self.assertEqual(pantheon.icon, "assets/images/pantheons/UI_god_pantheon_Greek.png")
        self.assertEqual(pantheon.background, "assets/images/backgrounds/background_greek.png")
        self.assertEqual(god.portrait, "assets/images/gods/hades_portrait.png")
        self.assertEqual(god.breakout_portrait, "assets/images/gods/hades_breakoutportrait.png")
        self.assertEqual(god.hud_ring, "assets/images/pantheons/major_gods/hud/Hud_Ring_Grk_Hades.png")
        self.assertEqual(build.goal_icon, "assets/images/score_age_2.png")
        self.assertEqual(build.portrait, "assets/images/gods/hades_portrait.png")
