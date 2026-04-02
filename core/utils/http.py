from http import HTTPStatus
from typing import Any, Iterable, Sequence, Type, TypeVar, Union

from django.db.models import Model, Q, QuerySet
from ninja.errors import HttpError

T = TypeVar("T", bound=Model)

SUCCESS_CODES = {
    HTTPStatus.OK,
    HTTPStatus.CREATED,
    HTTPStatus.ACCEPTED,
    HTTPStatus.NO_CONTENT,
}


def resp(status: int, body: Any):
    """
    공통 response

    기능:
    - 문자열이면 스키마에 맞게 감싸서 반환
    - 성공 코드: {"message": "..."} (204는 None)
    - 에러 코드: {"detail": "..."}
    """
    if isinstance(body, str):
        if status in SUCCESS_CODES:
            return status, (
                {} if status == HTTPStatus.NO_CONTENT else {"message": body}
            )
        return status, {"detail": body}
    return status, body


def get_or_404(
    model_or_qs: Union[Type[T], QuerySet[T]],
    /,
    *,
    pk: Any | None = None,
    msg: str = "리소스를 찾을 수 없습니다.",
    q: Q | None = None,
    filters: dict | None = None,
    only: Sequence[str] | None = None,
    select_related: Iterable[str] | None = None,
    prefetch_related: Iterable[str] | None = None,
    for_update: bool = False,
    only_alive: bool = True,
    **kwargs: Any,
) -> T:
    """
    get_object_or_404 대체 django-ninja friendly 하도록 재 정의

    기능:
    - Model/QuerySet 모두 지원, 옵션으로 최적화 가능하도록 정의
    - only_alive=True면 is_deleted=False 자동 필터링
    """
    qs: QuerySet[T]
    if isinstance(model_or_qs, type) and issubclass(model_or_qs, Model):
        qs = model_or_qs.objects.all()
    else:
        qs = model_or_qs

    if q is not None:
        qs = qs.filter(q)
    if filters:
        qs = qs.filter(**filters)
    if kwargs:
        qs = qs.filter(**kwargs)
    if pk is not None:
        qs = qs.filter(pk=pk)
    if only_alive and hasattr(qs.model, "is_deleted"):
        qs = qs.filter(is_deleted=False)
    if only:
        qs = qs.only(*only)
    if select_related:
        qs = qs.select_related(*select_related)
    if prefetch_related:
        qs = qs.prefetch_related(*prefetch_related)
    if for_update:
        qs = qs.select_for_update()

    obj = qs.first()
    if obj is None:
        raise HttpError(HTTPStatus.NOT_FOUND, msg)
    return obj
