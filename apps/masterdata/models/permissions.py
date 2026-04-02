from core.models import BaseModel
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey


class PermissionGroup(BaseModel):
    name = models.CharField(max_length=256, default="", verbose_name="그룹명")

    class Meta:
        db_table = "permission_group"
        verbose_name = "권한 그룹"


class MenuPermissions(MPTTModel, BaseModel):
    group = models.ForeignKey(
        PermissionGroup, on_delete=models.CASCADE, verbose_name="권한 그룹"
    )
    name = models.CharField(max_length=256, default="", verbose_name="메뉴명")
    permissions = models.BooleanField(default=True, verbose_name="권한")
    parent = TreeForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="submenu"
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "menu_permissions"
        verbose_name = "메뉴 권한"
