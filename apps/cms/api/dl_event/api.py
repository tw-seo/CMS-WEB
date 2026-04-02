from ninja import Router, Schema
import logging

from ninja.errors import HttpError

from apps.cms.schemas import EventInfo, EventType, All_Info_Dto
from apps.cms.api.api import build_all_info
from apps.cms.services.actions.event import (
    insert_event_info_table,
    insert_event_info_table_bulk,
    update_event_info_table,
    delete_event_info_table_using_evt_key,
    delete_all_event_info_table,
    select_event_info_table,
)
from apps.cms.services.actions.camera import select_camera_info
from apps.cms.services.actions.buzzer import select_buzzer_info_table
from apps.cms.services.actions.interlock import select_interlock_table
from apps.cms.services.actions.event_type import select_event_type_table

from apps.cms.schemas import (
    DeleteEventLogRequest,
    EventLogCountResponse,
    EventOccurIn,
    ReportInfo,
    ReportRequest,
    ReportResponse,
    SimpleEventLogCount,
    SimpleEventLogRequest,
)
from apps.cms.services.workers.viewer_notifier import (
    notify_viewer_account_info_change,
    notify_viewer_all_info_update,
    notify_viewer_evt_occur,
)
from apps.cms.services.actions.event_occur import (
    count_event_occurrences,
    delete_event_occurrences,
    normalize_event_occurrences,
    save_event_occurrences,
    serialize_normalized_event_occurrences,
    select_event_occurrences,
    select_simple_event_log,
)

logger = logging.getLogger(__name__)
router = Router(tags=["DL-Event"])

def _notify_viewer_all(reason: str) -> None:
    try:
        notify_viewer_all_info_update(reason)
        notify_viewer_account_info_change(reason)
    except Exception as exc:
        logger.warning("Viewer all/account notify failed (%s): %s", reason, exc)


class EventKeyIn(Schema):
    evt_key: str


class CameraKeyIn(Schema):
    camera_key: str


@router.post(
    "/insert_event_info/",
    response=All_Info_Dto,
    summary="단일 이벤트 등록",
    description="이벤트를 1건 생성하고 전체 설정 스냅샷을 반환합니다.",
)
def insert_event_info(request, payload: EventInfo):
    if not insert_event_info_table(payload):
        raise HttpError(400, "Failed to insert event info.")
    _notify_viewer_all("event_insert")
    return build_all_info()


@router.post(
    "/insert_multi_event_infos/",
    response=All_Info_Dto,
    summary="여러 이벤트 일괄 등록",
    description="여러 이벤트를 생성하고 전체 설정 스냅샷을 반환합니다.",
)
def insert_multi_event_infos(request, payload: list[EventInfo]):
    if not insert_event_info_table_bulk(payload):
        raise HttpError(400, "Failed to insert event infos.")
    _notify_viewer_all("event_insert_multi")
    return build_all_info()


@router.post(
    "/update_event_info/",
    response=All_Info_Dto,
    summary="이벤트 수정",
    description="단일 이벤트를 수정하고 전체 설정 스냅샷을 반환합니다.",
)
def update_event_info(request, payload: EventInfo):
    if not update_event_info_table(payload):
        raise HttpError(404, "Event info not found.")
    _notify_viewer_all("event_update")
    return build_all_info()


@router.post(
    "/delete_evnet_info/",
    response=All_Info_Dto,
    summary="이벤트 키로 삭제",
    description="이벤트 1건을 삭제하고 전체 설정 스냅샷을 반환합니다.",
)
def delete_evnet_info(request, payload: EventKeyIn):
    if not delete_event_info_table_using_evt_key(payload.evt_key):
        raise HttpError(404, "Event info not found.")
    _notify_viewer_all("event_delete")
    return build_all_info()


@router.post(
    "/delete_all_event_info/",
    response=All_Info_Dto,
    summary="카메라 기준 이벤트 전체 삭제",
    description="지정한 카메라의 모든 이벤트를 삭제하고 전체 설정 스냅샷을 반환합니다.",
)
def delete_all_event_info(request, payload: CameraKeyIn):
    if not delete_all_event_info_table(payload.camera_key):
        raise HttpError(404, "No event info found for camera.")
    _notify_viewer_all("event_delete_all")
    return build_all_info()


@router.post(
    "/get_event_types/",
    response=list[EventType],
    summary="이벤트 타입 조회",
    description="시스템에 저장된 모든 이벤트 타입을 반환합니다.",
)
def get_event_types(request):
    _, event_types = select_event_type_table()
    return event_types


@router.post(
    "/evt_update/",
    summary="이벤트 발생 내역 업데이트",
    description="이벤트 발생 목록을 저장하고 처리 건수를 반환합니다.",
)
def evt_update(request, payload: list[EventOccurIn]):
    count = save_event_occurrences(payload)
    return {"message": "Success", "count": count}


@router.post(
    "/evt_occur/",
    summary="이벤트 발생 내역 수신 (DL)",
    description="DL에서 전달된 이벤트 발생 목록을 저장하고 처리 건수를 반환합니다.",
)
def evt_occur(request, payload: list[EventOccurIn]):
    normalized_items = normalize_event_occurrences(payload)
    count = save_event_occurrences(payload, normalized_items=normalized_items)
    try:
        forward_payload = serialize_normalized_event_occurrences(normalized_items)
        notify_viewer_evt_occur(forward_payload)
    except Exception as exc:
        logger.warning("Viewer evt_occur notify failed: %s", exc)
    return {"message": "Success", "count": count}


@router.post(
    "/get_event_log/",
    response=ReportResponse,
    summary="이벤트 발생 로그 조회",
    description="조건에 맞는 이벤트 발생 로그를 반환합니다.",
)
def get_event_log(request, payload: ReportRequest):
    try:
        items, total_count = select_event_occurrences(payload)
        return {
            "items": items,
            "total_count": total_count,
            "page": payload.page,
            "page_size": payload.page_size,
        }
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception:
        raise HttpError(500, "Failed to fetch event log.")


@router.post(
    "/select_simple_event_log/",
    response=list[SimpleEventLogCount],
    summary="이벤트 발생 로그 간단 조회",
    description="카메라별 이벤트 타입 카운트를 반환합니다.",
)
def select_simple_event_log_api(request, payload: SimpleEventLogRequest):
    try:
        print(f"[select_simple_event_log] payload={payload.dict()}")
        results = select_simple_event_log(payload)
        print(f"[select_simple_event_log] result_count={len(results)}")
        print(f"[select_simple_event_log] results={[item.dict() for item in results]}")
        return results
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception:
        raise HttpError(500, "Failed to fetch simple event log.")


@router.delete(
    "/delete_event_log/",
    summary="이벤트 발생 로그 삭제",
    description="지정된 카메라/이벤트 타입 조건에 맞는 로그를 삭제합니다.",
)
def delete_event_log(request, payload: DeleteEventLogRequest):
    try:
        deleted = delete_event_occurrences(payload)
        return {"message": "Success", "deleted": deleted}
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception:
        raise HttpError(500, "Failed to delete event log.")


@router.post(
    "/count_event_log/",
    response=EventLogCountResponse,
    summary="이벤트 발생 로그 삭제 대상 건수 조회",
    description="삭제 조건과 동일한 필터를 적용해 삭제 대상 건수를 반환합니다.",
)
def count_event_log(request, payload: DeleteEventLogRequest):
    try:
        count = count_event_occurrences(payload)
        return {"count": count}
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception:
        raise HttpError(500, "Failed to count event log.")


@router.post(
    "/select_evt_infos/",
    response=list[EventInfo],
    summary="이벤트 목록 조회",
    description="등록된 이벤트 설정 목록을 조회합니다.",
)
def select_event_infos(request):
    _, rows = select_event_info_table()
    return rows


@router.post(
    "/select_evt_types/",
    response=list[EventType],
    summary="이벤트 타입 목록 조회",
    description="등록된 이벤트 타입 목록을 조회합니다.",
)
def select_event_types(request):
    _, rows = select_event_type_table()
    return rows
