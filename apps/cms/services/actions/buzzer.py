# apps/cms/services/buzzer.py
from __future__ import annotations
from typing import List, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo
from django.db import transaction
from apps.cms.models import BuzzerInfoTable
from apps.cms.schemas import BuzzerInfo  # b6_i4_* 필드 사용

KST = ZoneInfo("Asia/Seoul")


def _sanitize(info: BuzzerInfo) -> dict:
    name = (info.buzzer_name or "").strip() or "empty"
    location = (info.buzzer_location or "").strip() or "empty"
    broker = (info.buzzer_brocker or "").strip()  # 스키마는 brocker, 컬럼은 broker
    topic = (info.buzzer_topic or "").strip()
    buz_time = int(info.buzzer_time or 0)
    if buz_time <= 0:
        buz_time = 10
    if buz_time > 1000:
        buz_time = 1000
    return dict(
        buzzer_name=name,
        buzzer_location=location,
        buzzer_broker=broker,
        buzzer_topic=topic,
        buzzer_time=buz_time,
    )


def modify_buzzer_info(info: BuzzerInfo) -> bool:
    key = (info.buzzer_key or "").strip()
    if not key:
        return False

    fields = _sanitize(info)
    # WHERE buzzer_info_key = @key
    updated = BuzzerInfoTable.objects.filter(pk=key).update(**fields)
    return updated > 0


def insert_buzzer_infos(infos: List[BuzzerInfo]) -> bool:
    if not infos:
        return False

    ts_sec = int(datetime.now(KST).timestamp())  # C#과 동일하게 초 단위
    objs: List[BuzzerInfoTable] = []

    for i, info in enumerate(infos, start=1):
        key = f"B{ts_sec}-{i}"
        fields = _sanitize(info)
        objs.append(BuzzerInfoTable(
            buzzer_info_key=key,
            **fields,
        ))

    # 원샷으로 INSERT (PK 충돌 시 예외 → 전체 롤백)
    with transaction.atomic():
        BuzzerInfoTable.objects.bulk_create(objs, ignore_conflicts=False)

    return True

def delete_buzzer_info(keys: List[str]) -> bool:
    if not keys:
        return False
    with transaction.atomic():
        deleted_count, _ = BuzzerInfoTable.objects.filter(
            buzzer_info_key__in=keys
        ).delete()
    return deleted_count > 0


def select_buzzer_info_table() -> Tuple[bool, List[BuzzerInfo]]:
    rows = (
        BuzzerInfoTable.objects
        .order_by("buzzer_info_key")
        .values(
            "buzzer_info_key",
            "buzzer_name",
            "buzzer_location",
            "buzzer_time",
            "buzzer_broker",   # 모델 컬럼명은 broker
            "buzzer_topic",
        )
    )

    result: List[BuzzerInfo] = []
    for r in rows:
        result.append(BuzzerInfo(
            buzzer_key=r["buzzer_info_key"] or "",
            buzzer_name=(r["buzzer_name"] or ""),
            buzzer_location=(r["buzzer_location"] or ""),
            buzzer_time=int(r["buzzer_time"] or 0),
            # 스키마 필드명은 brocker로 정의되어 있음(오타 유지)
            buzzer_brocker=(r["buzzer_broker"] or ""),
            buzzer_topic=(r["buzzer_topic"] or ""),
        ))

    return True, result