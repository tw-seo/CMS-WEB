"""Background worker that polls viewer/DL health endpoints."""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Iterable, Optional

from django.conf import settings

from ..clients.monitor import ServiceEndpoint, ServiceMonitorClient, ServiceMonitorError
_monitor_worker: Optional[ServiceMonitorWorker] = None
_monitor_lock = threading.Lock()

_service_status_lock = threading.Lock()
_service_status_snapshot: dict[str, Optional[bool]] = {"viewer": None, "dl": None}

logger = logging.getLogger("cms.service_monitor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

if getattr(settings, "DEBUG", False):
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.WARNING)


def _build_endpoints() -> list[ServiceEndpoint]:
    endpoints: list[ServiceEndpoint] = []

    viewer_ip = getattr(settings, "VIEWER_IP", None)
    viewer_port = getattr(settings, "VIEWER_PORT", None)
    viewer_path = getattr(settings, "VIEWER_HEALTH_PATH", "/API/is_running")
    viewer_method = getattr(settings, "VIEWER_HEALTH_METHOD", "POST").upper()
    if viewer_ip and viewer_port:
        endpoints.append(
            ServiceEndpoint(
                name="viewer",
                ip=str(viewer_ip),
                port=str(viewer_port),
                path=viewer_path,
                method=viewer_method,
            )
        )

    dl_ip = getattr(settings, "DL_IP", None)
    dl_port = getattr(settings, "DL_PORT", None)
    dl_path = getattr(settings, "DL_HEALTH_PATH", "/API/is_running")
    dl_method = getattr(settings, "DL_HEALTH_METHOD", "POST").upper()
    if dl_ip and dl_port:
        endpoints.append(
            ServiceEndpoint(
                name="dl",
                ip=str(dl_ip),
                port=str(dl_port),
                path=dl_path,
                method=dl_method,
            )
        )

    return endpoints


class ServiceMonitorWorker:
    def __init__(
        self,
        endpoints: Iterable[ServiceEndpoint],
        *,
        interval_seconds: int = 60,
        debug: bool = False,
    ) -> None:
        self.endpoints = list(endpoints)
        self.clients = [ServiceMonitorClient(endpoint) for endpoint in self.endpoints]
        self.interval_seconds = max(5, int(interval_seconds or 60))
        self.debug = debug

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("[ServiceMonitor] already running")
            return

        if not self.endpoints:
            logger.info("[ServiceMonitor] no endpoints configured; skipping start")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="ServiceMonitor", daemon=True)
        self._thread.start()
        logger.info(
            "[ServiceMonitor] started with endpoints: %s",
            ", ".join(endpoint.url() for endpoint in self.endpoints),
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("[ServiceMonitor] stopped")

    def _run_loop(self) -> None:
        self._check_once()
        while not self._stop_event.wait(self.interval_seconds):
            self._check_once()

    def _check_once(self) -> None:
        for endpoint, client in zip(self.endpoints, self.clients):
            try:
                running = client.check_is_running()
                update_service_status(endpoint.name, running)
            except ServiceMonitorError as exc:
                update_service_status(endpoint.name, False)
                logger.error("[ServiceMonitor] %s", exc)
                continue

            if running:
                if self.debug:
                    logger.info(
                        "[ServiceMonitor] %s running (%s)", endpoint.name, endpoint.url()
                    )
            else:
                logger.error(
                    "[ServiceMonitor] %s reported not running (payload=false) at %s",
                    endpoint.name,
                    endpoint.url(),
                )

def start_service_monitor() -> Optional[ServiceMonitorWorker]:
    if not getattr(settings, "SERVICE_MONITOR_ENABLED", True):
        logger.info("[ServiceMonitor] disabled by configuration")
        return None

    runserver_command = any("runserver" in arg for arg in sys.argv)
    run_main_flag = os.environ.get("RUN_MAIN")
    if runserver_command and run_main_flag != "true":
        return None

    global _monitor_worker
    if _monitor_worker is not None:
        return _monitor_worker

    with _monitor_lock:
        if _monitor_worker is not None:
            return _monitor_worker

        endpoints = _build_endpoints()
        if not endpoints:
            logger.info("[ServiceMonitor] no endpoints detected; worker not started")
            return None

        interval = getattr(settings, "SERVICE_MONITOR_INTERVAL_SECONDS", 60)
        debug = bool(getattr(settings, "DEBUG", False))
        worker = ServiceMonitorWorker(endpoints, interval_seconds=interval, debug=debug)
        _monitor_worker = worker
        try:
            worker.start()
        except Exception:
            _monitor_worker = None
            raise
        return worker


def stop_service_monitor() -> None:
    global _monitor_worker
    if _monitor_worker is None:
        return

    with _monitor_lock:
        if _monitor_worker is None:
            return
        _monitor_worker.stop()
        _monitor_worker = None


def _normalize_service_name(name: str) -> str:
    return name.lower()


def update_service_status(name: str, running: Optional[bool]) -> None:
    normalized = _normalize_service_name(name)
    with _service_status_lock:
        _service_status_snapshot[normalized] = running


def get_service_status_snapshot() -> dict[str, Optional[bool]]:
    with _service_status_lock:
        return dict(_service_status_snapshot)
