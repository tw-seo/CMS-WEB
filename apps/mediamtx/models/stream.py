from django.conf import settings
from django.db import models

from core.models import CompanyBaseModel


class StreamProtocol(models.TextChoices):
    RTSP = "rtsp", "RTSP"
    HLS = "hls", "HLS"
    WEBRTC = "webrtc", "WebRTC"


class MediaStream(CompanyBaseModel):
    camera_key = models.CharField(max_length=128, db_index=True)
    stream_path = models.CharField(max_length=128, unique=True)
    original_rtsp = models.CharField(max_length=1024)
    stream_type = models.CharField(max_length=16, choices=StreamProtocol.choices)
    source_on_demand = models.BooleanField(default=False)
    token_auth_enabled = models.BooleanField(default=True)
    last_issued_token = models.TextField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    last_issued_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_streams",
    )

    class Meta:
        db_table = "media_stream"
        verbose_name = "Media stream"
        unique_together = ("company", "camera_key")
        indexes = [
            models.Index(fields=["company", "stream_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.camera_key} ({self.stream_type})"
