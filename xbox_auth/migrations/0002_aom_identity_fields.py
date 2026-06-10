from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("xbox_auth", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="xboxprofile",
            name="aom_profile_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="xboxprofile",
            name="aom_alias",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="xboxprofile",
            name="aom_avatar_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="xboxprofile",
            name="aom_last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
