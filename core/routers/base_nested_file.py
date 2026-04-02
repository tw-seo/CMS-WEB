from http import HTTPStatus
from typing import Any, Generic, List, Optional, TypeVar

from core.schema import ErrorSchema, MessageSchema
from core.utils.http import get_or_404, resp
from django.db import models
from ninja import File, Form, Router
from ninja.files import UploadedFile

ParentT = TypeVar("ParentT", bound=models.Model)
ChildT = TypeVar("ChildT", bound=models.Model)
ServiceT = TypeVar("ServiceT")
CreateSchemaT = TypeVar("CreateSchemaT")
UpdateSchemaT = TypeVar("UpdateSchemaT")
ResponseSchemaT = TypeVar("ResponseSchemaT")


class BaseNestedFileRouter(
    Generic[ParentT, ChildT, ServiceT, CreateSchemaT, UpdateSchemaT, ResponseSchemaT]
):
    """Nested CRUD File Router"""

    def __init__(
        self,
        *,
        parent_model: type[ParentT],
        child_model: type[ChildT],
        service_class: type[ServiceT],
        create_schema: type[CreateSchemaT],
        update_schema: type[UpdateSchemaT],
        response_schema: type[ResponseSchemaT],
        prefix: str,
        tags: Optional[list[str]] = None,
    ):
        self.router = Router(tags=tags or [])
        self.parent_model = parent_model
        self.child_model = child_model
        self.service_class = service_class
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.response_schema = response_schema
        self.prefix = prefix
        self._register_routes()

    def __getattr__(self, name: str):
        return getattr(self.router, name)

    def get_service(self, request):
        return self.service_class(company=getattr(request.auth, "company", None))

    def get_parent(self, request, parent_id: int):
        return get_or_404(self.parent_model.objects, pk=parent_id)

    def handle_get(self, request: Any, obj: Any):
        return obj

    def handle_list(self, request: Any, qs: list[Any]):
        return list(qs)

    def _register_routes(self):
        child_name = self.child_model.__name__.lower()
        parent_name = self.parent_model.__name__.lower()

        @self.router.post(
            f"/{{parent_id}}/{self.prefix}",
            operation_id=f"{parent_name}_{child_name}_create",
            response={HTTPStatus.CREATED: MessageSchema},
        )
        def create_item(
            request: Any,
            parent_id: int,
            payload: Form[self.create_schema],  # type: ignore
            file: Optional[UploadedFile] = File(None),
        ):
            parent = self.get_parent(request, parent_id)
            service = self.get_service(request)
            service.create_with_file(payload, parent, file)
            return resp(HTTPStatus.CREATED, "생성 완료")

        @self.router.get(
            f"/{{parent_id}}/{self.prefix}",
            operation_id=f"{parent_name}_{child_name}_list",
            response={HTTPStatus.OK: List[self.response_schema]},
        )
        def list_items(request: Any, parent_id: int):
            parent = self.get_parent(request, parent_id)
            service = self.get_service(request)
            qs = service.list(parent)
            return resp(HTTPStatus.OK, self.handle_list(request, qs))

        @self.router.get(
            f"/{{parent_id}}/{self.prefix}/{{id}}",
            operation_id=f"{parent_name}_{child_name}_get",
            response={
                HTTPStatus.OK: self.response_schema,
                HTTPStatus.NOT_FOUND: ErrorSchema,
            },
        )
        def get_item(request: Any, parent_id: int, id: int):
            service = self.get_service(request)
            obj = service.retrieve(id)
            return resp(HTTPStatus.OK, self.handle_get(request, obj))

        @self.router.put(
            f"/{{parent_id}}/{self.prefix}/{{id}}",
            operation_id=f"{parent_name}_{child_name}_update",
            response={HTTPStatus.OK: MessageSchema},
        )
        def update_item(
            request: Any,
            parent_id: int,
            id: int,
            payload: Form[self.update_schema],  # type: ignore
            file: Optional[UploadedFile] = File(None),
        ):
            service = self.get_service(request)
            obj = service.retrieve(id)
            service.update_with_file(obj, payload, file)
            return resp(HTTPStatus.OK, "수정 완료")

        @self.router.delete(
            f"/{{parent_id}}/{self.prefix}/{{id}}",
            operation_id=f"{parent_name}_{child_name}_delete",
            response={HTTPStatus.NO_CONTENT: None},
        )
        def delete_item(request: Any, parent_id: int, id: int):
            service = self.get_service(request)
            obj = service.retrieve(id)
            service.delete(obj)
            return resp(HTTPStatus.NO_CONTENT, "삭제 완료")
