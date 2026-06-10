# Generated manually for Prostagma Steam authentication.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SteamProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("steam_id", models.CharField(db_index=True, max_length=32, unique=True)),
                ("persona_name", models.CharField(blank=True, max_length=128)),
                ("profile_url", models.URLField(blank=True)),
                ("avatar", models.URLField(blank=True)),
                ("avatar_medium", models.URLField(blank=True)),
                ("avatar_full", models.URLField(blank=True)),
                ("country_code", models.CharField(blank=True, max_length=8)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="steam_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["persona_name", "steam_id"],
            },
        ),
    ]
