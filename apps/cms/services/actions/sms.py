"""Service helpers for managing SMS contact information."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from django.db import transaction

from apps.cms.models import SMSInfoTable
from apps.cms.schemas import SMSInfo

logger = logging.getLogger(__name__)


def _normalize(value: Optional[str]) -> Optional[str]:
    trimmed = (value or "").strip()
    return trimmed or None


def _has_any_value(fields: dict) -> bool:
    return any(fields.values())


def _prepare_objects(infos: List[SMSInfo]) -> List[SMSInfoTable]:
    objects: List[SMSInfoTable] = []
    for info in infos or []:
        fields = {
            "user_name": _normalize(info.name),
            "ph_num": _normalize(info.ph_num),
            "department": _normalize(info.department),
            "title": _normalize(info.title),
        }
        if not _has_any_value(fields):
            continue
        objects.append(SMSInfoTable(**fields))
    return objects


def select_sms_info_table() -> Tuple[bool, List[SMSInfo]]:
    """Fetches the SMS info rows, ordered by name to mimic the legacy query."""
    try:
        rows = (
            SMSInfoTable.objects.order_by("user_name", "ph_num")
            .values("user_name", "ph_num", "department", "title")
        )
        result = [
            SMSInfo(
                name=row.get("user_name") or "",
                ph_num=row.get("ph_num") or "",
                department=row.get("department") or "",
                title=row.get("title") or "",
            )
            for row in rows
        ]
        return True, result
    except Exception:
        logger.exception("Failed to select SMS info rows.")
        return False, []


def delete_sms_table() -> bool:
    """Clears the SMS contact table."""
    try:
        SMSInfoTable.objects.all().delete()
        return True
    except Exception:
        logger.exception("Failed to delete SMS info rows.")
        return False


def insert_sms_infos(infos: List[SMSInfo]) -> bool:
    """Bulk inserts the provided contacts."""
    try:
        objects = _prepare_objects(infos)
        if not objects:
            # Treat empty payload as a no-op success just like the legacy flow.
            return True
        with transaction.atomic():
            SMSInfoTable.objects.bulk_create(objects)
        return True
    except Exception:
        logger.exception("Failed to insert SMS info rows.")
        return False


def replace_sms_infos(infos: List[SMSInfo]) -> Tuple[bool, List[SMSInfo]]:
    """
    Mimics the legacy flow:
    1) delete every row,
    2) insert the provided contacts,
    3) return the refreshed table contents.
    """
    try:
        with transaction.atomic():
            SMSInfoTable.objects.all().delete()
            objects = _prepare_objects(infos)
            if objects:
                SMSInfoTable.objects.bulk_create(objects)
        return select_sms_info_table()
    except Exception:
        logger.exception("Failed to replace SMS info rows.")
        return False, []
