from __future__ import annotations

import hashlib
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Iterable
from urllib.parse import parse_qs

import jwt
import requests
from core.exceptions import AppError
from core.services.base import BaseService
from django.conf import settings
from django.utils import timezone

from apps.mediamtx.models import MediaStream
from apps.mediamtx.schemas import (
    MediaAuthPayloadSchema,
    MediaAuthResponseSchema,
    MediaStreamResponseSchema,
    MediaStreamRtspMapSchema,
    StreamRequestSchema,
    StreamResponseSchema,
)


@dataclass
class MediaMtxConfig:
    public_host: str
    api_base: str
    default_ondemand: bool
    token_auth_enabled: bool
    jwt_secret: str
    token_ttl_sec: int
    rtsp_port: str
    hls_port: str
    webrtc_port: str
    source_protocol: str

    @classmethod
    def load(cls) -> "MediaMtxConfig":
        cfg = getattr(settings, "MEDIAMTX", {})
        return cls(
            public_host=cfg.get("PUBLIC_HOST", "127.0.0.1"),
            api_base=str(cfg.get("API_BASE", "http://mediamtx:9997")).rstrip("/"),
            default_ondemand=bool(cfg.get("DEFAULT_ONDEMAND", False)),
            token_auth_enabled=bool(cfg.get("TOKEN_AUTH_ENABLED", True)),
            jwt_secret=cfg.get("JWT_SECRET", "supersecret_change_me"),
            token_ttl_sec=int(cfg.get("TOKEN_TTL_SEC", 300)),
            rtsp_port=str(cfg.get("MTX_RTSP_PORT", "8554")),
            hls_port=str(cfg.get("HLS_PORT", "8888")),
            webrtc_port=str(cfg.get("WEBRTC_PORT", "8889")),
            source_protocol=cfg.get("SOURCE_PROTOCOL", "tcp"),
        )


class MediaMtxService(BaseService[MediaStream, StreamRequestSchema]):
    model = MediaStream

    def __init__(self, company=None):
        super().__init__(company=company)
        self.config = MediaMtxConfig.load()
        self.logger = logging.getLogger(__name__)

    def issue_stream(
        self, payload: StreamRequestSchema, *, requested_by=None
    ) -> StreamResponseSchema:
        self._require_company()
        stream_path = self._derive_stream_path(payload.original_rtsp)
        source_on_demand = (
            self.config.default_ondemand
            if payload.source_on_demand is None
            else payload.source_on_demand
        )

        stream, _ = MediaStream.objects.update_or_create(
            company=self.company,
            camera_key=payload.camera_key,
            defaults={
                "stream_path": stream_path,
                "original_rtsp": payload.original_rtsp,
                "stream_type": payload.stream_type,
                "source_on_demand": source_on_demand,
                "token_auth_enabled": self.config.token_auth_enabled,
                "requested_by": requested_by,
            },
        )

        self._ensure_path(stream.stream_path, stream.original_rtsp, source_on_demand)

        token, expires_at = self._make_token(stream.stream_path)
        urls = self._build_urls(stream.stream_path, token if token else None)

        stream.last_issued_token = token
        stream.token_expires_at = expires_at
        stream.last_issued_at = timezone.now()
        stream.token_auth_enabled = self.config.token_auth_enabled
        stream.save(
            update_fields=[
                "stream_path",
                "original_rtsp",
                "stream_type",
                "source_on_demand",
                "token_auth_enabled",
                "last_issued_token",
                "token_expires_at",
                "last_issued_at",
                "requested_by",
            ]
        )

        return StreamResponseSchema(
            path=stream.stream_path,
            stream_type=stream.stream_type,
            requested_url=urls[payload.stream_type],
            all_urls=urls,
            note=(
                f"PUBLIC_HOST={self.config.public_host}, "
                f"sourceOnDemand={source_on_demand}, "
                f"tokenAuth={self.config.token_auth_enabled}"
            ),
            token=token,
        )

    def list_streams(self) -> list[MediaStreamResponseSchema]:
        self._require_company()
        values = [
            "id",
            "camera_key",
            "stream_path",
            "original_rtsp",
            "stream_type",
            "source_on_demand",
            "token_auth_enabled",
        ]
        return [
            MediaStreamResponseSchema(**item)
            for item in self.list(values=values)  # type: ignore[arg-type]
        ]

    def list_rtsp_mappings(self) -> list[MediaStreamRtspMapSchema]:
        self._require_company()
        try:
            from apps.mediamtx.services.registry import get_rtsp_mapping_snapshot

            snapshot = get_rtsp_mapping_snapshot()
        except Exception:
            snapshot = {}
        rows = self.list(values=["camera_key", "original_rtsp", "stream_path"])
        mappings: list[MediaStreamRtspMapSchema] = []
        for row in rows:  # type: ignore[assignment]
            stream_path = row.get("stream_path") or ""
            rtsp_url = self._build_urls(stream_path, None)["rtsp"] if stream_path else ""
            camera_key = row.get("camera_key", "")
            entry = snapshot.get(camera_key, [])
            dl_rtsp = entry[2] if len(entry) > 2 else ""
            mtx_dl_rtsp = entry[3] if len(entry) > 3 else ""
            mappings.append(
                MediaStreamRtspMapSchema(
                    camera_key=camera_key,
                    original_rtsp=row.get("original_rtsp", ""),
                    mediamtx_rtsp=rtsp_url,
                    dl_rtsp=dl_rtsp,
                    mtx_dl_rtsp=mtx_dl_rtsp,
                )
            )
        return mappings

    def list_rtsp_clients(self) -> dict:
        base = self.config.api_base
        urls = [
            f"{base}/v3/rtsp/conns/list",
            f"{base}/v3/rtsp/sessions/list",
            f"{base}/v2/rtsp/conns/list",
            f"{base}/v2/rtsp/sessions/list",
        ]
        resp = None
        for url in urls:
            try:
                resp = requests.get(url, timeout=5)
            except requests.RequestException as exc:
                self.logger.exception("MediaMTX rtsp list failed")
                raise AppError(
                    f"MediaMTX conns list failed: {exc}", HTTPStatus.BAD_GATEWAY
                )
            if resp.status_code == HTTPStatus.OK:
                try:
                    return {"source": "rtsp_list", "data": resp.json()}
                except ValueError as exc:
                    raise AppError(
                        f"MediaMTX conns list invalid json: {exc}",
                        HTTPStatus.BAD_GATEWAY,
                    )
            if resp.status_code == HTTPStatus.NOT_FOUND:
                continue
            raise AppError(
                f"MediaMTX conns list failed: {resp.status_code} {resp.text}",
                HTTPStatus.BAD_GATEWAY,
            )

        paths_payload = self._list_paths_payload()
        paths = self._extract_path_names(paths_payload)
        clients = self._collect_rtsp_clients_from_paths(paths)
        return {"source": "paths", "clients": clients}

    def _list_paths_payload(self) -> dict:
        base = self.config.api_base
        urls = [
            f"{base}/v3/paths/list",
            f"{base}/v2/paths/list",
        ]
        for url in urls:
            try:
                resp = requests.get(url, timeout=5)
            except requests.RequestException as exc:
                self.logger.exception("MediaMTX paths list failed")
                raise AppError(
                    f"MediaMTX paths list failed: {exc}", HTTPStatus.BAD_GATEWAY
                )
            if resp.status_code == HTTPStatus.OK:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise AppError(
                        f"MediaMTX paths list invalid json: {exc}",
                        HTTPStatus.BAD_GATEWAY,
                    )
            if resp.status_code == HTTPStatus.NOT_FOUND:
                continue
            raise AppError(
                f"MediaMTX paths list failed: {resp.status_code} {resp.text}",
                HTTPStatus.BAD_GATEWAY,
            )
        raise AppError("MediaMTX paths list failed: 404", HTTPStatus.BAD_GATEWAY)

    def _extract_path_names(self, payload: dict) -> list[str]:
        if not isinstance(payload, dict):
            return []
        items = payload.get("items") or payload.get("item") or payload.get("paths") or []
        names: list[str] = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("path") or item.get("id")
                    if name:
                        names.append(str(name))
                elif isinstance(item, str):
                    names.append(item)
        return names

    def _collect_rtsp_clients_from_paths(self, paths: list[str]) -> list[dict]:
        clients: list[dict] = []
        for path in paths:
            detail = self._get_path_detail(path)
            readers = detail.get("readers") if isinstance(detail, dict) else None
            if not isinstance(readers, list):
                continue
            for reader in readers:
                if not isinstance(reader, dict):
                    continue
                protocol = reader.get("protocol") or reader.get("proto")
                if protocol and str(protocol).lower() != "rtsp":
                    continue
                clients.append(
                    {
                        "path": path,
                        "id": reader.get("id"),
                        "protocol": protocol,
                        "remote_addr": reader.get("remoteAddr") or reader.get("remote_addr"),
                        "created": reader.get("created"),
                    }
                )
        return clients

    def _get_path_detail(self, path: str) -> dict:
        base = self.config.api_base
        urls = [
            f"{base}/v3/paths/get/{path}",
            f"{base}/v2/paths/get/{path}",
        ]
        for url in urls:
            try:
                resp = requests.get(url, timeout=5)
            except requests.RequestException:
                continue
            if resp.status_code == HTTPStatus.OK:
                try:
                    return resp.json()
                except ValueError:
                    return {}
            if resp.status_code == HTTPStatus.NOT_FOUND:
                continue
        return {}

    def validate_media_auth(
        self, payload: MediaAuthPayloadSchema
    ) -> MediaAuthResponseSchema:
        if not self.config.token_auth_enabled:
            return MediaAuthResponseSchema(ok=True)

        token = self._extract_token_from_query(payload.query or "")
        if not token:
            raise AppError("token not found", HTTPStatus.UNAUTHORIZED)

        try:
            data = jwt.decode(token, self.config.jwt_secret, algorithms=["HS256"])
        except Exception:
            raise AppError("invalid token", HTTPStatus.UNAUTHORIZED)

        self._validate_claim(data.get("path"), payload.path, "path mismatch")
        self._validate_allowed(data.get("actions", ["read"]), payload.action, "action")
        self._validate_allowed(
            data.get("protocols", ["rtsp", "hls", "webrtc"]),
            payload.protocol,
            "protocol",
        )
        return MediaAuthResponseSchema(ok=True)

    def _ensure_path(self, stream_path: str, source: str, source_on_demand: bool):
        exists = self._mtx_get_path(stream_path)
        if exists:
            return
        self._mtx_add_path(stream_path, source, source_on_demand)

    def _mtx_get_path(self, stream_path: str) -> bool:
        url = f"{self.config.api_base}/v3/config/paths/get/{stream_path}"
        try:
            resp = requests.get(url, timeout=5)
        except requests.RequestException as exc:
            self.logger.exception("MediaMTX path get failed")
            raise AppError(
                f"MediaMTX config check failed: {exc}", HTTPStatus.BAD_GATEWAY
            )
        if resp.status_code == HTTPStatus.OK:
            return True
        if resp.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST):
            return False
        raise AppError(
            f"MediaMTX config check failed: {resp.status_code} {resp.text}",
            HTTPStatus.BAD_GATEWAY,
        )

    def _mtx_add_path(self, stream_path: str, source: str, source_on_demand: bool):
        url = f"{self.config.api_base}/v3/config/paths/add/{stream_path}"
        body = {
            "source": source,
            "sourceOnDemand": source_on_demand,
            "sourceProtocol": self.config.source_protocol,
        }
        try:
            resp = requests.post(url, json=body, timeout=5)
        except requests.RequestException as exc:
            self.logger.exception("MediaMTX path add failed")
            raise AppError(
                f"MediaMTX path add failed: {exc}", HTTPStatus.BAD_GATEWAY
            )
        if resp.status_code != HTTPStatus.OK:
            raise AppError(
                f"MediaMTX path add failed: {resp.status_code} {resp.text}",
                HTTPStatus.BAD_GATEWAY,
            )

    def _mtx_delete_path(self, stream_path: str) -> None:
        url = f"{self.config.api_base}/v3/config/paths/delete/{stream_path}"
        try:
            resp = requests.post(url, timeout=5)
        except requests.RequestException as exc:
            self.logger.exception("MediaMTX path delete failed")
            raise AppError(
                f"MediaMTX path delete failed: {exc}", HTTPStatus.BAD_GATEWAY
            )
        if resp.status_code in (HTTPStatus.OK, HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST):
            return
        raise AppError(
            f"MediaMTX path delete failed: {resp.status_code} {resp.text}",
            HTTPStatus.BAD_GATEWAY,
        )

    def _build_urls(self, stream_path: str, token: str | None) -> dict[str, str]:
        base_urls = {
            "rtsp": f"rtsp://{self.config.public_host}:{self.config.rtsp_port}/{stream_path}",
            "hls": f"http://{self.config.public_host}:{self.config.hls_port}/{stream_path}/index.m3u8",
            "webrtc": f"http://{self.config.public_host}:{self.config.webrtc_port}/{stream_path}/whep",
        }
        if not token:
            return base_urls
        return {k: f"{url}?token={token}" for k, url in base_urls.items()}

    def _make_token(self, path: str, allow_protocols: Iterable[str] | None = None):
        if not self.config.token_auth_enabled:
            return None, None
        now = int(time.time())
        allow_protocols = (
            tuple(allow_protocols) if allow_protocols else ("rtsp", "hls", "webrtc")
        )
        payload = {
            "sub": "mediamtx-client",
            "path": path,
            "actions": ["read"],
            "protocols": list(allow_protocols),
            "exp": now + self.config.token_ttl_sec,
            "iat": now,
        }
        token = jwt.encode(payload, self.config.jwt_secret, algorithm="HS256")
        return token, datetime.fromtimestamp(payload["exp"])

    def _derive_stream_path(self, source: str) -> str:
        normalized = source.strip().lower()
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        return f"cam-{digest[:12]}"

    def _extract_token_from_query(self, query: str) -> str | None:
        parsed = parse_qs(query.lstrip("?"))
        tokens = parsed.get("token", [])
        return tokens[0] if tokens else None

    def _validate_claim(self, claim_value: str | None, actual: str | None, msg: str):
        if actual and claim_value not in (actual, "*"):
            raise AppError(msg, HTTPStatus.UNAUTHORIZED)

    def _validate_allowed(
        self, allowed: Iterable[str] | None, value: str | None, label: str
    ):
        if value is None:
            return
        allowed = allowed or []
        if "*" in allowed:
            return
        if value not in allowed:
            raise AppError(
                f"{label} '{value}' not allowed", HTTPStatus.UNAUTHORIZED
            )

    def _require_company(self):
        if self._has_company_field() and self.company is None:
            raise AppError("company context required", HTTPStatus.FORBIDDEN)
