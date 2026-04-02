from apps.company.models import Company
from apps.company.schemas.company import CompanyCreateSchema, CompanyUpdateSchema
from core.schemas.file import FileSchema
from core.services.base import BaseService
from django.db import transaction
from ninja.files import UploadedFile


class CompanyService(BaseService[Company, CompanyCreateSchema]):
    model = Company

    @transaction.atomic
    def create_with_file(
        self, payload: CompanyCreateSchema, file: UploadedFile | None, request
    ) -> dict:
        data = payload.dict(exclude_unset=True)
        obj = self.model.objects.create(**data)

        if file:
            obj.attachment.save(file.name, file, save=True)

        return self.serialize_with_file(obj, request)

    @transaction.atomic
    def update_with_file(
        self,
        obj: Company,
        payload: CompanyUpdateSchema,
        file: UploadedFile | None,
        request,
    ) -> dict:
        data = payload.dict(exclude_unset=True)
        for field, value in data.items():
            setattr(obj, field, value)

        if file:
            if obj.attachment:
                obj.attachment.delete(save=False)
            obj.attachment.save(file.name, file, save=True)

        obj.save()
        return self.serialize_with_file(obj, request)

    def serialize_with_file(self, obj: Company, request) -> dict:
        return {
            "id": obj.id,
            "name": obj.name,
            "representative": obj.representative,
            "registration_number": obj.registration_number,
            "file": FileSchema.from_field(obj.attachment, request),
        }
