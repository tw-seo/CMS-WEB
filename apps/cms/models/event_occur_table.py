# apps/cms/models/event_occur_table.py
from django.db import models
# ⚠️ Postgres의 point[] 타입을 Django가 직접 지원하진 않음.
# 실무에선 (x,y) 문자열의 배열로 저장하거나, JSONField에 [[x,y], ...] 저장을 권장.
# 아래는 문자열 "(x,y)" 형태의 배열로 매핑하는 예시.
from django.contrib.postgres.fields import ArrayField

class EventOccurTable(models.Model):
    occur_no           = models.AutoField(primary_key=True)  # serial 대응
    event_occur_time   = models.DateTimeField()              # timestamp without time zone
    event_register_key = models.CharField(max_length=50, null=True, blank=True)
    camera_info_key    = models.CharField(max_length=50)     # 필요시 CameraInfo FK로 교체 가능
    event_type_key     = models.CharField(max_length=50)     # 필요시 EventTypeTable FK로 교체 가능
    object_class       = models.CharField(max_length=50, null=True, blank=True)
    img_path           = models.TextField(null=True, blank=True)

    # point[] 대체: "(x,y)" 문자열 배열로 저장 (예: ["(12.3,45.6)", "(7.8,9.0)"])
    event_occur_point  = ArrayField(
        base_field=models.CharField(max_length=64),  # "(x,y)" 담기
        null=True, blank=True
    )

    class Meta:
        db_table = "EVENT_OCCUR_TABLE"
        indexes = [
            models.Index(fields=["event_occur_time"]),
            models.Index(fields=["camera_info_key"]),
            models.Index(fields=["event_type_key"]),
        ]
