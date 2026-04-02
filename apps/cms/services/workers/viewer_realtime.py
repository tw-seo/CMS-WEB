from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

try:
    from websockets.server import WebSocketServerProtocol, serve
except Exception as exc:  # pragma: no cover - dependency missing at runtime
    WebSocketServerProtocol = object  # type: ignore[assignment]
    serve = None  # type: ignore[assignment]
    _WEBSOCKETS_IMPORT_ERROR = exc
else:
    _WEBSOCKETS_IMPORT_ERROR = None


logger = logging.getLogger("cms.viewer_realtime")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

logger.setLevel(logging.INFO if getattr(settings, "DEBUG", False) else logging.WARNING)


@dataclass(slots=True)
class ViewerRealtimeConfig:
    enabled: bool
    host: str
    port: int
    path: str
    ping_interval_seconds: int
    ping_timeout_seconds: int
    register_timeout_seconds: int
    send_timeout_seconds: int

    @classmethod
    def from_settings(cls) -> "ViewerRealtimeConfig":
        return cls(
            enabled=bool(getattr(settings, "VIEWER_REALTIME_ENABLED", True)),
            host=str(getattr(settings, "VIEWER_REALTIME_HOST", "0.0.0.0") or "0.0.0.0"),
            port=int(getattr(settings, "VIEWER_REALTIME_PORT", 10516) or 10516),
            path=str(getattr(settings, "VIEWER_REALTIME_PATH", "/ws/viewer") or "/ws/viewer"),
            ping_interval_seconds=max(
                5,
                int(getattr(settings, "VIEWER_REALTIME_PING_INTERVAL_SECONDS", 20) or 20),
            ),
            ping_timeout_seconds=max(
                5,
                int(getattr(settings, "VIEWER_REALTIME_PING_TIMEOUT_SECONDS", 20) or 20),
            ),
            register_timeout_seconds=max(
                3,
                int(getattr(settings, "VIEWER_REALTIME_REGISTER_TIMEOUT_SECONDS", 10) or 10),
            ),
            send_timeout_seconds=max(
                1,
                int(getattr(settings, "VIEWER_REALTIME_SEND_TIMEOUT_SECONDS", 5) or 5),
            ),
        )


@dataclass(slots=True)
class ViewerRealtimeSession:
    websocket: WebSocketServerProtocol
    client_type: str
    viewer_id: str
    account_key: str
    user_id: str
    remote_address: str
    connected_at: float


class ViewerRealtimeServer:
    def __init__(self, config: ViewerRealtimeConfig) -> None:
        self.config = config
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started_event = threading.Event()
        self._server_ready = threading.Event()
        self._sessions: dict[int, ViewerRealtimeSession] = {}
        self._sessions_lock = threading.Lock()
        self._shutdown_future: Optional[asyncio.Future] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("[ViewerRealtime] already running")
            return

        if serve is None:
            logger.warning("[ViewerRealtime] websockets dependency unavailable: %s", _WEBSOCKETS_IMPORT_ERROR)
            return

        self._stop_event.clear()
        self._started_event.clear()
        self._server_ready.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ViewerRealtimeServer",
            daemon=True,
        )
        self._thread.start()
        self._started_event.wait(timeout=5)

    def stop(self) -> None:
        self._stop_event.set()
        loop = self._loop
        shutdown_future = self._shutdown_future
        if loop and shutdown_future and not shutdown_future.done():
            loop.call_soon_threadsafe(shutdown_future.set_result, None)
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def broadcast(self, message_type: str, payload: object, *, audience: str, reason: Optional[str]) -> bool:
        if not self.config.enabled:
            logger.info("[ViewerRealtime] disabled by configuration")
            return False

        loop = self._loop
        if loop is None or not self._server_ready.is_set():
            logger.warning("[ViewerRealtime] server not ready; skipping %s", message_type)
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._broadcast(message_type, payload, audience=audience, reason=reason),
            loop,
        )
        try:
            return bool(future.result(timeout=self.config.send_timeout_seconds + 1))
        except Exception as exc:
            logger.warning("[ViewerRealtime] broadcast failed (%s): %s", message_type, exc)
            return False

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._serve_forever())
        except Exception as exc:
            logger.warning("[ViewerRealtime] server stopped unexpectedly: %s", exc)
        finally:
            self._server_ready.clear()
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            loop.close()
            self._loop = None
            self._shutdown_future = None

    async def _serve_forever(self) -> None:
        self._shutdown_future = asyncio.get_running_loop().create_future()
        normalized_path = self._normalize_path(self.config.path)
        async with serve(
            self._handle_connection,
            self.config.host,
            self.config.port,
            ping_interval=self.config.ping_interval_seconds,
            ping_timeout=self.config.ping_timeout_seconds,
        ):
            self._server_ready.set()
            self._started_event.set()
            logger.warning(
                "[ViewerRealtime] listening on ws://%s:%s%s",
                self.config.host,
                self.config.port,
                normalized_path,
            )
            await self._shutdown_future

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        normalized_path = self._normalize_path(self.config.path)
        if self._normalize_path(getattr(websocket, "path", "")) != normalized_path:
            await websocket.close(code=1008, reason="invalid_path")
            return

        session: Optional[ViewerRealtimeSession] = None
        try:
            session = await self._register_session(websocket)
            if session is None:
                return

            async for raw in websocket:
                await self._handle_client_message(session, raw)
        except Exception as exc:
            if session is not None:
                logger.info(
                    "[ViewerRealtime] disconnected viewer_id=%s client_type=%s reason=%s",
                    session.viewer_id,
                    session.client_type,
                    exc,
                )
        finally:
            if session is not None:
                self._remove_session(session)

    async def _register_session(
        self, websocket: WebSocketServerProtocol
    ) -> Optional[ViewerRealtimeSession]:
        try:
            raw = await asyncio.wait_for(
                websocket.recv(),
                timeout=self.config.register_timeout_seconds,
            )
        except Exception as exc:
            logger.info("[ViewerRealtime] register receive failed: %s", exc)
            await websocket.close(code=1008, reason="register_timeout")
            return None

        try:
            data = json.loads(raw)
        except Exception:
            await websocket.close(code=1008, reason="invalid_json")
            return None

        if not isinstance(data, dict):
            await websocket.close(code=1008, reason="invalid_payload")
            return None

        if str(data.get("type") or "").strip() != "register":
            await websocket.close(code=1008, reason="register_required")
            return None

        payload = data.get("payload")
        if isinstance(payload, dict):
            register_data = payload
        else:
            register_data = data

        client_type = str(register_data.get("client_type") or "").strip().lower()
        if client_type not in {"main_viewer", "sub_viewer"}:
            logger.warning(
                "[ViewerRealtime] invalid client_type during register: raw=%s",
                data,
            )
            await websocket.close(code=1008, reason="invalid_client_type")
            return None

        remote = getattr(websocket, "remote_address", None)
        remote_address = ""
        if isinstance(remote, tuple) and remote:
            remote_address = str(remote[0] or "")
        elif remote:
            remote_address = str(remote)

        session = ViewerRealtimeSession(
            websocket=websocket,
            client_type=client_type,
            viewer_id=str(register_data.get("viewer_id") or "").strip(),
            account_key=str(register_data.get("account_key") or "").strip(),
            user_id=str(register_data.get("user_id") or "").strip(),
            remote_address=remote_address,
            connected_at=time.time(),
        )

        with self._sessions_lock:
            self._sessions[id(websocket)] = session

        logger.warning(
            "[ViewerRealtime] connected client_type=%s viewer_id=%s remote=%s sessions=%s",
            session.client_type,
            session.viewer_id or "(empty)",
            session.remote_address or "(unknown)",
            len(self._sessions),
        )

        await websocket.send(
            json.dumps(
                {
                    "type": "registered",
                    "reason": "connected",
                    "payload": {
                        "client_type": session.client_type,
                        "viewer_id": session.viewer_id,
                    },
                },
                ensure_ascii=False,
            )
        )
        return session

    async def _handle_client_message(self, session: ViewerRealtimeSession, raw: str) -> None:
        try:
            data = json.loads(raw)
        except Exception:
            logger.info("[ViewerRealtime] invalid client message from %s", session.viewer_id)
            return

        message_type = str(data.get("type") or "").strip().lower()
        if message_type == "heartbeat":
            return

        logger.info(
            "[ViewerRealtime] unsupported client message viewer_id=%s type=%s",
            session.viewer_id,
            message_type,
        )

    async def _broadcast(
        self,
        message_type: str,
        payload: object,
        *,
        audience: str,
        reason: Optional[str],
    ) -> bool:
        targets = self._select_sessions(audience)
        if not targets:
            logger.warning("[ViewerRealtime] no active viewer sessions for %s", audience)
            return False

        text = json.dumps(
            {
                "type": message_type,
                "reason": reason or "",
                "payload": payload,
            },
            ensure_ascii=False,
            default=str,
        )

        has_success = False
        stale: list[ViewerRealtimeSession] = []
        for session in targets:
            try:
                await session.websocket.send(text)
                has_success = True
            except Exception as exc:
                logger.warning(
                    "[ViewerRealtime] send failed viewer_id=%s client_type=%s type=%s exc=%s",
                    session.viewer_id,
                    session.client_type,
                    message_type,
                    exc,
                )
                stale.append(session)

        for session in stale:
            self._remove_session(session)

        logger.info(
            "[ViewerRealtime] broadcast type=%s audience=%s targets=%s success=%s",
            message_type,
            audience,
            len(targets),
            has_success,
        )
        return has_success

    def _select_sessions(self, audience: str) -> list[ViewerRealtimeSession]:
        with self._sessions_lock:
            sessions = list(self._sessions.values())

        if audience == "main":
            return [item for item in sessions if item.client_type == "main_viewer"]
        if audience == "lite":
            return [item for item in sessions if item.client_type == "sub_viewer"]
        return sessions

    def _remove_session(self, session: ViewerRealtimeSession) -> None:
        with self._sessions_lock:
            self._sessions.pop(id(session.websocket), None)

    @staticmethod
    def _normalize_path(path: str) -> str:
        text = (path or "").strip()
        if not text:
            return "/"
        if not text.startswith("/"):
            text = f"/{text}"
        return text


_viewer_realtime_server: Optional[ViewerRealtimeServer] = None
_viewer_realtime_lock = threading.Lock()


def start_viewer_realtime_server() -> Optional[ViewerRealtimeServer]:
    config = ViewerRealtimeConfig.from_settings()
    if not config.enabled:
        logger.info("[ViewerRealtime] disabled by configuration")
        return None

    if serve is None:
        logger.warning("[ViewerRealtime] websockets dependency unavailable: %s", _WEBSOCKETS_IMPORT_ERROR)
        return None

    runserver_command = any("runserver" in arg for arg in sys.argv)
    run_main_flag = os.environ.get("RUN_MAIN")
    if runserver_command and run_main_flag != "true":
        return None

    global _viewer_realtime_server
    if _viewer_realtime_server is not None:
        return _viewer_realtime_server

    with _viewer_realtime_lock:
        if _viewer_realtime_server is not None:
            return _viewer_realtime_server

        server = ViewerRealtimeServer(config)
        _viewer_realtime_server = server
        try:
            server.start()
            atexit.register(stop_viewer_realtime_server)
        except Exception:
            _viewer_realtime_server = None
            raise
        return server


def stop_viewer_realtime_server() -> None:
    global _viewer_realtime_server
    if _viewer_realtime_server is None:
        return

    with _viewer_realtime_lock:
        if _viewer_realtime_server is None:
            return
        _viewer_realtime_server.stop()
        _viewer_realtime_server = None


def _broadcast(message_type: str, payload: object, *, audience: str, reason: Optional[str]) -> bool:
    server = start_viewer_realtime_server()
    if server is None:
        return False
    return server.broadcast(message_type, payload, audience=audience, reason=reason)


def broadcast_viewer_mtx_info_update(payload: object, reason: Optional[str] = None) -> bool:
    return _broadcast("mtx_info_update", payload, audience="main", reason=reason)


def broadcast_viewer_all_info_update(payload: object, reason: Optional[str] = None) -> bool:
    return _broadcast("all_info_update", payload, audience="main", reason=reason)


def broadcast_viewer_evt_occur(payload: object, reason: Optional[str] = None) -> bool:
    return _broadcast("evt_occur", payload, audience="all", reason=reason)


def broadcast_viewer_account_info_change(payload: object, reason: Optional[str] = None) -> bool:
    return _broadcast("account_info_change", payload, audience="lite", reason=reason)


__all__ = [
    "ViewerRealtimeConfig",
    "ViewerRealtimeServer",
    "broadcast_viewer_account_info_change",
    "broadcast_viewer_all_info_update",
    "broadcast_viewer_evt_occur",
    "broadcast_viewer_mtx_info_update",
    "start_viewer_realtime_server",
    "stop_viewer_realtime_server",
]
