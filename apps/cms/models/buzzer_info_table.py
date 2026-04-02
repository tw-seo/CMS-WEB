# apps/cms/models/buzzer_info_table.py
from django.db import models

class BuzzerInfoTable(models.Model):
    buzzer_info_key = models.CharField(max_length=100, primary_key=True)
    buzzer_name     = models.CharField(max_length=100, null=True, blank=True)
    buzzer_location = models.CharField(max_length=100, null=True, blank=True)
    buzzer_time     = models.IntegerField(null=True, blank=True)
    buzzer_broker   = models.CharField(max_length=100, null=True, blank=True)
    buzzer_topic    = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "BUZZER_INFO_TABLE"
        indexes = [
            models.Index(fields=["buzzer_name"]),
            models.Index(fields=["buzzer_location"]),
        ]
