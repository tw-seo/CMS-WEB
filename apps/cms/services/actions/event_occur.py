from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Sequence

from django.db import transaction
from django.db.models import Count, Q

from apps.cms.models import CameraInfo, EventOccurTable
from apps.cms.schemas import (
    DeleteEventLogRequest,
    EventOccurIn,
    ReportInfo,
    ReportRequest,
    SimpleEventLogCount,
    SimpleEventLogRequest,
)

UTC = timezone.utc
KST = timezone(timedelta(hours=9))


def _now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        # Backward compatibility: old clients sent timezone-free KST strings.
        return value.replace(tzinfo=KST).astimezone(UTC).replace(tzinfo=None)
    return value.astimezone(UTC).replace(tzinfo=None)


def _utc_iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        aware = value.replace(tzinfo=UTC)
    else:
        aware = value.astimezone(UTC)
    return aware.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None

    s = str(value).strip()

    if s.isdigit():
        try:
            return datetime.fromtimestamp(int(s), tz=UTC).replace(tzinfo=None)
        except Exception:
            return None

    try:
        parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return _to_utc_naive(parsed)
    except Exception:
        return None


def _normalize_event_occurrence(item: EventOccurIn) -> dict[str, Any]:
    occurred_at = _parse_time(getattr(item, "event_occur_time", None)) or _now_utc_naive()
    return {
        "event_occur_time": occurred_at,
        "event_register_key": (item.event_register_key or "").strip() or None,
        "camera_info_key": (item.camera_info_key or "").strip() or "",
        "event_type_key": (item.event_type_key or "").strip() or "",
        "object_class": (item.object_class or "").strip() or None,
        "img_path": (item.img_path or "").strip() or None,
        "event_occur_point": list(item.event_occur_point or []),
    }


def normalize_event_occurrences(items: Sequence[EventOccurIn]) -> List[dict[str, Any]]:
    return [_normalize_event_occurrence(item) for item in items]


def serialize_normalized_event_occurrences(
    normalized_items: Sequence[dict[str, Any]],
) -> List[dict[str, Any]]:
    serialized: List[dict[str, Any]] = []
    for item in normalized_items:
        serialized.append(
            {
                "event_register_key": item["event_register_key"],
                "camera_info_key": item["camera_info_key"],
                "event_type_key": item["event_type_key"],
                "object_class": item["object_class"],
                "img_path": item["img_path"],
                # Always emit UTC for inter-service consistency.
                "event_occur_time": _utc_iso_z(item["event_occur_time"]),
                "event_occur_point": list(item["event_occur_point"] or []),
            }
        )
    return serialized


def _apply_occur_time_range(queryset, start: datetime | None, end: datetime | None, end_raw: str):
    if start:
        queryset = queryset.filter(event_occur_time__gte=start)

    if end:
        # Date-only / midnight end values are usually sent by date pickers.
        # Interpret them as an inclusive day range by using next-day exclusive.
        is_epoch = end_raw.isdigit()
        is_midnight = (
            end.hour == 0
            and end.minute == 0
            and end.second == 0
            and end.microsecond == 0
        )
        if not is_epoch and is_midnight:
            queryset = queryset.filter(event_occur_time__lt=end + timedelta(days=1))
        else:
            queryset = queryset.filter(event_occur_time__lte=end)

    return queryset


def save_event_occurrences(
    items: Sequence[EventOccurIn],
    normalized_items: Sequence[dict[str, Any]] | None = None,
) -> int:
    if not items:
        return 0

    normalized = (
        list(normalized_items)
        if normalized_items is not None
        else normalize_event_occurrences(items)
    )

    objs: List[EventOccurTable] = []
    for item in normalized:
        objs.append(
            EventOccurTable(
                event_occur_time=item["event_occur_time"],
                event_register_key=item["event_register_key"],
                camera_info_key=item["camera_info_key"],
                event_type_key=item["event_type_key"],
                object_class=item["object_class"],
                img_path=item["img_path"],
                event_occur_point=list(item["event_occur_point"] or []),
            )
        )

    with transaction.atomic():
        EventOccurTable.objects.bulk_create(objs, ignore_conflicts=False)

    return len(objs)


def select_event_occurrences(query: ReportRequest) -> tuple[List[ReportInfo], int]:
    start_raw = (query.start_date or "").strip()
    end_raw = (query.end_date or "").strip()
    start = _parse_time(start_raw)
    end = _parse_time(end_raw)
    if start_raw and not start:
        raise ValueError("Invalid start_date.")
    if end_raw and not end:
        raise ValueError("Invalid end_date.")

    event_types = [key.strip() for key in (query.event_types or []) if key and key.strip()]
    camera_keys = [
        key.strip() for key in (query.camera_info_keys or []) if key and key.strip()
    ]

    sort_order = (query.sort_order or "").strip().lower()
    if not sort_order:
        sort_order = "latest"
    if sort_order not in ("latest", "oldest"):
        raise ValueError("Invalid sort_order. Use 'latest' or 'oldest'.")

    page_size = query.page_size
    page = query.page
    if page_size <= 0:
        raise ValueError("page_size must be greater than 0.")
    if page <= 0:
        raise ValueError("page must be greater than 0.")

    ordering = ["event_occur_time", "occur_no"]
    if sort_order == "latest":
        ordering = ["-event_occur_time", "-occur_no"]

    queryset = EventOccurTable.objects.all().order_by(*ordering)
    queryset = _apply_occur_time_range(queryset, start, end, end_raw)
    if event_types:
        queryset = queryset.filter(event_type_key__in=event_types)
    if camera_keys:
        queryset = queryset.filter(camera_info_key__in=camera_keys)

    total_count = queryset.count()
    offset = (page - 1) * page_size
    queryset = queryset[offset : offset + page_size]

    camera_name_map = {
        item["camera_info_key"]: item.get("camera_name") or ""
        for item in CameraInfo.objects.filter(
            camera_info_key__in=camera_keys
            if camera_keys
            else queryset.values_list("camera_info_key", flat=True)
        ).values("camera_info_key", "camera_name")
    }

    results: List[ReportInfo] = []
    for row in queryset:
        results.append(
            ReportInfo(
                occur_no=row.occur_no,
                event_register_key=row.event_register_key,
                camera_info_key=row.camera_info_key,
                camera_name=camera_name_map.get(row.camera_info_key, ""),
                event_type_key=row.event_type_key,
                object_class=row.object_class,
                img_path=row.img_path,
                event_occur_time=_utc_iso_z(row.event_occur_time),
                event_occur_point=list(row.event_occur_point or []),
            )
        )
    return results, total_count


def select_simple_event_log(query: SimpleEventLogRequest) -> List[SimpleEventLogCount]:
    start_raw = (query.start_time or "").strip()
    end_raw = (query.end_time or "").strip()
    start = _parse_time(start_raw)
    end = _parse_time(end_raw)
    if start_raw and not start:
        raise ValueError("Invalid start_time.")
    if end_raw and not end:
        raise ValueError("Invalid end_time.")

    cam_info_key = (query.cam_info_key or "").strip()

    queryset = EventOccurTable.objects.all()
    if cam_info_key:
        queryset = queryset.filter(camera_info_key=cam_info_key)
    queryset = _apply_occur_time_range(queryset, start, end, end_raw)

    queryset = (
        queryset.values("camera_info_key")
        .annotate(
            invasion_count=Count("occur_no", filter=Q(event_type_key="E2024-11-19-001")),
            loiter_count=Count("occur_no", filter=Q(event_type_key="E2024-11-19-002")),
            fire_count=Count("occur_no", filter=Q(event_type_key="E2024-11-19-003")),
            fall_count=Count("occur_no", filter=Q(event_type_key="E2025-01-20-001")),
            hit_count=Count("occur_no", filter=Q(event_type_key="E2025-07-29-001")),
            jam_count=Count("occur_no", filter=Q(event_type_key="E2025-07-29-002")),
        )
        .order_by("camera_info_key")
    )

    results: List[SimpleEventLogCount] = []
    for row in queryset:
        results.append(
            SimpleEventLogCount(
                camera_info_key=row.get("camera_info_key"),
                invasion_count=row.get("invasion_count", 0),
                loiter_count=row.get("loiter_count", 0),
                fire_count=row.get("fire_count", 0),
                fall_count=row.get("fall_count", 0),
                hit_count=row.get("hit_count", 0),
                jam_count=row.get("jam_count", 0),
            )
        )
    return results


def _normalize_multi_filter(value) -> tuple[bool, List[str]]:
    if value is None:
        return False, []

    if isinstance(value, str):
        text = value.strip()
        if text == "*":
            return True, []
        return False, [text] if text else []

    items: List[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        if text == "*":
            return True, []
        items.append(text)
    return False, items


def _build_event_occurrence_filter_queryset(query: DeleteEventLogRequest):
    event_wild, event_list = _normalize_multi_filter(query.event_types)
    camera_wild, camera_list = _normalize_multi_filter(query.camera_info_keys)

    start_raw = (getattr(query, "start_date", "") or "").strip()
    end_raw = (getattr(query, "end_date", "") or "").strip()
    start = _parse_time(start_raw)
    end = _parse_time(end_raw)

    if not event_wild and not event_list:
        raise ValueError("event_types must be '*' or a non-empty list.")
    if not camera_wild and not camera_list:
        raise ValueError("camera_info_keys must be '*' or a non-empty list.")
    if start_raw and not start:
        raise ValueError("Invalid start_date.")
    if end_raw and not end:
        raise ValueError("Invalid end_date.")

    queryset = EventOccurTable.objects.all()
    if not event_wild:
        queryset = queryset.filter(event_type_key__in=event_list)
    if not camera_wild:
        queryset = queryset.filter(camera_info_key__in=camera_list)
    queryset = _apply_occur_time_range(queryset, start, end, end_raw)
    return queryset


def count_event_occurrences(query: DeleteEventLogRequest) -> int:
    queryset = _build_event_occurrence_filter_queryset(query)
    return queryset.count()


def delete_event_occurrences(query: DeleteEventLogRequest) -> int:
    queryset = _build_event_occurrence_filter_queryset(query)
    deleted, _ = queryset.delete()
    return deleted
