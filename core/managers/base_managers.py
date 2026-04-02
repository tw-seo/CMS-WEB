from typing import Generic, TypeVar

from django.db import models
from typing_extensions import Self

_T = TypeVar("_T", bound=models.Model)


class SoftDeleteQuerySetMixin:
    def delete(self) -> int:
        """SoftDelete delete 호출 시 is_deleted=True로 변경"""
        return super().update(is_deleted=True)

    def alive(self) -> Self:
        """삭제되지 않은 데이터"""
        return self.filter(is_deleted=False)

    def deleted(self) -> Self:
        """삭제된 데이터만"""
        return self.filter(is_deleted=True)

    def with_deleted(self) -> Self:
        """삭제 포함 전체"""
        return self.all()


class SoftDeleteQuerySet(SoftDeleteQuerySetMixin, models.QuerySet[_T], Generic[_T]):
    pass


class SoftDeleteManager(models.Manager[_T], Generic[_T]):
    def get_queryset(self) -> SoftDeleteQuerySet[_T]:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def alive(self) -> SoftDeleteQuerySet[_T]:
        return self.get_queryset().alive()

    def deleted(self) -> SoftDeleteQuerySet[_T]:
        return self.get_queryset().deleted()

    def with_deleted(self) -> SoftDeleteQuerySet[_T]:
        return SoftDeleteQuerySet(self.model, using=self._db)
