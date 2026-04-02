from ninja import Router, Schema, Field
from ninja.errors import HttpError

from apps.account.models import Account
from apps.cms.models import CameraInfo, ViewerManage
from apps.cms.schemas import Viewer_Manager_Set_Info
from django.db import models
from django.conf import settings
from pydantic import AliasChoices
from apps.cms.services.workers.viewer_notifier import (
    notify_viewer_account_info_change,
    notify_viewer_all_info_update,
)

viewer_manage_router = Router(tags=["viewer-manage"])

def _notify_viewer_all(reason: str) -> None:
    if not bool(getattr(settings, "VIEWER_ASSIGNMENT_PUSH_ENABLED", False)):
        return
    try:
        notify_viewer_all_info_update(reason)
        notify_viewer_account_info_change(reason)
    except Exception as exc:
        print(f"[viewer-notify][viewer-manage] failed ({reason}): {exc}")


@viewer_manage_router.post(
    "/apply_viewer_manager_set_info/",
    summary="Apply viewer-manage infos",
    description="Validate setter/user/camera_keys and insert VIEWER_MANAGE row.",
    response=list[Viewer_Manager_Set_Info],
)
def apply_viewer_manage(request, payload: Viewer_Manager_Set_Info):
    setter_key = (payload.setter_key or "").strip()
    user_key = (payload.user_key or "").strip()
    print(
        "[viewer-manage] payload",
        {
            "viewer_manager_key": payload.viewer_manager_key,
            "camera_keys": payload.camera_keys,
            "setter_id": payload.setter_id,
            "setter_key": payload.setter_key,
            "user_id": payload.user_id,
            "user_key": payload.user_key,
        },
    )
    if not setter_key or not user_key:
        raise HttpError(400, "setter_key and user_key are required.")

    setter = (
        Account.objects.filter(
            account_key=setter_key, is_active=True, is_deleted=False
        )
        .only("account_key", "is_superuser", "is_staff")
        .first()
    )
    if setter:
        print(
            "[viewer-manage] setter",
            {
                "account_key": setter.account_key,
                "is_superuser": setter.is_superuser,
                "is_admin": setter.is_staff,
            },
        )
    else:
        print("[viewer-manage] setter not found", {"setter_key": setter_key})
    if not setter or not (setter.is_superuser or setter.is_staff):
        raise HttpError(403, "setter_key is not authorized.")

    user = (
        Account.objects.filter(
            account_key=user_key, is_active=True, is_deleted=False
        )
        .only("account_key")
        .first()
    )
    if user:
        print("[viewer-manage] user", {"account_key": user.account_key})
    else:
        print("[viewer-manage] user not found", {"user_key": user_key})
    if not user:
        raise HttpError(400, "Invalid user_key.")

    keys = [str(k).strip() for k in (payload.camera_keys or []) if str(k).strip()]
    if not keys:
        raise HttpError(400, "camera_keys is required.")

    existing = set(
        CameraInfo.objects.filter(camera_info_key__in=keys).values_list(
            "camera_info_key", flat=True
        )
    )
    valid_keys = [k for k in keys if k in existing]
    if not valid_keys:
        raise HttpError(400, "No valid camera_keys.")

    existing = ViewerManage.objects.filter(
        setter_key=setter_key, user_key=user_key
    ).order_by("viewer_manage_key")
    if existing.exists():
        row = existing.first()
        row.setter = setter
        row.user = user
        row.camera_keys = valid_keys
        row.assignment_version = int(row.assignment_version or 0) + 1
        row.save(update_fields=["setter", "user", "camera_keys", "assignment_version"])
    else:
        ViewerManage.objects.create(
            setter=setter,
            user=user,
            setter_key=setter_key,
            user_key=user_key,
            camera_keys=valid_keys,
            assignment_version=1,
        )

    _notify_viewer_all("viewer_manage_apply")
    results: list[Viewer_Manager_Set_Info] = []
    rows = ViewerManage.objects.all().order_by("viewer_manage_key")
    for row in rows:
        results.append(
            Viewer_Manager_Set_Info(
                viewer_manager_key=row.viewer_manage_key,
                camera_keys=list(row.camera_keys or []),
                setter_id=str(row.setter_id),
                setter_key=row.setter_key,
                user_id=str(row.user_id),
                user_key=row.user_key,
                assignment_version=int(row.assignment_version or 0),
            )
        )
    return results


class ViewerManageSelectIn(Schema):
    account_key: str = Field(
        description="Account key",
        validation_alias=AliasChoices("account_key", "accountKey"),
    )


class ViewerManageDeleteIn(Schema):
    user_key: str = Field(
        description="User account key",
        validation_alias=AliasChoices("user_key", "userKey"),
    )
    account_key: str = Field(
        description="Account key",
        validation_alias=AliasChoices("account_key", "accountKey"),
    )


@viewer_manage_router.post(
    "/select_viewer_manager_set_info/",
    summary="Select viewer-manage infos by account_key",
    description="Return Viewer_Manager_Set_Info rows assigned to the given account_key.",
    response=list[Viewer_Manager_Set_Info],
)
def select_viewer_manage_info(request, payload: ViewerManageSelectIn):
    account_key = str(payload.account_key).strip()
    if not account_key:
        raise HttpError(400, "account_key is required.")

    rows = ViewerManage.objects.filter(
        models.Q(user_key=account_key) | models.Q(setter_key=account_key)
    ).order_by("viewer_manage_key")
    results: list[Viewer_Manager_Set_Info] = []
    for row in rows:
        results.append(
            Viewer_Manager_Set_Info(
                viewer_manager_key=row.viewer_manage_key,
                camera_keys=list(row.camera_keys or []),
                setter_id=str(row.setter_id),
                setter_key=row.setter_key,
                user_id=str(row.user_id),
                user_key=row.user_key,
                assignment_version=int(row.assignment_version or 0),
            )
        )
    return results


@viewer_manage_router.post(
    "/delete_viewer_manager_set_info/",
    summary="Delete viewer-manage info",
    description="Delete VIEWER_MANAGE row by viewer_manager_key.",
    response=list[Viewer_Manager_Set_Info],
)
def delete_viewer_manage_info(request, payload: ViewerManageDeleteIn):
    user_key = str(payload.user_key).strip()
    account_key = str(payload.account_key).strip()
    if not user_key:
        raise HttpError(400, "user_key is required.")
    if not account_key:
        raise HttpError(400, "account_key is required.")
    ViewerManage.objects.filter(
        models.Q(user_key=user_key)
        & (models.Q(setter_key=account_key) | models.Q(user_key=account_key))
    ).delete()

    _notify_viewer_all("viewer_manage_delete")
    rows = ViewerManage.objects.filter(
        models.Q(user_key=account_key) | models.Q(setter_key=account_key)
    ).order_by("viewer_manage_key")
    results: list[Viewer_Manager_Set_Info] = []
    for row in rows:
        results.append(
            Viewer_Manager_Set_Info(
                viewer_manager_key=row.viewer_manage_key,
                camera_keys=list(row.camera_keys or []),
                setter_id=str(row.setter_id),
                setter_key=row.setter_key,
                user_id=str(row.user_id),
                user_key=row.user_key,
                assignment_version=int(row.assignment_version or 0),
            )
        )
    return results
