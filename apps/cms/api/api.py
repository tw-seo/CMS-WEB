from ninja import Router, Field, Schema
from pydantic import AliasChoices

from apps.cms.schemas import All_Info_Dto, CamInfo, EventInfo
from apps.mediamtx.schemas import MediaStreamRtspMapSchema
from apps.account.models import Account
from apps.cms.services.actions.buzzer import select_buzzer_info_table
from apps.cms.services.actions.camera import select_camera_info
from apps.cms.services.actions.event import select_event_info_table
from apps.cms.services.actions.event_type import select_event_type_table
from apps.cms.services.actions.interlock import select_interlock_table
from apps.cms.models import CameraInfo, ViewerManage, EventInfoTable

router = Router(tags=["Setting View"])


def build_all_info() -> All_Info_Dto:
    _, cam_infos = select_camera_info()
    _, event_infos = select_event_info_table()
    _, event_types = select_event_type_table()
    _, buzzer_infos = select_buzzer_info_table()
    _, interlock_infos = select_interlock_table()
    try:
        from apps.mediamtx.services.registry import get_rtsp_mapping_snapshot

        snapshot = get_rtsp_mapping_snapshot()
    except Exception:
        snapshot = {}

    mtx_infos: list[MediaStreamRtspMapSchema] = []
    for camera_key in sorted(snapshot):
        entry = snapshot.get(camera_key) or []
        mtx_infos.append(
            MediaStreamRtspMapSchema(
                camera_key=str(camera_key),
                original_rtsp=str(entry[0]) if len(entry) > 0 else "",
                mediamtx_rtsp=str(entry[1]) if len(entry) > 1 else "",
                dl_rtsp=str(entry[2]) if len(entry) > 2 else "",
                mtx_dl_rtsp=str(entry[3]) if len(entry) > 3 else "",
            )
        )
    return All_Info_Dto(
        cam_infos=cam_infos,
        event_infos=event_infos,
        event_types=event_types,
        buzzer_infos=buzzer_infos,
        interlock_infos=interlock_infos,
        mtx_infos=mtx_infos,
    )


class GetAllInfoUsingIdIn(Schema):
    user_id: str = Field(
        description="Account id",
        validation_alias=AliasChoices("user_id", "userId", "id"),
    )
    pw: str = Field(description="Password", validation_alias=AliasChoices("pw", "password"))


def _build_cam_infos_for_keys(camera_keys: list[str]) -> list[CamInfo]:
    if not camera_keys:
        return []

    rows = (
        CameraInfo.objects.filter(camera_info_key__in=camera_keys)
        .order_by("view_index", "camera_info_key")
        .values(
            "camera_info_key",
            "camera_name",
            "location",
            "ip_address",
            "port",
            "user_name",
            "password",
            "rtsp_url_001",
            "rtsp_url_002",
            "rtsp_url_003",
            "view_index",
            "websocket_api",
            "is_thermal",
        )
    )
    result: list[CamInfo] = []
    for idx, row in enumerate(rows, start=1):
        result.append(
            CamInfo(
                index=idx,
                cam_name=row.get("camera_name") or "no name",
                cam_location=row.get("location"),
                cam_rtsp_url1=row.get("rtsp_url_001"),
                cam_rtsp_url2=row.get("rtsp_url_002"),
                cam_rtsp_rul3=row.get("rtsp_url_003"),
                cam_ip=row.get("ip_address"),
                cam_port=row.get("port"),
                cam_main_stream=row.get("rtsp_url_001"),
                cam_second_stream=row.get("rtsp_url_002"),
                cam_third_stream=row.get("rtsp_url_003"),
                cam_id=row.get("user_name"),
                cam_pw=row.get("password"),
                cam_info_key=row.get("camera_info_key"),
                cam_view_index=row.get("view_index")
                if row.get("view_index") is not None
                else -1,
                is_thermal=bool(row.get("is_thermal", False)),
            )
        )
    return result


def _build_event_infos_for_keys(camera_keys: list[str]) -> list[EventInfo]:
    if not camera_keys:
        return []
    _, all_events = select_event_info_table()
    camera_key_set = set(camera_keys)
    return [evt for evt in all_events if evt.cam_info_key in camera_key_set]


def _build_mtx_infos_for_keys(camera_keys: list[str]) -> list[MediaStreamRtspMapSchema]:
    if not camera_keys:
        return []
    try:
        from apps.mediamtx.services.registry import get_rtsp_mapping_snapshot

        snapshot = get_rtsp_mapping_snapshot()
    except Exception:
        snapshot = {}

    ordered_camera_keys = list(
        CameraInfo.objects.filter(camera_info_key__in=camera_keys)
        .order_by("view_index", "camera_info_key")
        .values_list("camera_info_key", flat=True)
    )

    mtx_infos: list[MediaStreamRtspMapSchema] = []
    for camera_key in ordered_camera_keys:
        entry = snapshot.get(camera_key) or []
        mtx_infos.append(
            MediaStreamRtspMapSchema(
                camera_key=str(camera_key),
                original_rtsp=str(entry[0]) if len(entry) > 0 else "",
                mediamtx_rtsp=str(entry[1]) if len(entry) > 1 else "",
                dl_rtsp=str(entry[2]) if len(entry) > 2 else "",
                mtx_dl_rtsp=str(entry[3]) if len(entry) > 3 else "",
            )
        )
    return mtx_infos


@router.post(
    "/get_setting_view_all_info/",
    response=All_Info_Dto,
    summary="설정 화면 전체 데이터 조회",
    description="카메라/버저/인터락/이벤트/이벤트타입 데이터를 모두 조회해 한 번에 반환합니다.",
)
def get_setting_view_all_info(request):
    print("[get_setting_view_all_info] called", {"method": request.method})
    result = build_all_info()
    print(
        "[get_setting_view_all_info] result",
        {
            "cam_infos": len(result.cam_infos),
            "event_infos": len(result.event_infos),
            "event_types": len(result.event_types),
            "buzzer_infos": len(result.buzzer_infos),
            "interlock_infos": len(result.interlock_infos),
            "mtx_infos": len(result.mtx_infos),
        },
    )
    return result


@router.post(
    "/get_all_info_using_id/",
    response=All_Info_Dto,
    summary="Get all info by account id",
    description="Return all info for admin/superuser, or filtered camera info for normal users.",
)
def get_all_info_using_id(request, payload: GetAllInfoUsingIdIn):
    user_id = (payload.user_id or "").strip()
    password = payload.pw or ""
    if not user_id or not password:
        return All_Info_Dto()

    account = (
        Account.objects.filter(username=user_id, is_active=True, is_deleted=False)
        .only("account_key", "is_superuser", "is_staff", "password")
        .first()
    )
    if not account or not account.check_password(password):
        return All_Info_Dto()

    if account.is_superuser or account.is_staff:
        return build_all_info()

    keys_set: set[str] = set()
    rows = ViewerManage.objects.filter(user_key=str(account.account_key)).values_list(
        "camera_keys", flat=True
    )
    for item in rows:
        if not item:
            continue
        for key in item:
            if key:
                keys_set.add(str(key))
    camera_keys = list(keys_set)

    _, event_types = select_event_type_table()
    _, buzzer_infos = select_buzzer_info_table()
    _, interlock_infos = select_interlock_table()

    cam_infos = _build_cam_infos_for_keys(camera_keys)
    event_infos = _build_event_infos_for_keys(camera_keys)
    mtx_infos = _build_mtx_infos_for_keys(camera_keys)

    return All_Info_Dto(
        cam_infos=cam_infos,
        event_infos=event_infos,
        event_types=event_types,
        buzzer_infos=buzzer_infos,
        interlock_infos=interlock_infos,
        mtx_infos=mtx_infos,
    )
