from typing import Literal

from ninja import Field, Schema


class StreamRequestSchema(Schema):
    camera_key: str
    original_rtsp: str
    stream_type: Literal["rtsp", "hls", "webrtc"]
    source_on_demand: bool | None


class StreamResponseSchema(Schema):
    path: str
    stream_type: str
    requested_url: str
    all_urls: dict[str, str]
    note: str
    token: str | None = None


class MediaAuthPayloadSchema(Schema):
    path: str | None = None
    protocol: str | None = None
    action: str | None = None
    query: str | None = None
    ip: str | None = None
    user: str | None = None


class MediaAuthResponseSchema(Schema):
    ok: bool


class MediaStreamResponseSchema(Schema):
    id: int
    camera_key: str
    stream_path: str
    original_rtsp: str
    stream_type: str
    source_on_demand: bool
    token_auth_enabled: bool


class MediaStreamRtspMapSchema(Schema):
    camera_key: str
    original_rtsp: str
    mediamtx_rtsp: str
    dl_rtsp: str = ""
    mtx_dl_rtsp: str = ""


class MediaWatchdogStatusSchema(Schema):
    enabled: bool
    running: bool
    api_base: str | None = None
    health_url: str | None = None
    docker_container: str | None = None
    last_ok: bool | None = None
    last_checked_at: str | None = None
    last_error: str | None = None
    last_restart_at: str | None = None
    last_restart_ok: bool | None = None
    last_restart_error: str | None = None
