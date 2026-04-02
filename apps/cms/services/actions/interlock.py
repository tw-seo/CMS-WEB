from __future__ import annotations

from datetime import datetime
from typing import List, Sequence, Tuple
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.db import transaction

from apps.cms.models import (
    BuzzerInfoTable,
    BuzzerInterlockTable,
    CameraInfo,
)
from apps.cms.schemas import InterlockInfo


KST = ZoneInfo("Asia/Seoul")


def _trim(value: str | None) -> str:
    return (value or "").strip()


def _with_default(value: str | None, fallback: str) -> str:
    text = _trim(value)
    return text if text else fallback


def select_interlock_table() -> Tuple[bool, List[InterlockInfo]]:
    rows = (
        BuzzerInterlockTable.objects.order_by("interlock_info_key")
        .values(
            "interlock_info_key",
            "interlock_name",
            "buzzer_info_key",
            "buzzer_name",
            "camera_info_key",
            "camera_name",
        )
    )

    result: List[InterlockInfo] = []
    for row in rows:
        result.append(
            InterlockInfo(
                interlock_key=_trim(row.get("interlock_info_key")),
                interlock_name=_trim(row.get("interlock_name")),
                buzzer_key=_trim(row.get("buzzer_info_key")),
                buzzername=_trim(row.get("buzzer_name")),
                cam_key=_trim(row.get("camera_info_key")),
                cam_name=_trim(row.get("camera_name")),
            )
        )

    return True, result


def get_interlock_count() -> int:
    try:
        return BuzzerInterlockTable.objects.count()
    except Exception:
        return -1


def insert_interlock_info(infos: Sequence[InterlockInfo]) -> bool:
    if not infos:
        return False

    ts_sec = int(datetime.now(KST).timestamp())
    objects_to_create: List[BuzzerInterlockTable] = []

    for idx, info in enumerate(infos):
        buzzer_key = _trim(info.buzzer_key)
        camera_key = _trim(info.cam_key)
        if not buzzer_key or not camera_key:
            continue

        generated_key = f"BI{ts_sec}{idx}"
        objects_to_create.append(
            BuzzerInterlockTable(
                interlock_info_key=generated_key,
                interlock_name=_with_default(info.interlock_name, "empty"),
                buzzer_info_key=buzzer_key,
                buzzer_name=_with_default(info.buzzername, "empty"),
                camera_info_key=camera_key,
                camera_name=_with_default(info.cam_name, "empty"),
            )
        )

    if not objects_to_create:
        return False

    with transaction.atomic():
        BuzzerInterlockTable.objects.bulk_create(objects_to_create, ignore_conflicts=False)

    return True


def delete_interlock_info(keys: Sequence[str]) -> bool:
    valid_keys = [_trim(key) for key in keys or [] if _trim(key)]
    if not valid_keys:
        return False

    with transaction.atomic():
        deleted_count, _ = BuzzerInterlockTable.objects.filter(
            interlock_info_key__in=valid_keys
        ).delete()

    return deleted_count > 0


def populate_interlock_table() -> bool:
    try:
        cameras = list(
            CameraInfo.objects.order_by("camera_info_key").values_list(
                "camera_info_key", "camera_name"
            )
        )
    except Exception:
        return False

    try:
        buzzers = list(
            BuzzerInfoTable.objects.order_by("buzzer_info_key").values_list(
                "buzzer_info_key", "buzzer_name"
            )
        )
    except Exception:
        return False

    if not cameras or not buzzers:
        return False

    counter = 1
    objects_to_create: List[BuzzerInterlockTable] = []

    for camera_key, camera_name in cameras:
        for buzzer_key, buzzer_name in buzzers:
            objects_to_create.append(
                BuzzerInterlockTable(
                    interlock_info_key=str(uuid4()),
                    interlock_name=str(counter),
                    buzzer_info_key=_trim(buzzer_key),
                    buzzer_name=_with_default(buzzer_name, "empty"),
                    camera_info_key=_trim(camera_key),
                    camera_name=_with_default(camera_name, "empty"),
                )
            )
            counter += 1

    with transaction.atomic():
        BuzzerInterlockTable.objects.bulk_create(objects_to_create, ignore_conflicts=False)

    return True


def delete_buzzer_associated_remaining_interlock_info(buzzer_keys: Sequence[str]) -> None:
    valid_keys = [_trim(key) for key in buzzer_keys or [] if _trim(key)]
    if not valid_keys:
        return

    with transaction.atomic():
        BuzzerInterlockTable.objects.filter(buzzer_info_key__in=valid_keys).delete()
