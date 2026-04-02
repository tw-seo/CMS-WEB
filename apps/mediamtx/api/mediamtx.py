from http import HTTPStatus
from typing import Any, Literal
from urllib.parse import urlparse

from core.exceptions import AppError
from core.schema import ErrorSchema
from core.utils.http import resp
from ninja import Field, Query, Router, Schema
from pydantic import AliasChoices

from apps.account.models import Account
from apps.cms.models import ViewerManage
from apps.mediamtx.schemas import (
    MediaAuthPayloadSchema,
    MediaAuthResponseSchema,
    MediaStreamResponseSchema,
    MediaWatchdogStatusSchema,
    StreamRequestSchema,
    StreamResponseSchema,
)
from apps.mediamtx.services import MediaMtxService
from apps.mediamtx.services.registry import get_rtsp_mapping_snapshot
from apps.mediamtx.services.watchdog import get_watchdog_snapshot

mediamtx_router = Router(tags=["MediaMTX"])


class MediaListLoginIn(Schema):
    user_id: str = Field(
        description="Account id",
        validation_alias=AliasChoices("user_id", "userId", "id"),
    )
    pw: str = Field(description="Password", validation_alias=AliasChoices("pw", "password"))


class ViewerStreamIssueIn(MediaListLoginIn):
    camera_key: str = Field(
        description="Camera info key",
        validation_alias=AliasChoices("camera_key", "cameraKey"),
    )
    stream_variant: Literal["cctv", "ai"] = Field(
        default="cctv",
        description="Requested stream variant",
        validation_alias=AliasChoices("stream_variant", "streamVariant", "variant"),
    )


def _authenticate_viewer(user_id: str, password: str):
    if not user_id or not password:
        return None

    return (
        Account.objects.filter(username=user_id, is_active=True, is_deleted=False)
        .only("account_key", "is_superuser", "is_staff", "password")
        .first()
    )


def _resolve_allowed_camera_keys(account: Account, snapshot: dict[str, list[str]]) -> list[str]:
    if account.is_superuser or account.is_staff:
        return sorted(snapshot.keys())

    keys_set: set[str] = set()
    rows = ViewerManage.objects.filter(user_key=str(account.account_key)).values_list(
        "camera_keys", flat=True
    )
    for item in rows:
        if not item:
            continue
        for key in item:
            if key:
                keys_set.add(str(key))
    return sorted(keys_set)


def _extract_stream_path(rtsp_url: str) -> str:
    if not rtsp_url:
        return ""

    parsed = urlparse(rtsp_url)
    return parsed.path.lstrip("/")


@mediamtx_router.post(
    "/streams/issue-url",
    operation_id="mediamtx_issue_url",
    summary="영상분배 서버 스트림 URL 발급 요청",
    response={
        HTTPStatus.OK: StreamResponseSchema,
        HTTPStatus.BAD_REQUEST: ErrorSchema,
        HTTPStatus.UNAUTHORIZED: ErrorSchema,
        HTTPStatus.FORBIDDEN: ErrorSchema,
        HTTPStatus.BAD_GATEWAY: ErrorSchema,
    },
)
def issue_stream_url(
    request: Any,
    camera_key: str,
    original_rtsp: str ,
    stream_type: Literal["rtsp", "hls", "webrtc"],
    source_on_demand: bool | None,
):
    service = MediaMtxService(company=getattr(request.auth, "company", None))
    try:
        payload = StreamRequestSchema(
            camera_key=camera_key,
            original_rtsp=original_rtsp,
            stream_type=stream_type,
            source_on_demand=source_on_demand,
        )
        data = service.issue_stream(
            payload, requested_by=getattr(request, "auth", None)
        )
    except AppError as exc:
        return resp(exc.status, exc.detail)
    return resp(HTTPStatus.OK, data)


@mediamtx_router.get(
    "/streams",
    operation_id="mediamtx_streams",
    summary="영상분배 서버 스트림 목록 조회",
    response={
        HTTPStatus.OK: list[MediaStreamResponseSchema],
        HTTPStatus.FORBIDDEN: ErrorSchema,
    },
)
def list_streams(request: Any):
    service = MediaMtxService(company=getattr(request.auth, "company", None))
    try:
        data = service.list_streams()
    except AppError as exc:
        return resp(exc.status, exc.detail)
    return resp(HTTPStatus.OK, data)


@mediamtx_router.post(
    "/list/",
    operation_id="mediamtx_list_rtsp",
    summary="MediaMTX RTSP mapping list",
    response={HTTPStatus.OK: dict[str, list[str]]},
)
def list_rtsp_mappings(request: Any):
    return resp(HTTPStatus.OK, get_rtsp_mapping_snapshot())


@mediamtx_router.post(
    "/list-login/",
    operation_id="mediamtx_list_login_rtsp",
    summary="MediaMTX RTSP mapping list with account auth",
    response={HTTPStatus.OK: dict[str, list[str]]},
)
def list_rtsp_mappings_login(request: Any, payload: MediaListLoginIn):
    user_id = (payload.user_id or "").strip()
    password = payload.pw or ""
    if not user_id or not password:
        return resp(HTTPStatus.OK, [])

    account = _authenticate_viewer(user_id, password)
    if not account or not account.check_password(password):
        return resp(HTTPStatus.OK, [])

    snapshot = get_rtsp_mapping_snapshot()
    keys = _resolve_allowed_camera_keys(account, snapshot)

    results: dict[str, list[str]] = {}
    for camera_key in keys:
        entry = snapshot.get(camera_key) or []
        results[str(camera_key)] = [
            str(entry[0]) if len(entry) > 0 else "",
            str(entry[1]) if len(entry) > 1 else "",
            str(entry[2]) if len(entry) > 2 else "",
            str(entry[3]) if len(entry) > 3 else "",
        ]
    return resp(HTTPStatus.OK, results)


@mediamtx_router.post(
    "/streams/issue-viewer-url",
    operation_id="mediamtx_issue_viewer_url",
    summary="뷰어 계정 기반 MediaMTX WebRTC URL 발급",
    response={
        HTTPStatus.OK: StreamResponseSchema,
        HTTPStatus.UNAUTHORIZED: ErrorSchema,
        HTTPStatus.FORBIDDEN: ErrorSchema,
        HTTPStatus.NOT_FOUND: ErrorSchema,
    },
)
def issue_viewer_stream_url(request: Any, payload: ViewerStreamIssueIn):
    user_id = (payload.user_id or "").strip()
    password = payload.pw or ""
    camera_key = (payload.camera_key or "").strip()

    account = _authenticate_viewer(user_id, password)
    if not account or not account.check_password(password):
        return resp(HTTPStatus.UNAUTHORIZED, "invalid viewer credentials")

    snapshot = get_rtsp_mapping_snapshot()
    allowed_keys = set(_resolve_allowed_camera_keys(account, snapshot))
    if camera_key not in allowed_keys:
        return resp(HTTPStatus.FORBIDDEN, "camera access denied")

    entry = snapshot.get(camera_key) or []
    stream_index = 3 if payload.stream_variant == "ai" else 1
    mediamtx_rtsp = str(entry[stream_index]) if len(entry) > stream_index else ""
    stream_path = _extract_stream_path(mediamtx_rtsp)
    if not stream_path:
        return resp(HTTPStatus.NOT_FOUND, "stream path not found")

    service = MediaMtxService()
    token, _ = service._make_token(stream_path, allow_protocols=("webrtc",))
    urls = service._build_urls(stream_path, token)
    return resp(
        HTTPStatus.OK,
        StreamResponseSchema(
            path=stream_path,
            stream_type="webrtc",
            requested_url=urls["webrtc"],
            all_urls=urls,
            note=f"viewer={user_id}, variant={payload.stream_variant}",
            token=token,
        ),
    )


@mediamtx_router.post(
    "/media/auth",
    auth=None,
    operation_id="mediamtx_auth",
    response={
        HTTPStatus.OK: MediaAuthResponseSchema,
        HTTPStatus.UNAUTHORIZED: ErrorSchema,
    },
)
def media_auth(request: Any, payload: MediaAuthPayloadSchema):
    service = MediaMtxService()
    try:
        data = service.validate_media_auth(payload)
    except AppError as exc:
        return resp(exc.status, exc.detail)
    return resp(HTTPStatus.OK, data)


@mediamtx_router.get(
    "/watchdog",
    operation_id="mediamtx_watchdog_status",
    summary="MediaMTX watchdog status",
    response={HTTPStatus.OK: MediaWatchdogStatusSchema},
)
def watchdog_status(request: Any):
    return resp(HTTPStatus.OK, get_watchdog_snapshot())


@mediamtx_router.get(
    "/cliten_list",
    operation_id="mediamtx_client_list",
    summary="MediaMTX RTSP client connections list",
    response={
        HTTPStatus.OK: dict,
        HTTPStatus.BAD_GATEWAY: ErrorSchema,
        HTTPStatus.FORBIDDEN: ErrorSchema,
    },
)
def client_list(request: Any):
    service = MediaMtxService(company=getattr(request.auth, "company", None))
    try:
        data = service.list_rtsp_clients()
    except AppError as exc:
        return resp(exc.status, exc.detail)
    return resp(HTTPStatus.OK, data)
