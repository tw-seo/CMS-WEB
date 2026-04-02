from __future__ import annotations

from datetime import datetime
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


def _generate_viewer_manage_key() -> str:
    ts_sec = int(datetime.utcnow().timestamp())
    return f"V{ts_sec}"


class ViewerManage(models.Model):
    viewer_manage_key = models.CharField(
        max_length=50,
        primary_key=True,
        db_column="viewer_manage_key",
        default=_generate_viewer_manage_key,
    )
    setter_key = models.CharField(
        max_length=50,
        db_column="setter_key",
        blank=True,
        null=True,
    )
    user_key = models.CharField(
        max_length=50,
        db_column="user_key",
        blank=True,
        null=True,
    )
    setter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="viewer_manage_setters",
        db_column="setter_id",
        limit_choices_to={"is_staff": True},
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="viewer_manage_users",
        db_column="user_id",
        limit_choices_to={"is_staff": False},
    )
    camera_keys = ArrayField(
        base_field=models.CharField(max_length=50),
        default=list,
        blank=True,
    )
    assignment_version = models.BigIntegerField(
        db_column="assignment_version",
        default=1,
    )

    class Meta:
        db_table = "VIEWER_MANAGE"
        indexes = [
            models.Index(fields=["setter"]),
            models.Index(fields=["user"]),
        ]
