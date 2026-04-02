from http import HTTPStatus
from typing import Any

from core.exceptions import AppError
from core.schema import ErrorSchema
from core.utils.http import resp
from ninja import Router

from apps.account.schemas import LoginSchema, TokenResponseSchema
from apps.account.services.auth import AuthService

auth_router = Router(tags=["로그인"])


@auth_router.post(
    "/login",
    response={
        HTTPStatus.OK: TokenResponseSchema,
        HTTPStatus.BAD_REQUEST: ErrorSchema,
        HTTPStatus.SERVICE_UNAVAILABLE: ErrorSchema,
        HTTPStatus.FORBIDDEN: ErrorSchema,
    },
    auth=None,
)
def login(request: Any, payload: LoginSchema):
    try:
        data = AuthService().login(request, payload.username, payload.password)
        return data
    except AppError as e:
        return resp(e.status, e.detail)
