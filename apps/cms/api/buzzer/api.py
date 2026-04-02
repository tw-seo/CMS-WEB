from ninja import Router
from ninja.errors import HttpError
from apps.cms.schemas import ApplyBuzzerInfosIn, BuzzerInfo
from apps.cms.schemas import All_Info_Dto
from apps.cms.api.api import build_all_info
from apps.cms.services.actions.buzzer import (
    select_buzzer_info_table,
    delete_buzzer_info,
    insert_buzzer_infos,
    modify_buzzer_info,
)
from apps.cms.services.actions.interlock import (
    delete_buzzer_associated_remaining_interlock_info,
)
from apps.cms.services.workers.viewer_notifier import (
    notify_viewer_account_info_change,
    notify_viewer_all_info_update,
)


router = Router(tags=["Buzzer"])

def _notify_viewer_all(reason: str) -> None:
    try:
        notify_viewer_all_info_update(reason)
        notify_viewer_account_info_change(reason)
    except Exception as exc:
        print(f"[viewer-notify][buzzer] failed ({reason}): {exc}")


@router.post(
    "/apply_buzzer_infos/",
    response=All_Info_Dto,
    summary="buzzer 적용 버튼 동작",
    description="입력: buzzer_infos(배열), delete_keys(배열). 출력: 적용 결과(배열).",
)
def apply_buzzer_infos(request, payload: ApplyBuzzerInfosIn):

    delete_keys = [(k or "").strip() for k in payload.delete_keys if (k or "").strip()]

    new_items = [
        info for info in payload.buzzer_infos if not (info.buzzer_key or "").strip()
    ]
    if delete_keys:
        delete_buzzer_info(delete_keys)
        delete_buzzer_associated_remaining_interlock_info(delete_keys)
    if new_items:
        insert_buzzer_infos(new_items)
    _notify_viewer_all("buzzer_apply")
    return build_all_info()


@router.post(
    "/modify_buzzer_info/",
    response=list[BuzzerInfo],
    summary="buzzer 수정 버튼 동작",
    description="입력: BuzzerInfo. 출력: 수정 이후 전체 목록.",
)
def modify_buzzer_infos(request, payload: BuzzerInfo):
    key = (payload.buzzer_key or "").strip()
    if not key:
        raise HttpError(400, "buzzer_key is required.")

    name = (payload.buzzer_name or "").strip() or "empty"
    location = (payload.buzzer_location or "").strip() or "empty"
    broker = (payload.buzzer_brocker or "").strip()
    topic = (payload.buzzer_topic or "").strip()

    try:
        buzzer_time = int(payload.buzzer_time or 0)
    except (TypeError, ValueError):
        buzzer_time = 0

    if buzzer_time <= 0:
        buzzer_time = 10
    if buzzer_time > 1000:
        buzzer_time = 1000

    sanitized = BuzzerInfo(
        buzzer_key=key,
        buzzer_name=name,
        buzzer_location=location,
        buzzer_time=buzzer_time,
        buzzer_brocker=broker,
        buzzer_topic=topic,
    )

    if not modify_buzzer_info(sanitized):
        raise HttpError(404, "Buzzer info not found.")

    _notify_viewer_all("buzzer_modify")
    _, rows = select_buzzer_info_table()
    return rows


@router.post(
    "/select_buzzer_infos/",
    response=list[BuzzerInfo],
    summary="buzzer 목록 조회",
    description="등록된 부저 설정 목록을 조회합니다.",
)
def select_buzzer_infos(request):
    _, rows = select_buzzer_info_table()
    return rows

