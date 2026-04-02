from __future__ import annotations

from datetime import datetime
import logging
from typing import List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Count

from apps.cms.models import EventInfoTable
from apps.cms.schemas import EventInfo

KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)


def _build_dl_add_event_url() -> str:
    ip = str(getattr(settings, "DL_IP", "") or "")
    port = str(getattr(settings, "DL_PORT", "") or "")
    if not ip or not port:
        return ""
    path = str(getattr(settings, "DL_ADD_EVENT_PATH", "/api/add_new_event") or "")
    if not path.startswith("/"):
        path = f"/{path}"
    print(f"씨바 여기 봐라 http://{ip}:{port}{path}")
    return f"http://{ip}:{port}{path}"


def _notify_dl_add_event(camera_info_key: Optional[str], event_register_key: Optional[str]) -> None:
    url = _build_dl_add_event_url()
    if not url:
        return
    payload = {
        "camera_info_key": camera_info_key or "",
        "event_register_key": event_register_key or "",
    }
    timeout = float(getattr(settings, "DL_ADD_EVENT_TIMEOUT_SECONDS", 5) or 5)
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("DL add_new_event failed: %s", exc)


def _build_dl_add_all_event_url() -> str:
    ip = str(getattr(settings, "DL_IP", "") or "")
    port = str(getattr(settings, "DL_PORT", "") or "")
    if not ip or not port:
        return ""
    path = str(getattr(settings, "DL_ADD_ALL_EVENT_PATH", "/api/add_all_event") or "")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://{ip}:{port}{path}"


def _notify_dl_add_all_event(camera_info_key: Optional[str]) -> None:
    url = _build_dl_add_all_event_url()
    if not url:
        return
    payload = {"camera_info_key": camera_info_key or ""}
    timeout = float(getattr(settings, "DL_ADD_ALL_EVENT_TIMEOUT_SECONDS", 5) or 5)
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("DL add_all_event failed: %s", exc)


def _build_dl_modify_event_url() -> str:
    ip = str(getattr(settings, "DL_IP", "") or "")
    port = str(getattr(settings, "DL_PORT", "") or "")
    if not ip or not port:
        return ""
    path = str(getattr(settings, "DL_MODIFY_EVENT_PATH", "/api/modify_one_event") or "")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://{ip}:{port}{path}"


def _notify_dl_modify_event(
    camera_info_key: Optional[str], event_register_key: Optional[str]
) -> None:
    url = _build_dl_modify_event_url()
    if not url:
        return
    payload = {
        "camera_info_key": camera_info_key or "",
        "event_register_key": event_register_key or "",
    }
    timeout = float(getattr(settings, "DL_MODIFY_EVENT_TIMEOUT_SECONDS", 5) or 5)
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("DL modify_one_event failed: %s", exc)


def _build_dl_delete_event_url() -> str:
    ip = str(getattr(settings, "DL_IP", "") or "")
    port = str(getattr(settings, "DL_PORT", "") or "")
    if not ip or not port:
        return ""
    path = str(getattr(settings, "DL_DELETE_EVENT_PATH", "/api/delete_one_event") or "")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://{ip}:{port}{path}"


def _notify_dl_delete_event(
    camera_info_key: Optional[str], event_register_key: Optional[str]
) -> None:
    url = _build_dl_delete_event_url()
    if not url:
        return
    payload = {
        "camera_info_key": camera_info_key or "",
        "event_register_key": event_register_key or "",
    }
    timeout = float(getattr(settings, "DL_DELETE_EVENT_TIMEOUT_SECONDS", 5) or 5)
    try:
        response = requests.delete(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("DL delete_one_event failed: %s", exc)


def _build_dl_delete_all_event_url() -> str:
    ip = str(getattr(settings, "DL_IP", "") or "")
    port = str(getattr(settings, "DL_PORT", "") or "")
    if not ip or not port:
        return ""
    path = str(getattr(settings, "DL_DELETE_ALL_EVENT_PATH", "/api/delete_all_event") or "")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://{ip}:{port}{path}"


def _notify_dl_delete_all_event(camera_info_key: Optional[str]) -> None:
    url = _build_dl_delete_all_event_url()
    if not url:
        return
    payload = {"camera_info_key": camera_info_key or ""}
    timeout = float(getattr(settings, "DL_DELETE_ALL_EVENT_TIMEOUT_SECONDS", 5) or 5)
    try:
        response = requests.delete(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("DL delete_all_event failed: %s", exc)


def _normalize_jagged(value) -> Optional[List[List[str]]]:
    if value in (None, []):
        return None

    if isinstance(value, list):
        if not value:
            return None
        if isinstance(value[0], list):
            return [[str(item) if item is not None else None for item in row] for row in value]
        return [list(map(lambda item: str(item) if item is not None else None, value))]

    if isinstance(value, tuple):
        return _normalize_jagged(list(value))

    if isinstance(value, str):
        return [[value]]

    if isinstance(value, dict):
        return None

    try:
        if value.shape and value.ndim == 2:  # type: ignore[attr-defined]
            rows, cols = value.shape  # type: ignore[attr-defined]
            result = []
            for i in range(rows):
                row = []
                for j in range(cols):
                    row.append(str(value[i, j]) if value[i, j] is not None else None)
                result.append(row)
            return result
    except AttributeError:
        pass

    return None


def _to_rectangular(jagged: Optional[Sequence[Sequence[str]]]):
    if not jagged:
        return None

    rows = len(jagged)
    cols = max(len(row) if row else 0 for row in jagged)
    if cols == 0:
        return None

    rect = []
    for row in jagged:
        row = row or []
        rect.append([row[i] if i < len(row) else None for i in range(cols)])
    return rect


def select_event_info_table() -> Tuple[bool, List[EventInfo]]:
    try:
        queryset = EventInfoTable.objects.all().order_by("event_register_key")
    except Exception:
        return False, []

    result: List[EventInfo] = []
    for row in queryset:
        result.append(
            EventInfo(
                event_key=row.event_register_key or "",
                cam_info_key=row.camera_info_key or "",
                rtsp_url=row.rtsp_url or "",
                evt_type_key=row.event_type_key or "",
                event_info_roi=list(row.event_info_roi or []),
                event_info_roi_multi=_normalize_jagged(row.event_info_roi_multi) or [],
                shadow_rois=_normalize_jagged(row.event_shadow_roi) or [],
                edge_detect=row.edge_detect if row.edge_detect is not None else True,
            )
        )

    return True, result


def check_event_info_table_count(camera_info_key: str, max_event_count: int) -> bool:
    if not camera_info_key:
        return False

    try:
        count = EventInfoTable.objects.filter(camera_info_key=camera_info_key).count()
    except Exception:
        return False

    return count < max_event_count


def insert_event_info_table(info: EventInfo) -> bool:
    if info is None:
        return False

    try:
        ts_sec = int(datetime.now(KST).timestamp())
        primary_key = f"E{ts_sec}"

        event = EventInfoTable.objects.create(
            event_register_key=primary_key,
            camera_info_key=info.cam_info_key or None,
            rtsp_url=info.rtsp_url or None,
            event_type_key=info.evt_type_key or None,
            event_info_roi=list(info.event_info_roi or []),
            edge_detect=info.edge_detect,
            event_info_roi_multi=_to_rectangular(info.event_info_roi_multi),
            event_shadow_roi=_to_rectangular(info.shadow_rois),
        )
    except Exception:
        return False

    _notify_dl_add_event(event.camera_info_key, event.event_register_key)
    return True


def update_event_info_table(info: EventInfo) -> bool:
    if info is None or not info.event_key:
        return False

    try:
        existing_camera_key = (
            EventInfoTable.objects.filter(event_register_key=info.event_key)
            .values_list("camera_info_key", flat=True)
            .first()
        )
        updated = EventInfoTable.objects.filter(event_register_key=info.event_key).update(
            camera_info_key=info.cam_info_key or None,
            rtsp_url=info.rtsp_url or None,
            event_type_key=info.evt_type_key or None,
            event_info_roi=list(info.event_info_roi or []),
            edge_detect=info.edge_detect,
            event_info_roi_multi=_to_rectangular(info.event_info_roi_multi),
            event_shadow_roi=_to_rectangular(info.shadow_rois),
        )
    except Exception:
        return False
    if updated > 0:
        _notify_dl_modify_event(info.cam_info_key or existing_camera_key, info.event_key)
        return True
    return False


def insert_event_info_table_bulk(infos: Sequence[EventInfo]) -> bool:
    if not infos:
        return False

    camera_keys = sorted(
        {
            (info.cam_info_key or "").strip()
            for info in infos
            if (info.cam_info_key or "").strip()
        }
    )
    try:
        with transaction.atomic():
            if camera_keys:
                EventInfoTable.objects.filter(camera_info_key__in=camera_keys).delete()
            ts_sec = int(datetime.now(KST).timestamp())

            objs = []
            for offset, info in enumerate(infos):
                key = f"E{ts_sec + offset}"
                objs.append(
                    EventInfoTable(
                        event_register_key=key,
                        camera_info_key=info.cam_info_key or None,
                        rtsp_url=info.rtsp_url or None,
                        event_type_key=info.evt_type_key or None,
                        event_info_roi=list(info.event_info_roi or []),
                        edge_detect=info.edge_detect,
                        event_info_roi_multi=_to_rectangular(info.event_info_roi_multi),
                        event_shadow_roi=_to_rectangular(info.shadow_rois),
                    )
                )
            EventInfoTable.objects.bulk_create(objs, ignore_conflicts=False)
    except Exception:
        return False
    for key in camera_keys:
        _notify_dl_add_all_event(key)
    return True


def delete_all_event_info_table(camera_info_key: str) -> bool:
    key = (camera_info_key or "").strip()
    if not key:
        return False

    try:
        deleted, _ = EventInfoTable.objects.filter(camera_info_key=key).delete()
    except Exception:
        return False
    if deleted > 0:
        _notify_dl_delete_all_event(key)
        return True
    return False


def delete_event_info_table_using_evt_key(event_register_key: str) -> bool:
    key = (event_register_key or "").strip()
    if not key:
        return False

    try:
        row = (
            EventInfoTable.objects.filter(event_register_key=key)
            .values("camera_info_key", "event_register_key")
            .first()
        )
        deleted, _ = EventInfoTable.objects.filter(event_register_key=key).delete()
    except Exception:
        return False
    if deleted > 0:
        _notify_dl_delete_event(
            row.get("camera_info_key") if row else None,
            row.get("event_register_key") if row else None,
        )
        return True
    return False


def update_edge_detection_attribute() -> None:
    # Django migrations should manage schema updates. This placeholder matches the C# intent.
    pass
