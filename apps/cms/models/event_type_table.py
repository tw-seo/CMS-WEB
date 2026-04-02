from django.db import models
from django.contrib.postgres.fields import ArrayField  # ← 배열(varchar[])

class EventTypeTable(models.Model):
    event_type_key    = models.CharField(max_length=50, primary_key=True)
    event_type_name   = models.CharField(max_length=10)
    object_to_detects = ArrayField(
        base_field=models.CharField(max_length=10),
        default=list,
        blank=True,
    )

    class Meta:
        db_table = "EVENT_TYPE_TABLE"
        indexes = [
            models.Index(fields=["event_type_name"]),
        ]