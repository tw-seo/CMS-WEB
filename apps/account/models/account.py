from core.managers.base_managers import SoftDeleteManager
from core.models import BaseModel
from datetime import datetime
from django.contrib.auth.models import AbstractUser
from django.db import models
import random


def _generate_account_key() -> str:
    ts_sec = int(datetime.utcnow().timestamp())
    rand = random.randint(1000, 9999)
    return f"AC{ts_sec}{rand}"


class Account(AbstractUser, BaseModel):
    account_key = models.CharField(
        primary_key=True, max_length=50, db_column="account_key", default=_generate_account_key
    )
    username = models.CharField(max_length=150, unique=True, db_column="user_id")
    first_name = models.CharField(max_length=150, blank=True, db_column="user_name")
    last_name = None
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into this admin site.",
        verbose_name="staff status",
        db_column="is_admin",
    )
    department = models.CharField(
        max_length=128, blank=True, null=True, verbose_name="부서"
    )
    position = models.CharField(
        max_length=128, blank=True, null=True, verbose_name="직급"
    )

    groups = None
    user_permissions = None

    objects: SoftDeleteManager["Account"] = SoftDeleteManager()

    class Meta:
        db_table = "ACCOUNT_TABLE"
        verbose_name = "사용자"
