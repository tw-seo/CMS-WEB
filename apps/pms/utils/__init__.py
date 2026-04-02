from __future__ import annotations

from typing import Optional

from django.conf import settings

from apps.cms.services.workers.service_monitor import get_service_status_snapshot


def resolve_setting(name: str, default):
    """Fetch a setting with a fallback to env defaults."""

    return getattr(settings, name, default)


def build_endpoint_url(ip: str, port: str, endpoint: str) -> str:
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"http://{ip}:{port}{endpoint}"


def build_service_status_payload() -> tuple[str, dict[str, str]]:
    snapshot = get_service_status_snapshot()

    def translate(value: Optional[bool]) -> str:
        if value is True:
            return "running"
        if value is False:
            return "stopped"
        return "unknown"

    viewer_status = translate(snapshot.get("viewer"))
    dl_status = translate(snapshot.get("dl"))

    overall_status = "HEALTHY" if viewer_status == "running" and dl_status == "running" else "DEGRADED"
    services = {
        "GUI": viewer_status,
        "DL": dl_status,
    }
    return overall_status, services


__all__ = ["resolve_setting", "build_endpoint_url", "build_service_status_payload"]
