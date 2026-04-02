"""Background workers reporting CMS status to the PMS server."""

from __future__ import annotations

import logging
import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Callable, Optional

import requests
from django.conf import settings

from apps.pms.utils import (
    build_endpoint_url,
    build_service_status_payload,
    resolve_setting,
)

logger = logging.getLogger("pms.status")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

logger.setLevel(logging.INFO if getattr(settings, "DEBUG", False) else logging.WARNING)


@dataclass(slots=True)
class CmsPmsConfig:
    """Configuration holder for PMS communication."""

    pms_ip: str
    pms_port: str
    company_name: str
    cms_id: str
    status_interval_seconds: int
    cms_start_endpoint: str
    cms_status_endpoint: str

    @classmethod
    def from_settings(cls) -> "CmsPmsConfig":
        ip = resolve_setting("PMS_IP", os.getenv("PMS_IP", "127.0.0.1"))
        port = str(resolve_setting("PMS_PORT", os.getenv("PMS_PORT", "8080")))
        company = resolve_setting("COMPANY_NAME", os.getenv("COMPANY_NAME", "UnknownCompany"))
        cms_id = resolve_setting("CMS_ID", os.getenv("CMS_ID", "UnknownCMS"))

        interval_hours = int(
            resolve_setting(
                "PMS_INTERVAL_HOUR",
                os.getenv("PMS_INTERVAL_HOUR", os.getenv("PMS_STATUS_INTERVAL_HOURS", "1")),
            )
        )
        interval_seconds = max(interval_hours, 1) * 60 * 60

        start_endpoint = resolve_setting(
            "CMS_TO_PMS_CMS_START",
            os.getenv("CMS_TO_PMS_CMS_START", "/api/cms_start"),
        )
        status_endpoint = resolve_setting(
            "CMS_TO_PMS_STATUS",
            os.getenv("CMS_TO_PMS_STATUS", "/api/cms_status"),
        )

        return cls(
            pms_ip=ip,
            pms_port=port,
            company_name=company,
            cms_id=cms_id,
            status_interval_seconds=interval_seconds,
            cms_start_endpoint=start_endpoint,
            cms_status_endpoint=status_endpoint,
        )


class BaseSender:
    """HTTP helper mimicking the .NET sender behaviour."""

    def __init__(
        self,
        config: CmsPmsConfig,
        log: Optional[Callable[[str], None]] = None,
        *,
        debug: bool = False,
    ):
        self.config = config
        self.log = log or (lambda msg: logger.info(msg))
        self.debug = debug

    def _debug_print(self, message: str) -> None:
        if self.debug:
            print(message)

    def _post(self, url: str, payload: dict, name: str) -> tuple[bool, dict]:
        try:
            response = requests.post(url, json=payload, timeout=10)
            info = {
                "status": response.status_code,
                "body": response.text[:200],
                "url": url,
            }
            if response.ok:
                self.log(f"[{name}] request succeeded.")
                return True, info

            self.log(
                f"[{name}] request failed: status={response.status_code}, body={response.text[:200]}"
            )
            return False, info
        except requests.RequestException as exc:
            self.log(f"[{name}] request raised exception: {exc}")
            return False, {"error": str(exc), "url": url}


class CmsStartSender(BaseSender):
    """Sends the CMS start notification to PMS."""

    def send(self) -> bool:
        overall_status, services = build_service_status_payload()
        payload = {
            "company_name": self.config.company_name,
            "cms_id": self.config.cms_id,
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "status": overall_status,
            "services": services,
        }
        url = build_endpoint_url(self.config.pms_ip, self.config.pms_port, self.config.cms_start_endpoint)
        self._debug_print(
            f"[DEBUG] POST {url} payload={payload} (endpoint: CMS_TO_PMS_CMS_START)"
        )
        success, info = self._post(url, payload, "CmsStartSender")
        self._debug_print(
            f"[DEBUG] Response from CMS_TO_PMS_CMS_START: success={success}, info={info}"
        )
        return success


class CmsStatusSender(BaseSender):
    """Periodically reports the CMS status."""

    def __init__(
        self,
        config: CmsPmsConfig,
        status_provider: Optional[Callable[[], dict]] = None,
        log: Optional[Callable[[str], None]] = None,
        *,
        debug: bool = False,
    ) -> None:
        super().__init__(config, log, debug=debug)
        self.status_provider = status_provider or (lambda: {})

    def send(self) -> bool:
        overall_status, services = build_service_status_payload()
        extra_services = self.status_provider() or {}
        if isinstance(extra_services, dict):
            for key, value in extra_services.items():
                key_str = str(key)
                if key_str in services:
                    continue
                services[key_str] = str(value)
        payload = {
            "company_name": self.config.company_name,
            "cms_id": self.config.cms_id,
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "status": overall_status,
            "services": services,
        }
        url = build_endpoint_url(self.config.pms_ip, self.config.pms_port, self.config.cms_status_endpoint)
        self._debug_print(
            f"[DEBUG] POST {url} payload={payload} (endpoint: CMS_TO_PMS_STATUS)"
        )
        success, info = self._post(url, payload, "CmsStatusSender")
        self._debug_print(
            f"[DEBUG] Response from CMS_TO_PMS_STATUS: success={success}, info={info}"
        )
        return success


class StatusReporter:
    """Creates a background thread that mirrors the .NET StatusReporter behaviour."""

    def __init__(
        self,
        config: CmsPmsConfig,
        log: Optional[Callable[[str], None]] = None,
        status_provider: Optional[Callable[[], dict]] = None,
    ) -> None:
        self.config = config
        self.log = log or (lambda msg: logger.info(msg))
        self._debug_mode = bool(getattr(settings, "DEBUG", False))
        self.start_sender = CmsStartSender(config, self.log, debug=self._debug_mode)
        self.status_sender = CmsStatusSender(
            config,
            status_provider=status_provider,
            log=self.log,
            debug=self._debug_mode,
        )

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def send_cms_start(self) -> bool:
        return self.start_sender.send()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            self.log("[StatusReporter] already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="PMSStatusReporter", daemon=True
        )
        self._thread.start()
        self.log("[StatusReporter] background reporting thread started")
        if self._debug_mode:
            self.log("[StatusReporter] DEBUG mode detected; PMS sync loop is running continuously.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self.log("[StatusReporter] stopped")

    def _run_loop(self) -> None:
        interval = 5 if self._debug_mode else max(self.config.status_interval_seconds, 60)
        initial_delay = min(5, interval)
        interval = 5
        if initial_delay and self._stop_event.wait(initial_delay):
            return

        while not self._stop_event.wait(interval):
            if self._debug_mode:
                self.log("[StatusReporter] sending periodic CMS status update")
            self.status_sender.send()


_status_reporter: Optional[StatusReporter] = None
_reporter_lock = threading.Lock()


def start_status_reporter(status_provider: Optional[Callable[[], dict]] = None) -> Optional[StatusReporter]:
    """Initialize the status reporter once per process."""

    if not resolve_setting("PMS_STATUS_REPORTING_ENABLED", True):
        logger.info("[StatusReporter] disabled by configuration")
        return None

    run_main_flag = os.environ.get("RUN_MAIN")
    runserver_command = any("runserver" in arg for arg in sys.argv)
    if runserver_command and run_main_flag != "true":
        return None

    global _status_reporter
    if _status_reporter is not None:
        return _status_reporter

    with _reporter_lock:
        if _status_reporter is not None:
            return _status_reporter

        config = CmsPmsConfig.from_settings()
        reporter = StatusReporter(config, status_provider=status_provider)
        _status_reporter = reporter
        try:
            reporter.send_cms_start()
            reporter.start()
        except Exception:
            _status_reporter = None
            raise
        logger.info("[StatusReporter] PMS reporting started")
        return reporter


def stop_status_reporter() -> None:
    global _status_reporter
    if _status_reporter is None:
        return

    with _reporter_lock:
        if _status_reporter is None:
            return
        _status_reporter.stop()
        _status_reporter = None
