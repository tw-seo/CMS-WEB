from django.db import models

class CameraInfo(models.Model):
    camera_name   = models.CharField(max_length=50, null=True, blank=True)
    location      = models.CharField(max_length=50, null=True, blank=True)
    ip_address    = models.GenericIPAddressField(protocol="IPv4")  # C# varchar(15) 대응
    port          = models.CharField(max_length=5)                 # 그대로 문자열 포트
    user_name     = models.CharField(max_length=50, null=True, blank=True)
    password      = models.CharField(max_length=50, null=True, blank=True)
    rtsp_url_001  = models.CharField(max_length=255)
    rtsp_url_002  = models.CharField(max_length=255, null=True, blank=True)
    rtsp_url_003  = models.CharField(max_length=255, null=True, blank=True)
    camera_info_key = models.CharField(max_length=50, primary_key=True)
    websocket_api = models.CharField(max_length=255, null=True, blank=True)
    view_index    = models.IntegerField(null=True, blank=True)
    is_thermal    = models.BooleanField(default=False)

    class Meta:
        db_table = "CAMERA_INFO_TABLE"       # ← C#과 동일한 물리 테이블명
        indexes = [
            models.Index(fields=["ip_address"]),
            models.Index(fields=["camera_name"]),
            models.Index(fields=["view_index"]),
        ]
