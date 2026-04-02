import json
from pathlib import Path

from core.services.base import BaseService
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from mptt.utils import get_cached_trees

from apps.masterdata.models import MenuPermissions, PermissionGroup
from apps.masterdata.schemas import PermissionGroupSchema


class PermissionService(BaseService[PermissionGroup, PermissionGroupSchema]):
    model = PermissionGroup

    def _get_menu_list_to_dict(self) -> dict:
        path = Path(settings.BASE_DIR) / "core" / "files" / "menu_list.json"
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _serialize_node(self, node) -> dict:
        children = getattr(node, "_cached_children", [])
        return {
            "id": node.id,
            "name": node.name,
            "permissions": node.permissions,
            "submenu": [self._serialize_node(ch) for ch in children],
        }

    @transaction.atomic
    def sync(self, group_obj: PermissionGroup):
        MenuPermissions.objects.filter(group=group_obj).delete()
        for parent_name, details in self._get_menu_list_to_dict().items():
            parent_permission = MenuPermissions.objects.create(
                group=group_obj, name=parent_name
            )
            for child_name in details:
                MenuPermissions.objects.create(
                    group=group_obj,
                    name=child_name,
                    parent=parent_permission,
                )

        return "퍼미션 업데이트 완료"

    @transaction.atomic
    def create(self, payload: PermissionGroupSchema) -> PermissionGroup:
        data = payload.dict()
        obj = self.model.objects.create(**data)

        for parent_name, details in self._get_menu_list_to_dict().items():
            parent_permission = MenuPermissions.objects.create(
                group=obj,
                name=parent_name,
            )
            for child_name in details:
                MenuPermissions.objects.create(
                    group=obj,
                    name=child_name,
                    parent=parent_permission,
                )

        return obj

    def get_menu_permissions(self, group_obj: PermissionGroup) -> list[dict]:
        qs = (
            MenuPermissions.objects.filter(group=group_obj)
            .order_by("tree_id", "lft")
            .only("id", "name", "permissions", "parent")
        )
        roots = get_cached_trees(qs)
        return [self._serialize_node(root) for root in roots]

    @transaction.atomic
    def update_permission_state(self, permission_id: int, state: bool) -> int:
        perm = MenuPermissions.objects.select_for_update().get(pk=permission_id)

        if state and perm.get_ancestors().filter(permissions=False).exists():
            raise ValidationError("상위 메뉴 권한을 먼저 변경해주세요.")

        target_qs = perm.get_descendants(include_self=True).only("id")
        affected_ids = list(target_qs.values_list("id", flat=True))
        if not affected_ids:
            return 0

        updated = MenuPermissions.objects.filter(id__in=affected_ids).update(
            permissions=state
        )
        return updated
