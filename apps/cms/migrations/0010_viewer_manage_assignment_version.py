from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0009_smsinfotable_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="viewermanage",
            name="assignment_version",
            field=models.BigIntegerField(db_column="assignment_version", default=1),
        ),
    ]
