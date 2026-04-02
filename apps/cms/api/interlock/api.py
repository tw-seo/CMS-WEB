from ninja import Router
from ninja.errors import HttpError
from apps.cms.schemas import All_Info_Dto
from apps.cms.api.api import build_all_info

from apps.cms.schemas import ApplyInterlockIn, InterlockInfo
from apps.cms.services.actions.interlock import (
    select_interlock_table,
    insert_interlock_info,
    delete_interlock_info,
)
from apps.cms.services.workers.viewer_notifier import (
    notify_viewer_account_info_change,
    notify_viewer_all_info_update,
)

router = Router(tags=["Interlock"])

def _notify_viewer_all(reason: str) -> None:
    try:
        notify_viewer_all_info_update(reason)
        notify_viewer_account_info_change(reason)
    except Exception as exc:
        print(f"[viewer-notify][interlock] failed ({reason}): {exc}")


@router.post(
    "/apply_interlock_infos/",
    response=All_Info_Dto,
    summary="인터락 적용 버튼 동작",
    description="입력: interlock_infos(배열), delete_keys(배열). 출력: 적용 결과(배열).",
)
def apply_interlock_infos(request, payload: ApplyInterlockIn):
    delete_keys = [(k or "").strip() for k in payload.delete_keys if (k or "").strip()]

    interlock_infos = payload.interlock_infos or []
    new_items = [
        info
        for info in interlock_infos
        if not (getattr(info, "interlock_key", None) or "").strip()
    ]

    if delete_keys and not delete_interlock_info(delete_keys):
        raise HttpError(404, "Some interlock keys were not found for deletion.")

    if new_items and not insert_interlock_info(new_items):
        raise HttpError(400, "No interlock records were inserted.")

    _notify_viewer_all("interlock_apply")
    return build_all_info()


@router.post(
    "/select_interlock_infos/",
    response=list[InterlockInfo],
    summary="인터락 목록 조회",
    description="등록된 인터락 설정 목록을 조회합니다.",
)
def select_interlock_infos(request):
    _, rows = select_interlock_table()
    return rows

