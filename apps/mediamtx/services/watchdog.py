from __future__ import annotations

import logging
import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger("mediamtx.watchdog")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

logger.setLevel(logging.INFO if getattr(settings, "DEBUG", False) else logging.WARNING)


@dataclass(slots=True)
class MediaMtxWatchdogConfig:
    api_base: str
    health_path: str
    interval_seconds: int
    timeout_seconds: float
    enabled: bool

    @classmethod
    def from_settings(cls) -> "MediaMtxWatchdogConfig":
        cfg = getattr(settings, "MEDIAMTX", {})
        return cls(
            api_base=str(cfg.get("API_BASE", "")).rstrip("/"),
            health_path=str(cfg.get("WATCH_DOG_HEALTH_PATH", "/v3/config/paths/list")),
            interval_seconds=max(5, int(cfg.get("WATCH_DOG_INTERVAL_SECONDS", 30) or 30)),
            timeout_seconds=float(cfg.get("WATCH_DOG_TIMEOUT_SECONDS", 5) or 5),
            enabled=bool(cfg.get("WATCH_DOG_ENABLED", False)),
        )

    def health_url(self) -> str:
        if not self.api_base:
            return ""
        path = self.health_path or "/"
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.api_base}{path}"


_watchdog_worker: Optional["MediaMtxWatchdog"] = None
_watchdog_lock = threading.Lock()

_snapshot_lock = threading.Lock()
_snapshot = {
    "enabled": False,
    "running": False,
    "api_base": None,
    "health_url": None,
    "last_ok": None,
    "last_checked_at": None,
    "last_error": None,
}


def _update_snapshot(**kwargs: object) -> None:
    with _snapshot_lock:
        _snapshot.update(kwargs)


def get_watchdog_snapshot() -> dict[str, object]:
    with _snapshot_lock:
        return dict(_snapshot)


class MediaMtxWatchdog:
    def __init__(self, config: MediaMtxWatchdogConfig) -> None:
        self.config = config
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("[MediaMTXWatchdog] already running")
            return
        if not self.config.api_base:
            logger.warning("[MediaMTXWatchdog] API base not configured; skipping start")
            return

        _update_snapshot(
            running=True,
            api_base=self.config.api_base,
            health_url=self.config.health_url(),
        )
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="MediaMTXWatchdog", daemon=True
        )
        self._thread.start()
        logger.info("[MediaMTXWatchdog] started (interval=%ss)", self.config.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        _update_snapshot(running=False)
        logger.info("[MediaMTXWatchdog] stopped")

    def _run_loop(self) -> None:
        self._check_once()
        while not self._stop_event.wait(self.config.interval_seconds):
            self._check_once()

    def _check_once(self) -> None:
        ok, error = self._probe_api()
        _update_snapshot(
            last_ok=ok,
            last_checked_at=datetime.now(timezone.utc).isoformat(),
            last_error=error,
        )
        if ok:
            return
        if error:
            logger.warning("[MediaMTXWatchdog] health check failed: %s", error)

    def _probe_api(self) -> tuple[bool, Optional[str]]:
        url = self.config.health_url()
        if not url:
            return False, "api_base not configured"
        try:
            response = requests.get(url, timeout=self.config.timeout_seconds)
        except requests.RequestException as exc:
            return False, str(exc)

        if response.status_code >= 500:
            return False, f"status={response.status_code}"
        return True, None

def start_mtx_watchdog() -> Optional[MediaMtxWatchdog]:
    config = MediaMtxWatchdogConfig.from_settings()
    _update_snapshot(
        enabled=config.enabled,
        api_base=config.api_base,
        health_url=config.health_url(),
    )
    if not config.enabled:
        logger.info("[MediaMTXWatchdog] disabled by configuration")
        return None

    runserver_command = any("runserver" in arg for arg in sys.argv)
    run_main_flag = os.environ.get("RUN_MAIN")
    if runserver_command and run_main_flag != "true":
        return None

    global _watchdog_worker
    if _watchdog_worker is not None:
        return _watchdog_worker

    with _watchdog_lock:
        if _watchdog_worker is not None:
            return _watchdog_worker
        worker = MediaMtxWatchdog(config)
        _watchdog_worker = worker
        try:
            worker.start()
        except Exception:
            _watchdog_worker = None
            raise
        return worker


def stop_mtx_watchdog() -> None:
    global _watchdog_worker
    if _watchdog_worker is None:
        return

    with _watchdog_lock:
        if _watchdog_worker is None:
            return
        _watchdog_worker.stop()
        _watchdog_worker = None
