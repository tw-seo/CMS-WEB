from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
from django.db import transaction
from apps.cms.models import (
    BuzzerInterlockTable,
    CameraInfo,
    EventInfoTable,
)
from apps.cms.schemas import CamInfo

KST = ZoneInfo("Asia/Seoul")


def _get_attr(source, *candidates: str) -> Optional[object]:
    for name in candidates:
        if source is None:
            continue
        if isinstance(source, dict) and name in source:
            return source.get(name)
        if hasattr(source, name):
            return getattr(source, name, None)
    return None


def _stripped(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _boolish(value: Optional[object]) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "t"}:
        return True
    if text in {"0", "false", "no", "n", "f"}:
        return False
    return None


def _ensure_required(value: Optional[str], field: str) -> str:
    if not value:
        raise ValueError(f"{field} is required.")
    return value


def _generate_camera_key(suffix: str = "") -> str:
    ts_sec = int(datetime.now(KST).timestamp())
    return f"C{ts_sec}{suffix}"


def _next_view_index() -> int:
    indices = (
        CameraInfo.objects.exclude(view_index__isnull=True)
        .order_by("view_index")
        .values_list("view_index", flat=True)
    )
    expected = 0
    for value in indices:
        if value == expected:
            expected += 1
        elif value > expected:
            break
    return expected


def _normalize_view_indices() -> None:
    rows = list(CameraInfo.objects.values("camera_info_key", "view_index"))
    if not rows:
        return

    rows.sort(
        key=lambda row: (
            row.get("view_index") is None,
            row.get("view_index") if row.get("view_index") is not None else 10**9,
            row.get("camera_info_key") or "",
        )
    )

    for idx, row in enumerate(rows):
        if row.get("view_index") == idx:
            continue
        CameraInfo.objects.filter(camera_info_key=row.get("camera_info_key")).update(view_index=idx)


def _camera_payload(info: CamInfo | dict, *, include_key: bool = False) -> Dict[str, object]:
    camera_name = _stripped(
        _get_attr(info, "cam_name", "c5o_camName")
    )
    location = _stripped(
        _get_attr(info, "cam_location", "c5o_camLocation")
    )
    ip_address = _ensure_required(
        _stripped(_get_attr(info, "cam_ip", "c5o_ip")),
        "ip_address",
    )
    port = _ensure_required(
        _stripped(_get_attr(info, "cam_port", "cam_port", "c5o_port")),
        "port",
    )
    user_name = _stripped(_get_attr(info, "cam_id", "c5o_cam_id"))
    password = _stripped(_get_attr(info, "cam_pw", "c5o_password"))
    rtsp_url_001 = _ensure_required(
        _stripped(
            _get_attr(
                info,
                "cam_rtsp_url1",
                "cam_main_stream",
                "c5o_rtsp_url1",
            )
        ),
        "rtsp_url_001",
    )
    rtsp_url_002 = _stripped(_get_attr(info, "cam_rtsp_url2", "cam_second_stream", "c5o_rtsp_url2"))
    rtsp_url_003 = _stripped(_get_attr(info, "cam_rtsp_rul3", "cam_third_stream", "c5o_rtsp_url3"))
    websocket_api = _stripped(_get_attr(info, "cam_websocket_api", "c5o_websocket_api"))
    is_thermal = _boolish(_get_attr(info, "is_thermal", "c5o_is_thermal", "isThermal"))
    if is_thermal is None:
        is_thermal = False

    view_index = _get_attr(info, "cam_view_index", "c5o_viewIndex")
    view_index_value = None
    if view_index is not None:
        try:
            view_index_value = int(view_index)
        except (TypeError, ValueError):
            view_index_value = None
        else:
            if view_index_value < 0:
                view_index_value = None

    payload: Dict[str, object] = {
        "camera_name": camera_name,
        "location": location,
        "ip_address": ip_address,
        "port": port,
        "user_name": user_name,
        "password": password,
        "rtsp_url_001": rtsp_url_001,
        "rtsp_url_002": rtsp_url_002,
        "rtsp_url_003": rtsp_url_003,
        "websocket_api": websocket_api,
        "is_thermal": is_thermal,
    }

    if view_index_value is not None:
        payload["view_index"] = view_index_value

    if include_key:
        key = _stripped(_get_attr(info, "cam_info_key", "c5o_camera_info_key"))
        if not key:
            raise ValueError("cam_info_key is required for update.")
        payload["camera_info_key"] = key

    return payload


def select_camera_info() -> Tuple[bool, List[CamInfo]]:
    try:
        _normalize_view_indices()
        rows = (
            CameraInfo.objects.order_by("view_index", "camera_info_key")
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
    except Exception:
        return False, []

    result: List[CamInfo] = []
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
                cam_view_index=row.get("view_index") if row.get("view_index") is not None else -1,
                is_thermal=bool(row.get("is_thermal", False)),
            )
        )
    return True, result


def insert_camera_info(info: CamInfo | dict) -> bool:
    if info is None:
        return False

    try:
        payload = _camera_payload(info)
        payload["view_index"] = _next_view_index()
        payload["camera_info_key"] = _generate_camera_key()
        camera = CameraInfo.objects.create(**payload)
    except ValueError:
        return False
    except Exception:
        return False
    try:
        from apps.mediamtx.services.registry import register_camera_rtsp

        register_camera_rtsp(camera.camera_info_key, camera.rtsp_url_001)
    except Exception:
        pass
    return True


def update_camera_info(info: CamInfo | dict) -> bool:
    if info is None:
        return False

    try:
        payload = _camera_payload(info, include_key=True)
    except ValueError:
        return False
    except Exception:
        return False

    key = payload.pop("camera_info_key")
    view_index = payload.pop("view_index", None)

    update_fields = {k: v for k, v in payload.items() if v is not None or k in ["camera_name", "location"]}
    if view_index is not None:
        update_fields["view_index"] = view_index

    if not update_fields:
        return False

    try:
        existing = CameraInfo.objects.filter(camera_info_key=key).values("rtsp_url_001").first()
        updated = CameraInfo.objects.filter(camera_info_key=key).update(**update_fields)
    except Exception:
        return False
    if updated <= 0:
        return False

    try:
        from apps.mediamtx.services.registry import register_camera_rtsp, remove_camera_rtsp

        new_rtsp = update_fields.get("rtsp_url_001")
        old_rtsp = existing.get("rtsp_url_001") if existing else None
        if new_rtsp and new_rtsp != old_rtsp:
            remove_camera_rtsp(key, old_rtsp)
            register_camera_rtsp(key, new_rtsp)
        elif new_rtsp:
            register_camera_rtsp(key, new_rtsp)
    except Exception:
        pass
    return True


def insert_camera_info_array(infos: Sequence[CamInfo | dict]) -> bool:
    if not infos:
        return False

    objs: List[CameraInfo] = []
    base_view_index = _next_view_index()
    base_key = _generate_camera_key()
    for offset, info in enumerate(infos):
        if info is None:
            continue
        try:
            payload = _camera_payload(info)
        except ValueError:
            continue

        payload["view_index"] = base_view_index
        base_view_index += 1
        payload["camera_info_key"] = f"{base_key}{offset}"
        objs.append(CameraInfo(**payload))

    if not objs:
        return False

    try:
        with transaction.atomic():
            CameraInfo.objects.bulk_create(objs, ignore_conflicts=False)
    except Exception:
        return False

    try:
        from apps.mediamtx.services.registry import register_camera_rtsp

        for obj in objs:
            register_camera_rtsp(obj.camera_info_key, obj.rtsp_url_001)
    except Exception:
        pass

    return True


def delete_camera_info(keys: Sequence[str]) -> bool:
    valid_keys = [_stripped(key) for key in keys or [] if _stripped(key)]
    if not valid_keys:
        return False

    try:
        existing = list(
            CameraInfo.objects.filter(camera_info_key__in=valid_keys).values(
                "camera_info_key", "rtsp_url_001"
            )
        )
        with transaction.atomic():
            deleted_count, _ = CameraInfo.objects.filter(camera_info_key__in=valid_keys).delete()

            if deleted_count > 0:
                remaining_rows = list(
                    CameraInfo.objects.values("camera_info_key", "view_index")
                )
                remaining_rows.sort(
                    key=lambda row: (
                        row.get("view_index") is None,
                        row.get("view_index") if row.get("view_index") is not None else 10**9,
                        row.get("camera_info_key") or "",
                    )
                )

                for idx, row in enumerate(remaining_rows):
                    if row.get("view_index") == idx:
                        continue
                    CameraInfo.objects.filter(camera_info_key=row.get("camera_info_key")).update(view_index=idx)
    except Exception:
        return False

    try:
        from apps.mediamtx.services.registry import remove_camera_rtsp

        for row in existing:
            remove_camera_rtsp(row.get("camera_info_key") or "", row.get("rtsp_url_001"))
    except Exception:
        pass

    return deleted_count > 0


def delete_cam_associated_remaining_event_info(keys: Sequence[str]) -> None:
    valid_keys = [_stripped(key) for key in keys or [] if _stripped(key)]
    if not valid_keys:
        return

    try:
        with transaction.atomic():
            EventInfoTable.objects.filter(camera_info_key__in=valid_keys).delete()
    except Exception:
        pass


def delete_cam_associated_remaining_interlock_info(keys: Sequence[str]) -> None:
    valid_keys = [_stripped(key) for key in keys or [] if _stripped(key)]
    if not valid_keys:
        return

    try:
        with transaction.atomic():
            BuzzerInterlockTable.objects.filter(camera_info_key__in=valid_keys).delete()
    except Exception:
        pass


def update_websocket_endpoint_to_null(cam_info_key: str) -> bool:
    key = _stripped(cam_info_key)
    if not key:
        return False

    try:
        exists = CameraInfo.objects.filter(camera_info_key=key).exists()
    except Exception:
        return False
    if not exists:
        return False

    try:
        CameraInfo.objects.filter(camera_info_key=key).update(websocket_api=None)
    except Exception:
        return False
    return True


def update_websocket_info(info: CamInfo | dict) -> bool:
    if info is None:
        return False

    key = _stripped(_get_attr(info, "cam_info_key", "c5o_camera_info_key"))
    if not key:
        return False

    websocket_api = _stripped(_get_attr(info, "cam_websocket_api", "c5o_websocket_api"))
    if websocket_api is None:
        # 요청에 websocket 값이 없으면 camera_info_key로 설정
        websocket_api = key

    try:
        exists = CameraInfo.objects.filter(camera_info_key=key).exists()
    except Exception:
        return False
    if not exists:
        return False

    try:
        CameraInfo.objects.filter(camera_info_key=key).update(websocket_api=websocket_api)
    except Exception:
        return False
    return True


def get_next_view_index() -> int:
    return _next_view_index()
