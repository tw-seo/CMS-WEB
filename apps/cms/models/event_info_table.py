from django.db import models
from django.contrib.postgres.fields import ArrayField  # 배열 타입

class EventInfoTable(models.Model):
    event_register_key   = models.CharField(max_length=50, primary_key=True)
    camera_info_key      = models.CharField(max_length=50)                 # 필요시 FK 교체 가능
    rtsp_url             = models.CharField(max_length=200)
    event_type_key       = models.CharField(max_length=50)                 # 필요시 FK 교체 가능
    event_info_roi       = ArrayField(                                     # varchar(10)[]
        base_field=models.CharField(max_length=10),
        blank=False,
        default=list,
    )
    object_to_detects    = ArrayField(                                     # varchar(10)[]
        base_field=models.CharField(max_length=10),
        null=True, blank=True,
        default=list,
    )
    edge_detect          = models.BooleanField(default=True)               # NOT NULL DEFAULT true
    event_info_roi_multi = ArrayField(                                     # varchar(200)[][]
        base_field=ArrayField(
            base_field=models.CharField(max_length=200),
            default=list,
            blank=True,
        ),
        null=True, blank=True,
        default=list,
    )
    event_shadow_roi = ArrayField(                                     # varchar(200)[][]
        base_field=ArrayField(
            base_field=models.CharField(max_length=200),
            default=list,
            blank=True,
        ),
        null=True, blank=True,
        default=list,
    )

    class Meta:
        db_table = "EVENT_INFO_TABLE"
        indexes = [
            models.Index(fields=["camera_info_key"]),
            models.Index(fields=["event_type_key"]),
        ]
