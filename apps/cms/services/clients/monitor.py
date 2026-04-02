from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import requests


class ServiceMonitorError(RuntimeError):
    """Raised when a monitored service reports a failure."""


@dataclass(slots=True)
class ServiceEndpoint:
    name: str
    ip: str
    port: str
    path: str = "/API/is_running"
    method: str = "POST"

    def url(self) -> str:
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        return f"http://{self.ip}:{self.port}{path}"


class ServiceMonitorClient:
    def __init__(self, endpoint: ServiceEndpoint, *, timeout: float = 5.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.logger = logging.getLogger("cms.service_monitor.client")

    def check_is_running(self) -> bool:
        url = self.endpoint.url()
        method = (self.endpoint.method or "GET").upper()
        try:
            if method == "POST":
                response = requests.post(url, timeout=self.timeout)
            else:
                response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ServiceMonitorError(f"{self.endpoint.name} health check failed: {exc}") from exc

        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = response.text.strip()

        if isinstance(payload, list):
            if self.endpoint.name.lower() == "dl":
                self._handle_dl_rtsp_payload(payload)
                return True
            raise ServiceMonitorError(
                f"{self.endpoint.name} health check returned unexpected payload: {payload!r}"
            )

        if isinstance(payload, bool):
            return payload
        if isinstance(payload, dict):
            # Accept keys like "is_running" or "running"
            for key in ("is_running", "running", "status"):
                if key in payload:
                    value = payload[key]
                    if isinstance(value, bool):
                        return value
                    if isinstance(value, str):
                        lowered = value.lower()
                        if lowered in {"true", "1", "ok", "running"}:
                            return True
                        if lowered in {"false", "0", "stop", "stopped"}:
                            return False
        if isinstance(payload, str):
            lowered = payload.lower()
            if lowered in {"true", "1", "ok", "running"}:
                return True
            if lowered in {"false", "0", "stop", "stopped"}:
                return False

        raise ServiceMonitorError(
            f"{self.endpoint.name} health check returned unexpected payload: {payload!r}"
        )

    def _handle_dl_rtsp_payload(self, payload: list[Any]) -> None:
        items: list[dict[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            camera_key = item.get("camera_key") or item.get("camera_info_key") or ""
            dl_rtsp = item.get("dl_rtsp") or ""
            camera_key = str(camera_key).strip()
            dl_rtsp = str(dl_rtsp).strip()
            if not camera_key or not dl_rtsp:
                continue
            items.append({"camera_key": camera_key, "dl_rtsp": dl_rtsp})

        if not items:
            self.logger.info("[ServiceMonitor] DL is_running payload empty")
            return

        try:
            from apps.mediamtx.services.registry import register_dl_rtsp_bulk

            register_dl_rtsp_bulk(items)
        except Exception as exc:
            self.logger.warning("[ServiceMonitor] DL RTSP sync failed: %s", exc)


__all__ = [
    "ServiceMonitorClient",
    "ServiceMonitorError",
    "ServiceEndpoint",
]
