# Generated for Prostagma? Xbox/Microsoft sign-in integration.

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
            name="XboxProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("microsoft_sub", models.CharField(db_index=True, max_length=128, unique=True)),
                ("microsoft_email", models.EmailField(blank=True, max_length=254)),
                ("microsoft_name", models.CharField(blank=True, max_length=160)),
                ("xuid", models.CharField(blank=True, db_index=True, max_length=32)),
                ("user_hash", models.CharField(blank=True, max_length=128)),
                ("gamertag", models.CharField(blank=True, max_length=128)),
                ("gamerpic_url", models.URLField(blank=True)),
                ("access_token_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="xbox_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["gamertag", "microsoft_name", "microsoft_sub"],
            },
        ),
    ]
