from django.db import models

from core.managers.base_managers import SoftDeleteManager


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일자")
    updated_at = models.DateTimeField(
        null=True, blank=True, verbose_name="최근 수정일자"
    )
    created_by = models.CharField(default="admin", verbose_name="등록자")
    is_deleted = models.BooleanField(default=False, verbose_name="삭제 유무")

    objects: SoftDeleteManager["BaseModel"] = SoftDeleteManager()

    class Meta:
        abstract = True


class CompanyBaseModel(BaseModel):
    company = models.ForeignKey(
        "company.Company", on_delete=models.CASCADE, verbose_name="업체"
    )

    objects: SoftDeleteManager["CompanyBaseModel"] = SoftDeleteManager()

    class Meta:
        abstract = True
