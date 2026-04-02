from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0004_seed_event_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="camerainfo",
            name="is_thermal",
            field=models.BooleanField(default=False),
        ),
    ]
