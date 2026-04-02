from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0010_viewer_manage_assignment_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventoccurtable",
            name="img_path",
            field=models.TextField(blank=True, null=True),
        ),
    ]

