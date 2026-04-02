from typing import Any

from core.routers.base_file import BaseFileRouter

from apps.company.models import Company
from apps.company.schemas.company import (
    CompanyCreateSchema,
    CompanyResponseSchema,
    CompanyUpdateSchema,
)
from apps.company.services.company import CompanyService


class CompanyRouter(
    BaseFileRouter[
        Company,
        CompanyService,
        CompanyCreateSchema,
        CompanyUpdateSchema,
        CompanyResponseSchema,
    ]
):
    def __init__(self):
        super().__init__(
            service_class=CompanyService,
            model=Company,
            create_schema=CompanyCreateSchema,
            update_schema=CompanyUpdateSchema,
            response_schema=CompanyResponseSchema,
            tags=[
                "회사 관리, 개인정보 관리에 사용 될 듯? 추후 정리"
            ],
        )

    def handle_get(self, request: Any, obj: Company):
        service = CompanyService(company=request.auth.company)
        return service.serialize_with_file(obj, request)

    def handle_list(self, request: Any, qs):
        service = CompanyService(company=request.auth.company)
        return [service.serialize_with_file(obj, request) for obj in qs]


company_router = CompanyRouter()
