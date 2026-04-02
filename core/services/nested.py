from typing import Any, Generic, Sequence, TypeVar

from core.utils.http import get_or_404
from django.db import models, transaction

ChildT = TypeVar("ChildT", bound=models.Model)
SchemaT = TypeVar("SchemaT")


class BaseNestedService(Generic[ChildT, SchemaT]):
    """
    Nested CRUD 서비스 (parent_field 기반)
    - parent_field: FK 이름 (ex: "emission_source")
    - model: 자식 모델
    """

    model: type[ChildT]
    parent_field: str

    def __init__(self, company: Any = None):
        self.company = company

    @transaction.atomic
    def create(self, payload: SchemaT, parent: Any) -> ChildT:
        data = payload.dict()
        data[self.parent_field] = parent
        return self.model.objects.create(**data)

    def list(self, parent: Any, values: Sequence[str] | None = None):
        qs = self.model.objects.filter(**{self.parent_field: parent})
        return qs.values(*values) if values else qs

    def retrieve(self, id: int) -> ChildT:
        return get_or_404(self.model.objects, pk=id)

    @transaction.atomic
    def update_from_schema(self, obj: ChildT, payload: SchemaT) -> ChildT:
        data = payload.dict(exclude_unset=True)
        for field, value in data.items():
            setattr(obj, field, value)
        obj.save(update_fields=list(data.keys()))
        return obj

    @transaction.atomic
    def delete(self, obj: ChildT) -> None:
        obj.delete()
