from __future__ import annotations

from typing import List, Tuple

from apps.cms.models import EventTypeTable
from apps.cms.schemas import EventType


def select_event_type_table() -> Tuple[bool, List[EventType]]:
    try:
        rows = EventTypeTable.objects.order_by("event_type_key").values(
            "event_type_key",
            "event_type_name",
        )
    except Exception:
        return False, []

    result: List[EventType] = []
    for row in rows:
        result.append(
            EventType(
                event_type_key=row.get("event_type_key"),
                event_type_name=row.get("event_type_name"),
            )
        )

    return bool(result), result
