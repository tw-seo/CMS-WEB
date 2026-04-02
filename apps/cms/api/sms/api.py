from __future__ import annotations

from typing import List, Optional

from ninja import Body, Router, Schema
from ninja.errors import HttpError

from apps.cms.schemas import SMSInfo
from apps.cms.services.actions.sms import replace_sms_infos, select_sms_info_table

router = Router(tags=["SMS"])


class TestSMSResponse(Schema):
    message: str
    receivedCount: int


@router.post(
    "/insert_sms_infos/",
    response=list[SMSInfo],
    summary="SMS 연락처 일괄 적용",
    description="기존 연락처를 모두 삭제한 뒤 전달된 목록으로 대체합니다.",
)
def insert_sms_infos(request, payload: List[SMSInfo] = Body(...)):
    success, rows = replace_sms_infos(payload or [])
    if not success:
        raise HttpError(500, "Failed to update SMS info table.")
    return rows


@router.post(
    "/test_sms/",
    response=TestSMSResponse,
    summary="SMS 발송 테스트",
    description="전달된 목록의 건수를 반환합니다. 실제 발송 로직은 별도 연동이 필요합니다.",
)
def test_sms(request, payload: Optional[List[SMSInfo]] = Body(default=None)):
    count = len(payload or [])
    return TestSMSResponse(message="데이터 수신 완료", receivedCount=count)


@router.get(
    "/sms_infos/",
    response=list[SMSInfo],
    summary="SMS 연락처 조회",
    description="등록된 연락처 목록을 이름 순으로 반환합니다.",
)
def get_sms_infos(request):
    success, rows = select_sms_info_table()
    if not success:
        raise HttpError(500, "Failed to load SMS info table.")
    return rows
