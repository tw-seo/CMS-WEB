from __future__ import annotations

import json
import logging
import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings

from apps.cms.services.clients.notifier_base import HttpJsonNotifierBase, NotifyTarget
from apps.cms.services.workers.viewer_realtime import (
    broadcast_viewer_account_info_change,
    broadcast_viewer_all_info_update,
    broadcast_viewer_evt_occur,
    broadcast_viewer_mtx_info_update,
)

logger = logging.getLogger("cms.viewer_notifier")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

logger.setLevel(logging.INFO if getattr(settings, "DEBUG", False) else logging.WARNING)


@dataclass(slots=True)
class ViewerCmsUpdateConfig:
    enabled: bool
    ip: str
    port: str
    viewer_targets_raw: str
    lite_viewer_targets_raw: str
    mtx_update_path: str
    all_info_update_path: str
    evt_occur_path: str
    account_info_change_path: str
    timeout_seconds: float
    initial_delay_seconds: int
    auto_discovery_enabled: bool
    discovery_lookback_minutes: int

    @classmethod
    def from_settings(cls) -> "ViewerCmsUpdateConfig":
        return cls(
            enabled=bool(getattr(settings, "VIEWER_CMS_UPDATE_ENABLED", True)),
            ip=str(getattr(settings, "VIEWER_IP", "") or ""),
            port=str(getattr(settings, "VIEWER_PORT", "") or ""),
            viewer_targets_raw=str(getattr(settings, "VIEWER_NOTIFY_TARGETS", "") or ""),
            lite_viewer_targets_raw=str(
                getattr(settings, "LITE_VIEWER_NOTIFY_TARGETS", "") or ""
            ),
            mtx_update_path=str(
                getattr(settings, "VIEWER_CMS_UPDATE_PATH", "/api/gui_main/mtx_info_update")
            ),
            all_info_update_path=str(
                getattr(settings, "VIEWER_ALL_INFO_UPDATE_PATH", "/api/gui_main/all_info_update")
            ),
            evt_occur_path=str(
                getattr(settings, "VIEWER_EVT_OCCUR_PATH", "/api/gui_main/evt_occur")
            ),
            account_info_change_path=str(
                getattr(
                    settings,
                    "VIEWER_ACCOUNT_INFO_CHANGE_PATH",
                    "/api/lite_viewer/account_info_change/",
                )
            ),
            timeout_seconds=float(
                getattr(settings, "VIEWER_CMS_UPDATE_TIMEOUT_SECONDS", 5) or 5
            ),
            initial_delay_seconds=max(
                0,
                int(getattr(settings, "VIEWER_CMS_UPDATE_INITIAL_DELAY_SECONDS", 3) or 0),
            ),
            auto_discovery_enabled=bool(
                getattr(settings, "VIEWER_NOTIFY_AUTO_DISCOVERY_ENABLED", True)
            ),
            discovery_lookback_minutes=max(
                1,
                int(getattr(settings, "VIEWER_NOTIFY_DISCOVERY_LOOKBACK_MINUTES", 1440) or 1),
            ),
        )

    @staticmethod
    def _dedupe_targets(*groups: list[NotifyTarget]) -> list[NotifyTarget]:
        merged: list[NotifyTarget] = []
        seen: set[tuple[str, str]] = set()
        for group in groups:
            for item in group:
                ip = (item.ip or "").strip()
                port = (item.port or "").strip()
                if not ip or not port:
                    continue
                key = (ip, port)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(NotifyTarget(ip=ip, port=port))
        return merged

    def _discover_targets(self, client_type: str) -> list[NotifyTarget]:
        if not self.auto_discovery_enabled:
            return []
        try:
            from apps.account.models import AccountLoginHistory

            cutoff = datetime.now() - timedelta(minutes=self.discovery_lookback_minutes)
            rows = (
                AccountLoginHistory.objects.filter(
                    client_type=client_type,
                    ip_address__isnull=False,
                    logged_in_at__gte=cutoff,
                )
                .order_by("-logged_in_at")
                .values_list("ip_address", flat=True)[:500]
            )
        except Exception as exc:
            logger.warning("[ViewerNotifyDiscovery] query failed: %s", exc)
            return []

        targets: list[NotifyTarget] = []
        seen_ips: set[str] = set()
        default_port = (self.port or "").strip() or "8901"
        for row in rows:
            ip = str(row or "").strip()
            if not ip or ip in {"127.0.0.1", "0.0.0.0"}:
                continue
            if ip in seen_ips:
                continue
            seen_ips.add(ip)
            targets.append(NotifyTarget(ip=ip, port=default_port))
        return targets

    def viewer_targets(self) -> list[NotifyTarget]:
        parsed = HttpJsonNotifierBase.parse_targets(self.viewer_targets_raw)
        discovered = self._discover_targets("main_viewer")
        fallback = [NotifyTarget(ip=self.ip, port=self.port)] if self.ip and self.port else []
        return self._dedupe_targets(parsed, discovered, fallback)

    def lite_viewer_targets(self) -> list[NotifyTarget]:
        parsed = HttpJsonNotifierBase.parse_targets(self.lite_viewer_targets_raw)
        discovered = self._discover_targets("sub_viewer")
        return self._dedupe_targets(parsed, discovered, self.viewer_targets())


class ViewerNotifierClientBase(HttpJsonNotifierBase):
    def __init__(
        self,
        targets: list[NotifyTarget],
        *,
        timeout_seconds: float,
        label: str,
    ) -> None:
        super().__init__(
            targets,
            timeout_seconds=timeout_seconds,
            logger_name="cms.viewer_notifier",
            label=label,
        )


class ViewerMainNotifierClient(ViewerNotifierClientBase):
    def __init__(self, config: ViewerCmsUpdateConfig) -> None:
        super().__init__(
            config.viewer_targets(),
            timeout_seconds=config.timeout_seconds,
            label="ViewerMainNotify",
        )


class ViewerLiteNotifierClient(ViewerNotifierClientBase):
    def __init__(self, config: ViewerCmsUpdateConfig) -> None:
        super().__init__(
            config.lite_viewer_targets(),
            timeout_seconds=config.timeout_seconds,
            label="ViewerLiteNotify",
        )


class ViewerEventNotifierClient(ViewerNotifierClientBase):
    def __init__(self, config: ViewerCmsUpdateConfig) -> None:
        super().__init__(
            ViewerCmsUpdateConfig._dedupe_targets(
                config.viewer_targets(),
                config.lite_viewer_targets(),
            ),
            timeout_seconds=config.timeout_seconds,
            label="ViewerEventNotify",
        )


def _build_mtx_payload() -> list[dict[str, str]]:
    try:
        from apps.mediamtx.services.registry import get_rtsp_mapping_snapshot

        snapshot = get_rtsp_mapping_snapshot()
    except Exception:
        snapshot = {}

    payload: list[dict[str, str]] = []
    for camera_key in sorted(snapshot):
        entry = snapshot.get(camera_key) or []
        payload.append(
            {
                "camera_key": str(camera_key),
                "original_rtsp": str(entry[0]) if len(entry) > 0 else "",
                "mediamtx_rtsp": str(entry[1]) if len(entry) > 1 else "",
                "dl_rtsp": str(entry[2]) if len(entry) > 2 else "",
                "mtx_dl_rtsp": str(entry[3]) if len(entry) > 3 else "",
            }
        )

    return payload


def _build_all_info_payload() -> dict:
    try:
        from apps.cms.api.api import build_all_info

        return build_all_info().dict(by_alias=False)
    except Exception as exc:
        logger.warning("[ViewerAllInfoUpdate] build_all_info failed: %s", exc)
        return {}


def notify_viewer_cms_update(
    reason: Optional[str] = None, *, config: Optional[ViewerCmsUpdateConfig] = None
) -> bool:
    cfg = config or ViewerCmsUpdateConfig.from_settings()
    if not cfg.enabled:
        logger.info("[ViewerCMSUpdate] disabled by configuration")
        return False
    payload = _build_mtx_payload()
    print(
        f"[ViewerCMSUpdate] reason={reason} payload="
        f"{json.dumps(payload, ensure_ascii=True)}"
    )
    if bool(getattr(settings, "VIEWER_REALTIME_ENABLED", True)):
        return broadcast_viewer_mtx_info_update(payload, reason)

    notifier = ViewerMainNotifierClient(cfg)
    return notifier.notify(cfg.mtx_update_path, payload, reason)


def notify_viewer_all_info_update(
    reason: Optional[str] = None, *, config: Optional[ViewerCmsUpdateConfig] = None
) -> bool:
    cfg = config or ViewerCmsUpdateConfig.from_settings()
    if not cfg.enabled:
        logger.info("[ViewerAllInfoUpdate] disabled by configuration")
        return False
    payload = _build_all_info_payload()
    print(
        f"[ViewerAllInfoUpdate] reason={reason} payload="
        f"{json.dumps(payload, ensure_ascii=True)}"
    )
    if bool(getattr(settings, "VIEWER_REALTIME_ENABLED", True)):
        return broadcast_viewer_all_info_update(payload, reason)

    notifier = ViewerMainNotifierClient(cfg)
    return notifier.notify(cfg.all_info_update_path, payload, reason)


def notify_viewer_evt_occur(
    payload: list[object], *, config: Optional[ViewerCmsUpdateConfig] = None
) -> bool:
    cfg = config or ViewerCmsUpdateConfig.from_settings()
    if not cfg.enabled:
        logger.info("[ViewerEvtOccur] disabled by configuration")
        return False
    print(
        f"[ViewerEvtOccur] payload="
        f"{json.dumps(payload, ensure_ascii=True)}"
    )
    if bool(getattr(settings, "VIEWER_REALTIME_ENABLED", True)):
        return broadcast_viewer_evt_occur(payload, "evt_occur")

    notifier = ViewerEventNotifierClient(cfg)
    return notifier.notify(cfg.evt_occur_path, payload, "evt_occur")


def notify_viewer_account_info_change(
    reason: Optional[str] = None, *, config: Optional[ViewerCmsUpdateConfig] = None
) -> bool:
    cfg = config or ViewerCmsUpdateConfig.from_settings()
    if not cfg.enabled:
        logger.info("[ViewerAccountInfoChange] disabled by configuration")
        return False
    payload = {}
    print(
        f"[ViewerAccountInfoChange] reason={reason} payload="
        f"{json.dumps(payload, ensure_ascii=True)}"
    )
    if bool(getattr(settings, "VIEWER_REALTIME_ENABLED", True)):
        return broadcast_viewer_account_info_change(payload, reason)

    notifier = ViewerLiteNotifierClient(cfg)
    return notifier.notify(cfg.account_info_change_path, payload, reason)


class ViewerCmsUpdateWorker:
    def __init__(self, config: ViewerCmsUpdateConfig) -> None:
        self.config = config
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("[ViewerCMSUpdate] already running")
            return

        if not self.config.viewer_targets():
            logger.warning("[ViewerCMSUpdate] viewer endpoint not configured; skipping start")
            return
        if not self.config.enabled:
            logger.info("[ViewerCMSUpdate] disabled by configuration")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="ViewerCMSUpdate", daemon=True
        )
        self._thread.start()
        logger.info(
            "[ViewerCMSUpdate] started (delay=%ss)", self.config.initial_delay_seconds
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("[ViewerCMSUpdate] stopped")

    def _run(self) -> None:
        delay = self.config.initial_delay_seconds
        if delay and self._stop_event.wait(delay):
            return
        logger.info("[ViewerAllInfoUpdate] cms_start send skipped (wait for MTX resync)")


_viewer_worker: Optional[ViewerCmsUpdateWorker] = None
_viewer_lock = threading.Lock()


def start_viewer_notifier() -> Optional[ViewerCmsUpdateWorker]:
    config = ViewerCmsUpdateConfig.from_settings()
    if not config.enabled:
        logger.info("[ViewerCMSUpdate] disabled by configuration")
        return None
    if bool(getattr(settings, "VIEWER_REALTIME_ENABLED", True)):
        logger.info("[ViewerCMSUpdate] realtime transport enabled; http notifier worker idle")
        return None

    runserver_command = any("runserver" in arg for arg in sys.argv)
    run_main_flag = os.environ.get("RUN_MAIN")
    if runserver_command and run_main_flag != "true":
        return None

    global _viewer_worker
    if _viewer_worker is not None:
        return _viewer_worker

    with _viewer_lock:
        if _viewer_worker is not None:
            return _viewer_worker
        worker = ViewerCmsUpdateWorker(config)
        _viewer_worker = worker
        try:
            worker.start()
        except Exception:
            _viewer_worker = None
            raise
        return worker


def stop_viewer_notifier() -> None:
    global _viewer_worker
    if _viewer_worker is None:
        return

    with _viewer_lock:
        if _viewer_worker is None:
            return
        _viewer_worker.stop()
        _viewer_worker = None


__all__ = [
    "ViewerCmsUpdateConfig",
    "ViewerCmsUpdateWorker",
    "notify_viewer_cms_update",
    "notify_viewer_all_info_update",
    "notify_viewer_evt_occur",
    "notify_viewer_account_info_change",
    "start_viewer_notifier",
    "stop_viewer_notifier",
]
