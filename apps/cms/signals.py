from __future__ import annotations

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CameraInfo, ViewerManage


@receiver(post_delete, sender=CameraInfo)
def _remove_camera_key_from_viewer_manage(sender, instance: CameraInfo, **kwargs) -> None:
    key = (instance.camera_info_key or "").strip()
    if not key:
        return
    rows = ViewerManage.objects.filter(camera_keys__contains=[key])
    for row in rows:
        row.camera_keys = [item for item in row.camera_keys if item != key]
        row.save(update_fields=["camera_keys"])
