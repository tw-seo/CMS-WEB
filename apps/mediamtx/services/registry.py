from __future__ import annotations

import hashlib
import logging
import os
import sys
import threading
from dataclasses import dataclass
from typing import Iterable, Optional

import requests
from django.conf import settings
from django.db import close_old_connections

from apps.cms.models import CameraInfo
from apps.cms.services.workers.viewer_notifier import (
    notify_viewer_all_info_update,
    notify_viewer_cms_update,
)
from core.exceptions import AppError

from .mediamtx import MediaMtxService

logger = logging.getLogger("mediamtx.registry")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

logger.setLevel(logging.INFO if getattr(settings, "DEBUG", False) else logging.WARNING)

_rtsp_map: dict[str, list[str]] = {}
_dl_rtsp_map: dict[str, list[str]] = {}
_map_lock = threading.Lock()


def set_rtsp_mapping(camera_key: str, original_rtsp: str, mediamtx_rtsp: str) -> None:
    if not camera_key:
        return
    with _map_lock:
        entry = _rtsp_map.get(camera_key, ["", ""])
        if len(entry) < 2:
            entry = (entry + ["", ""])[:2]
        entry[0] = original_rtsp
        entry[1] = mediamtx_rtsp
        _rtsp_map[camera_key] = entry


def set_dl_rtsp_source(camera_key: str, dl_rtsp: str) -> None:
    if not camera_key:
        return
    with _map_lock:
        entry = _dl_rtsp_map.get(camera_key, ["", ""])
        if len(entry) < 2:
            entry = (entry + ["", ""])[:2]
        entry[0] = dl_rtsp
        _dl_rtsp_map[camera_key] = entry


def set_dl_rtsp_mapping(camera_key: str, dl_rtsp: str, mtx_dl_rtsp: str) -> None:
    if not camera_key:
        return
    with _map_lock:
        entry = _dl_rtsp_map.get(camera_key, ["", ""])
        if len(entry) < 2:
            entry = (entry + ["", ""])[:2]
        entry[0] = dl_rtsp
        entry[1] = mtx_dl_rtsp
        _dl_rtsp_map[camera_key] = entry


def remove_rtsp_mapping(camera_key: str) -> None:
    if not camera_key:
        return
    with _map_lock:
        _rtsp_map.pop(camera_key, None)
        _dl_rtsp_map.pop(camera_key, None)


def clear_rtsp_mappings() -> None:
    with _map_lock:
        _rtsp_map.clear()


def clear_dl_rtsp_mappings() -> None:
    with _map_lock:
        _dl_rtsp_map.clear()


def get_rtsp_mapping_snapshot() -> dict[str, list[str]]:
    with _map_lock:
        merged: dict[str, list[str]] = {}
        keys = set(_rtsp_map) | set(_dl_rtsp_map)
        for key in keys:
            rtsp_entry = _rtsp_map.get(key, ["", ""])
            dl_entry = _dl_rtsp_map.get(key, ["", ""])
            original_rtsp = rtsp_entry[0] if len(rtsp_entry) > 0 else ""
            mediamtx_rtsp = rtsp_entry[1] if len(rtsp_entry) > 1 else ""
            dl_rtsp = dl_entry[0] if len(dl_entry) > 0 else ""
            mtx_dl_rtsp = dl_entry[1] if len(dl_entry) > 1 else ""
            merged[key] = [original_rtsp, mediamtx_rtsp, dl_rtsp, mtx_dl_rtsp]
        for key, value in merged.items():
            print(f"[rtsp-map] {key} -> {value}")
        return {key: value[:] for key, value in merged.items()}


@dataclass(slots=True)
class MediaMtxRegistryConfig:
    enabled: bool
    initial_delay_seconds: int
    interval_seconds: int
    health_path: str
    timeout_seconds: float

    @classmethod
    def from_settings(cls) -> "MediaMtxRegistryConfig":
        cfg = getattr(settings, "MEDIAMTX", {})
        return cls(
            enabled=bool(cfg.get("REGISTRY_ENABLED", True)),
            initial_delay_seconds=max(
                0, int(cfg.get("REGISTRY_INITIAL_DELAY_SECONDS", 10) or 10)
            ),
            interval_seconds=max(
                5, int(cfg.get("REGISTRY_INTERVAL_SECONDS", 60) or 60)
            ),
            health_path=str(cfg.get("REGISTRY_HEALTH_PATH", "/v3/serverinfos/get")),
            timeout_seconds=float(cfg.get("REGISTRY_TIMEOUT_SECONDS", 5) or 5),
        )


class MediaMtxRegistryWorker:
    def __init__(self, config: MediaMtxRegistryConfig) -> None:
        self.config = config
        self._service = MediaMtxService()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._available: Optional[bool] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("[MediaMTXRegistry] already running")
            return

        if not self._service.config.api_base:
            logger.warning("[MediaMTXRegistry] API base not configured; skipping start")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="MediaMTXRegistry", daemon=True
        )
        self._thread.start()
        logger.info(
            "[MediaMTXRegistry] started (delay=%ss interval=%ss health=%s)",
            self.config.initial_delay_seconds,
            self.config.interval_seconds,
            self.config.health_path,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("[MediaMTXRegistry] stopped")

    def register_camera(self, camera_key: str, original_rtsp: str) -> bool:
        if not camera_key or not original_rtsp:
            return False
        if not self._is_available():
            logger.warning(
                "[MediaMTXRegistry] register skipped (unavailable) key=%s", camera_key
            )
            return False
        return self._register(camera_key, original_rtsp)

    def register_dl_rtsp(self, camera_key: str, dl_rtsp: str) -> bool:
        if not camera_key or not dl_rtsp:
            return False
        set_dl_rtsp_source(camera_key, dl_rtsp)
        if not self._is_available():
            logger.warning(
                "[MediaMTXRegistry] DL register skipped (unavailable) key=%s", camera_key
            )
            return True
        return self._register_dl(camera_key, dl_rtsp)

    def remove_dl_rtsp(self, camera_key: str, dl_rtsp: str | None = None) -> None:
        if not camera_key:
            return
        set_dl_rtsp_mapping(camera_key, "", "")
        if not dl_rtsp:
            return
        if not self._is_available():
            logger.warning(
                "[MediaMTXRegistry] DL delete skipped (unavailable) key=%s", camera_key
            )
            return
        stream_path = self._derive_dl_stream_path(dl_rtsp)
        try:
            self._service._mtx_delete_path(stream_path)
        except AppError as exc:
            logger.warning("[MediaMTXRegistry] DL delete failed: %s", exc)

    def remove_camera(self, camera_key: str, original_rtsp: str | None = None) -> None:
        if not camera_key:
            return
        remove_rtsp_mapping(camera_key)
        if not original_rtsp:
            return
        if not self._is_available():
            logger.warning(
                "[MediaMTXRegistry] delete skipped (unavailable) key=%s", camera_key
            )
            return
        stream_path = self._service._derive_stream_path(original_rtsp)
        try:
            self._service._mtx_delete_path(stream_path)
        except AppError as exc:
            logger.warning("[MediaMTXRegistry] delete failed: %s", exc)

    def resync_from_db(self) -> None:
        if not self._is_available():
            logger.warning("[MediaMTXRegistry] resync skipped (unavailable)")
            return
        clear_rtsp_mappings()
        close_old_connections()
        try:
            rows = CameraInfo.objects.values("camera_info_key", "rtsp_url_001")
        except Exception as exc:
            logger.warning("[MediaMTXRegistry] camera load failed: %s", exc)
            return
        rows_list = list(rows)
        logger.info("[MediaMTXRegistry] resync camera count=%s", len(rows_list))
        for row in rows_list:
            camera_key = row.get("camera_info_key") or ""
            original_rtsp = row.get("rtsp_url_001") or ""
            if not camera_key or not original_rtsp:
                continue
            self._register(camera_key, original_rtsp)

    def resync_dl_rtsp(self) -> None:
        if not self._is_available():
            logger.warning("[MediaMTXRegistry] DL resync skipped (unavailable)")
            return
        with _map_lock:
            items = list(_dl_rtsp_map.items())
        for camera_key, entry in items:
            dl_rtsp = entry[0] if entry else ""
            if not camera_key or not dl_rtsp:
                continue
            self._register_dl(camera_key, dl_rtsp)

    def _run_loop(self) -> None:
        if self.config.initial_delay_seconds:
            if self._stop_event.wait(self.config.initial_delay_seconds):
                return
        self._tick()
        while not self._stop_event.wait(self.config.interval_seconds):
            self._tick()

    def _tick(self) -> None:
        available = self._check_available()
        logger.info("[MediaMTXRegistry] health=%s", "ok" if available else "fail")
        if self._available is None:
            self._available = available
            if available:
                self.resync_from_db()
                dl_synced = self._sync_dl_rtsp_from_dl()
                if not dl_synced:
                    clear_dl_rtsp_mappings()
                notify_viewer_all_info_update("mediamtx_resync")
            return
        if available and not self._available:
            logger.warning("[MediaMTXRegistry] mediamtx restored; resyncing")
            clear_rtsp_mappings()
            self.resync_from_db()
            self.resync_dl_rtsp()
            notify_viewer_cms_update("mediamtx_restored")
        elif not available and self._available:
            logger.warning("[MediaMTXRegistry] mediamtx down; clearing map")
            clear_rtsp_mappings()
            notify_viewer_cms_update("mediamtx_down")
        self._available = available

    def _is_available(self) -> bool:
        return self._available is True

    def _check_available(self) -> bool:
        api_base = self._service.config.api_base
        if not api_base:
            return False
        path = self.config.health_path or "/"
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{api_base}{path}"
        try:
            response = requests.get(url, timeout=self.config.timeout_seconds)
        except requests.RequestException:
            return False
        return response.ok

    def _register(self, camera_key: str, original_rtsp: str) -> bool:
        stream_path = self._service._derive_stream_path(original_rtsp)
        try:
            self._service._ensure_path(
                stream_path,
                original_rtsp,
                self._service.config.default_ondemand,
            )
        except AppError as exc:
            logger.warning("[MediaMTXRegistry] register failed: %s", exc)
            return False
        rtsp_url = self._service._build_urls(stream_path, None)["rtsp"]
        set_rtsp_mapping(camera_key, original_rtsp, rtsp_url)
        logger.info("[MediaMTXRegistry] registered key=%s", camera_key)
        return True

    def _register_dl(self, camera_key: str, dl_rtsp: str) -> bool:
        stream_path = self._derive_dl_stream_path(dl_rtsp)
        try:
            self._service._ensure_path(
                stream_path,
                dl_rtsp,
                self._service.config.default_ondemand,
            )
        except AppError as exc:
            logger.warning("[MediaMTXRegistry] DL register failed: %s", exc)
            return False
        rtsp_url = self._service._build_urls(stream_path, None)["rtsp"]
        set_dl_rtsp_mapping(camera_key, dl_rtsp, rtsp_url)
        logger.info("[MediaMTXRegistry] DL registered key=%s", camera_key)
        return True

    def _sync_dl_rtsp_from_dl(self) -> bool:
        dl_ip = getattr(settings, "DL_IP", None)
        dl_port = getattr(settings, "DL_PORT", None)
        if not dl_ip or not dl_port:
            logger.warning("[MediaMTXRegistry] DL is_running skipped (missing DL_IP/DL_PORT)")
            return False

        path = str(getattr(settings, "DL_HEALTH_PATH", "/API/is_running") or "")
        if not path.startswith("/"):
            path = f"/{path}"
        method = str(getattr(settings, "DL_HEALTH_METHOD", "POST") or "").upper()
        timeout = float(getattr(settings, "DL_IS_RUNNING_TIMEOUT_SECONDS", 3) or 3)

        url = f"http://{dl_ip}:{dl_port}{path}"
        try:
            if method == "POST":
                response = requests.post(url, timeout=timeout)
            else:
                response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("[MediaMTXRegistry] DL is_running request failed: %s", exc)
            return False

        try:
            payload = response.json()
        except ValueError:
            payload = response.text.strip()

        if not isinstance(payload, list):
            logger.warning(
                "[MediaMTXRegistry] DL is_running payload not list; type=%s",
                type(payload).__name__,
            )
            return False

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

        register_dl_rtsp_bulk(items)
        logger.info("[MediaMTXRegistry] DL is_running synced count=%s", len(items))
        return True

    @staticmethod
    def _derive_dl_stream_path(source: str) -> str:
        normalized = source.strip().lower()
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        return f"dl-{digest[:12]}"


_registry_worker: Optional[MediaMtxRegistryWorker] = None
_registry_lock = threading.Lock()


def start_mtx_registry() -> Optional[MediaMtxRegistryWorker]:
    config = MediaMtxRegistryConfig.from_settings()
    if not config.enabled:
        logger.info("[MediaMTXRegistry] disabled by configuration")
        return None

    runserver_command = any("runserver" in arg for arg in sys.argv)
    run_main_flag = os.environ.get("RUN_MAIN")
    if runserver_command and run_main_flag != "true":
        return None

    global _registry_worker
    if _registry_worker is not None:
        return _registry_worker

    with _registry_lock:
        if _registry_worker is not None:
            return _registry_worker
        worker = MediaMtxRegistryWorker(config)
        _registry_worker = worker
        try:
            worker.start()
        except Exception:
            _registry_worker = None
            raise
        return worker


def get_registry_worker() -> Optional[MediaMtxRegistryWorker]:
    return _registry_worker


def register_camera_rtsp(camera_key: str, original_rtsp: str) -> bool:
    worker = _registry_worker
    if worker is None:
        return False
    return worker.register_camera(camera_key, original_rtsp)


def register_dl_rtsp(camera_key: str, dl_rtsp: str) -> bool:
    if not camera_key or not dl_rtsp:
        return False
    set_dl_rtsp_source(camera_key, dl_rtsp)
    worker = _registry_worker
    if worker is None:
        return True
    return worker.register_dl_rtsp(camera_key, dl_rtsp)


def register_dl_rtsp_bulk(items: Iterable[object]) -> int:
    desired: dict[str, str] = {}
    for item in items or []:
        if isinstance(item, dict):
            camera_key = item.get("camera_key") or ""
            dl_rtsp = item.get("dl_rtsp") or ""
        else:
            camera_key = getattr(item, "camera_key", "") or ""
            dl_rtsp = getattr(item, "dl_rtsp", "") or ""

        key = str(camera_key).strip()
        value = str(dl_rtsp).strip()
        if not key or not value:
            continue
        desired[key] = value

    with _map_lock:
        existing = {key: value[:] for key, value in _dl_rtsp_map.items()}

    worker = _registry_worker
    updated = 0

    for camera_key, entry in existing.items():
        if camera_key in desired:
            continue
        prev_dl = entry[0] if entry else ""
        if worker is not None:
            worker.remove_dl_rtsp(camera_key, prev_dl)
        else:
            set_dl_rtsp_mapping(camera_key, "", "")

    for camera_key, dl_rtsp in desired.items():
        prev_entry = existing.get(camera_key, ["", ""])
        prev_dl = prev_entry[0] if prev_entry else ""
        if prev_dl and prev_dl != dl_rtsp:
            if worker is not None:
                worker.remove_dl_rtsp(camera_key, prev_dl)
            else:
                set_dl_rtsp_mapping(camera_key, "", "")

        if worker is not None:
            if worker.register_dl_rtsp(camera_key, dl_rtsp):
                updated += 1
        else:
            set_dl_rtsp_mapping(camera_key, dl_rtsp, "")
            updated += 1

    return updated


def remove_camera_rtsp(camera_key: str, original_rtsp: str | None = None) -> None:
    worker = _registry_worker
    if worker is None:
        return
    worker.remove_camera(camera_key, original_rtsp)
