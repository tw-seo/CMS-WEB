from http import HTTPStatus

from core.routers.base import BaseRouter
from core.schema import MessageSchema
from core.utils.http import get_or_404, resp
from django.core.exceptions import ValidationError
from ninja import Path

from apps.masterdata.models import PermissionGroup
from apps.masterdata.schemas import (
    MenuPermissionSchema,
    PermissionGroupResponseSchema,
    PermissionGroupSchema,
    UpdatePermissionSchema,
)
from apps.masterdata.services import PermissionService


class PermissionRouter(BaseRouter):
    def __init__(self):
        super().__init__(
            service_class=PermissionService,
            model=PermissionGroup,
            create_schema=PermissionGroupSchema,
            update_schema=PermissionGroupSchema,
            response_schema=PermissionGroupResponseSchema,
            tags=["기준정보 관리 - 권한 관리"],
        )

        @self.router.put(
            "{id}/sync",
            response={HTTPStatus.OK: MessageSchema},
        )
        def sync_permissions(
            request, id: int = Path(..., ge=1, description="permission id")
        ):
            group = get_or_404(PermissionGroup, pk=id)
            service = PermissionService()
            return resp(HTTPStatus.OK, service.sync(group_obj=group))

        @self.router.get(
            "{id}/menus", response={HTTPStatus.OK: list[MenuPermissionSchema]}
        )
        def get_menu_permissions(
            request, id: int = Path(..., ge=1, description="permission id")
        ):
            group = get_or_404(PermissionGroup, pk=id)
            service = PermissionService()
            return resp(HTTPStatus.OK, service.get_menu_permissions(group_obj=group))

        @self.router.put(
            "{id}/menus",
            response={HTTPStatus.OK: dict, HTTPStatus.BAD_REQUEST: dict},
        )
        def update_menu_permission(
            request,
            payload: UpdatePermissionSchema,
            id: int = Path(..., ge=1, description="menu id"),
        ):
            service = PermissionService()
            try:
                updated = service.update_permission_state(id, payload.permissions)
                return resp(HTTPStatus.OK, {"message": f"수정 완료 ({updated}건 반영)"})
            except ValidationError as e:
                return resp(HTTPStatus.BAD_REQUEST, {"detail": e.messages[0]})


permission_router = PermissionRouter()
