from typing import Any, Generic, Sequence, TypeVar

from core.utils.http import get_or_404
from django.db import models, transaction
from django.db.models import F

SchemaT = TypeVar("SchemaT")
ModelT = TypeVar("ModelT", bound=models.Model)


class BaseService(Generic[ModelT, SchemaT]):
    """
    공통 CRUD 서비스

    기능:
    - company 필드가 있는 모델은 자동으로 company를 주입 후 필터링하며, 없는 모델은 무시
    - create / list / retrieve / update / delete 공통 제공

    FK 매핑 옵션:
    - fk_mappings: 모든 조회(list / retrieve)에 항상 annotate 되는 FK 매핑
    - list_mappings: list 조회 시에만 annotate 되는 FK 매핑
    - retrieve_mappings: 단건 조회 시에만 annotate 되는 FK 매핑
    """

    model: type[ModelT]
    fk_mappings: dict[str, str] = {}
    list_mappings: dict[str, str] = {}
    retrieve_mappings: dict[str, str] = {}

    def __init__(self, company: Any = None):
        self.company = company

    def _has_company_field(self) -> bool:
        return "company" in {f.name for f in self.model._meta.fields}

    @transaction.atomic
    def create(self, payload: SchemaT) -> ModelT:
        data = payload.dict()
        if self._has_company_field():
            data["company"] = self.company
        return self.model.objects.create(**data)

    def list(self, values: Sequence[str] | None = None):
        qs = self.model.objects.all()
        if self._has_company_field():
            qs = qs.filter(company=self.company)

        mappings = self.fk_mappings | self.list_mappings
        if mappings:
            qs = qs.annotate(**{alias: F(path) for alias, path in mappings.items()})
        return qs.values(*values) if values else qs

    def retrieve(self, id: int):
        qs = self.model.objects.all()
        if self._has_company_field():
            qs = qs.filter(company=self.company)

        mappings = self.fk_mappings | self.retrieve_mappings
        if mappings:
            qs = qs.annotate(**{alias: F(path) for alias, path in mappings.items()})
        return get_or_404(qs, pk=id)

    @transaction.atomic
    def update_from_schema(self, obj: ModelT, payload: SchemaT) -> ModelT:
        data = payload.dict(exclude_unset=True)
        for field, value in data.items():
            setattr(obj, field, value)
        obj.save(update_fields=list(data.keys()))
        return obj

    @transaction.atomic
    def delete(self, obj: ModelT) -> None:
        obj.delete()  # soft delete 대응 가능
