from django.db import models

class BuzzerInterlockTable(models.Model):
    interlock_info_key = models.CharField(max_length=50, primary_key=True)
    interlock_name     = models.CharField(max_length=50, null=True, blank=True)
    buzzer_info_key    = models.CharField(max_length=50)     # 필요시 BuzzerInfoTable FK로 교체 가능
    buzzer_name        = models.CharField(max_length=50, null=True, blank=True)
    camera_info_key    = models.CharField(max_length=50)     # 필요시 CameraInfo FK로 교체 가능
    camera_name        = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "BUZZER_INTERLOCK_TABLE"
        indexes = [
            models.Index(fields=["buzzer_info_key"]),
            models.Index(fields=["camera_info_key"]),
        ]
