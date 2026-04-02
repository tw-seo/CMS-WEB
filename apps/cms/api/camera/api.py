from ninja import Body, Field, Router, Schema
from ninja.errors import HttpError
from pydantic import AliasChoices

from apps.cms.schemas import CamInfo, ApplyCamInfosIn, All_Info_Dto, Cam_Key_And_Name
from apps.cms.api.api import build_all_info
from apps.account.models import Account
from apps.cms.models import CameraInfo, ViewerManage
from apps.cms.services.actions.camera import (
    insert_camera_info_array,
    update_camera_info,
    update_websocket_info,
    delete_camera_info,
    delete_cam_associated_remaining_event_info,
    delete_cam_associated_remaining_interlock_info,
    select_camera_info,
)
from apps.cms.services.actions.event import select_event_info_table
from apps.cms.services.actions.event_type import select_event_type_table
from apps.cms.services.actions.buzzer import select_buzzer_info_table
from apps.cms.services.actions.interlock import select_interlock_table
from apps.cms.services.workers.viewer_notifier import (
    notify_viewer_account_info_change,
    notify_viewer_all_info_update,
    notify_viewer_cms_update,
)
from apps.mediamtx.services.registry import register_dl_rtsp_bulk

router = Router(tags=["Camera"])

def _notify_viewer_all(reason: str) -> None:
    try:
        notify_viewer_all_info_update(reason)
        notify_viewer_account_info_change(reason)
    except Exception as exc:
        print(f"[viewer-notify][camera] failed ({reason}): {exc}")


class GetKeyAndNameIn(Schema):
    user_id: str = Field(
        description="Account id",
        validation_alias=AliasChoices("user_id", "userId", "id"),
    )
    pw: str = Field(description="Password", validation_alias=AliasChoices("pw", "password"))


class DlMtxRtspIn(Schema):
    camera_key: str
    dl_rtsp: str


@router.post(
    "/apply_camera_infos/",
    response=All_Info_Dto,
    summary="카메라 변경 적용",
    description="새 카메라 등록 및 삭제 대상 제거 후 전체 설정 스냅샷을 반환합니다.",
)
def apply_cam_infos(request, payload: ApplyCamInfosIn):
    delete_keys = [(key or "").strip() for key in payload.delete_keys if (key or "").strip()]
    new_items = [info for info in payload.cam_infos if not (info.cam_info_key or "").strip()]
    if delete_keys:
        if not delete_camera_info(delete_keys):
            raise HttpError(404, "Some camera keys were not found for deletion.")
        delete_cam_associated_remaining_event_info(delete_keys)
        delete_cam_associated_remaining_interlock_info(delete_keys)

    if new_items and not insert_camera_info_array(new_items):
        raise HttpError(400, "Failed to insert camera infos.")
    _notify_viewer_all("camera_apply")
    return build_all_info()


@router.post(
    "/modify_cam_info/",
    response=All_Info_Dto,
    summary="카메라 정보 수정",
    description="단일 카메라를 수정하고 전체 설정 스냅샷을 반환합니다.",
)
def modify_cam_info(request, payload: CamInfo):
    if not update_camera_info(payload):
        raise HttpError(404, "Camera info not found.")
    _notify_viewer_all("camera_modify")
    return build_all_info()


@router.post(
    "/update_websocket_endpoint/",
    response=bool,
    summary="웹소켓 엔드포인트 업데이트",
    description="camera_info_key에 해당하는 websocket_api 값을 업데이트합니다.",
)
def update_websocket_endpoint(request, payload: CamInfo):
    print(payload)
    updated = update_websocket_info(payload)
    if not updated:
        raise HttpError(400, "Failed to update websocket endpoint.")
    _notify_viewer_all("camera_websocket_update")
    return True


@router.post(
    "/select_camera_infos/",
    response=list[CamInfo],
    summary="카메라 정보 획득",
    description="카메라 정보를 획득한다.",
)
def select_cam_info(request):
    _, cam_infos = select_camera_info()
    return cam_infos


@router.post(
    "/new_dl_mtx_rtsps/",
    response=dict[str, int],
    summary="DL RTSP mapping update",
    description="K-Safety-DL sends camera_key and dl_rtsp mappings.",
)
def new_dl_mtx_rtsps(request, payload: list[DlMtxRtspIn] = Body(...)):
    updated = register_dl_rtsp_bulk(payload)
    notify_viewer_cms_update("mtx_info_update")
    return {"updated": updated}


@router.post(
    "/get_key_and_name/",
    response=list[Cam_Key_And_Name],
    summary="카메라 키/이름 조회",
    description="사용자 ID와 비밀번호를 통해 카메라 키와 이름 목록을 조회합니다.",
)
def get_key_and_name(request, payload: GetKeyAndNameIn):
    user_id = (payload.user_id or "").strip()
    password = payload.pw or ""
    if not user_id or not password:
        return []

    account = (
        Account.objects.filter(username=user_id, is_active=True, is_deleted=False)
        .only("account_key", "is_superuser", "is_staff", "password")
        .first()
    )
    if not account or not account.check_password(password):
        return []

    if account.is_superuser or account.is_staff:
        rows = CameraInfo.objects.order_by("view_index", "camera_info_key").values(
            "camera_info_key", "camera_name"
        )
    else:
        keys_set = set()
        rows_keys = ViewerManage.objects.filter(user_key=str(account.account_key)).values_list(
            "camera_keys", flat=True
        )
        for item in rows_keys:
            if not item:
                continue
            for key in item:
                if key:
                    keys_set.add(str(key))
        if not keys_set:
            return []
        rows = CameraInfo.objects.filter(camera_info_key__in=keys_set).order_by(
            "view_index", "camera_info_key"
        ).values("camera_info_key", "camera_name")

    result = []
    for row in rows:
        result.append(
            Cam_Key_And_Name(
                cam_key=str(row.get("camera_info_key") or ""),
                cam_name=str(row.get("camera_name") or ""),
            )
        )
    return result
