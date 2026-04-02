from django.db import migrations


EVENT_TYPES = [
    ("E2024-11-19-001", "침입", ["D001", "D002", "D004"]),
    ("E2024-11-19-002", "배회", ["D001", "D002", "D004"]),
    ("E2024-11-19-003", "화재", ["D005", "D006", "D007"]),
    ("E2025-01-20-001", "넘어짐", ["D001", "D002", "D004"]),
    ("E2025-07-29-001", "부딪힘", ["D001", "D002", "D004"]),
    ("E2025-07-29-002", "끼임", ["D001", "D002", "D004"]),
]


def seed_event_types(apps, schema_editor):
    EventTypeTable = apps.get_model("cms", "EventTypeTable")
    for key, name, objects in EVENT_TYPES:
        EventTypeTable.objects.update_or_create(
            event_type_key=key,
            defaults={
                "event_type_name": name,
                "object_to_detects": objects,
            },
        )


def unseed_event_types(apps, schema_editor):
    EventTypeTable = apps.get_model("cms", "EventTypeTable")
    EventTypeTable.objects.filter(event_type_key__in=[key for key, *_ in EVENT_TYPES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0003_eventinfotable_event_shadow_roi"),
    ]

    operations = [
        migrations.RunPython(seed_event_types, unseed_event_types),
    ]
