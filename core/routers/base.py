from http import HTTPStatus
from typing import Any, Generic, List, Optional, TypeVar

from core.schema import ErrorSchema, MessageSchema
from core.utils.http import resp
from django.db import models
from ninja import Router

ServiceT = TypeVar("ServiceT")
ModelT = TypeVar("ModelT", bound=models.Model)
CreateSchemaT = TypeVar("CreateSchemaT")
UpdateSchemaT = TypeVar("UpdateSchemaT")
ResponseSchemaT = TypeVar("ResponseSchemaT")


class BaseRouter(
    Generic[ModelT, ServiceT, CreateSchemaT, UpdateSchemaT, ResponseSchemaT]
):
    """JSON 기반 CRUD 라우터"""

    def __init__(
        self,
        *,
        service_class: type[ServiceT],
        model: type[ModelT],
        create_schema: type[CreateSchemaT],
        update_schema: type[UpdateSchemaT],
        response_schema: type[ResponseSchemaT],
        tags: Optional[list[str]] = None,
        operation_id=None,
    ):
        self.router = Router(tags=tags or [])
        self.service_class = service_class
        self.model = model
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.response_schema = response_schema
        self.operation_id = operation_id
        self._register_routes()

    def __getattr__(self, name: str):
        return getattr(self.router, name)

    def _get_service(self, request):
        return self.service_class(company=getattr(request.auth, "company", None))

    def _get_operation_id(self):
        return self.operation_id if self.operation_id else self.model.__name__.lower()

    def _register_routes(self):
        # model_name = self.model.__name__.lower()
        model_name = self._get_operation_id()

        @self.router.post(
            "",
            operation_id=f"{model_name}_create",
            response={HTTPStatus.CREATED: MessageSchema},
        )
        def create_item(request: Any, payload: self.create_schema):  # type: ignore
            service = self._get_service(request)
            service.create(payload)
            return resp(HTTPStatus.CREATED, "생성 완료")

        @self.router.get(
            "",
            operation_id=f"{model_name}_list",
            response={HTTPStatus.OK: List[self.response_schema]},
        )
        def list_items(request: Any):
            service = self._get_service(request)
            return resp(HTTPStatus.OK, service.list())

        @self.router.get(
            "{id}",
            operation_id=f"{model_name}_get",
            response={
                HTTPStatus.OK: self.response_schema,
                HTTPStatus.NOT_FOUND: ErrorSchema,
            },
        )
        def get_item(request: Any, id: int):
            service = self._get_service(request)
            return resp(HTTPStatus.OK, service.retrieve(id))

        @self.router.put(
            "{id}",
            operation_id=f"{model_name}_update",
            response={HTTPStatus.OK: MessageSchema},
        )
        def update_item(request: Any, id: int, payload: self.update_schema):  # type: ignore
            service = self._get_service(request)
            obj = service.retrieve(id)
            service.update_from_schema(obj, payload)
            return resp(HTTPStatus.OK, "수정 완료")

        @self.router.delete(
            "{id}",
            operation_id=f"{model_name}_delete",
            response={HTTPStatus.NO_CONTENT: None},
        )
        def delete_item(request: Any, id: int):
            service = self._get_service(request)
            obj = service.retrieve(id)
            service.delete(obj)
            return resp(HTTPStatus.NO_CONTENT, "삭제 완료")
