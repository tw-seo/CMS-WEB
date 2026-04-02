from core.managers.base_managers import SoftDeleteManager
from core.models import BaseModel
from django.db import models


class Company(BaseModel):
    name = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="회사명"
    )
    representative = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="대표자"
    )
    registration_number = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="사업자등록번호"
    )

    business_item = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="업종"
    )
    business_type = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="업태"
    )
    business_start_dt = models.DateTimeField(
        blank=True, null=True, verbose_name="개업일자"
    )

    address = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="회사주소"
    )
    phone_number = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="전화번호"
    )
    fax_number = models.CharField(
        max_length=256, blank=True, null=True, verbose_name="팩스번호"
    )


    objects: SoftDeleteManager["Company"] = SoftDeleteManager()

    class Meta:
        db_table = "company"
        verbose_name = "회사"
