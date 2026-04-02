from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError

from apps.account.models import Account, AccountLoginHistory
from apps.cms.models import AgentNode, AgentTargetState
from apps.cms.schemas import AgentHeartbeatRequest, AgentPolicyResponse, AgentPolicyTarget

agent_router = Router(tags=["Agent"])


class AgentPolicyQuery(Schema):
    agent_id: str = Field(description="Agent node id")


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _normalize_client_type(raw: Optional[str]) -> str:
    value = (raw or "").strip().lower()
    if value in {"main_viewer", "sub_viewer"}:
        return value
    return "sub_viewer"


def _resolve_role(account: Optional[Account]) -> str:
    if account is None:
        return "viewer"
    if account.is_superuser:
        return "superuser"
    if account.is_staff:
        return "admin"
    return "viewer"


def _build_policy_version(*moments: Optional[datetime]) -> int:
    available = [item for item in moments if item is not None]
    if not available:
        return int(datetime.now().timestamp())
    return int(max(available).timestamp())


@agent_router.post(
    "/heartbeat",
    auth=None,
    summary="Receive agent heartbeat",
    description="Persist latest agent and target statuses.",
)
def heartbeat(request, payload: AgentHeartbeatRequest):
    agent_id = (payload.agent.node_id or "").strip()
    if not agent_id:
        raise HttpError(400, "agent.node_id is required.")

    now = datetime.now()
    heartbeat_dt = _parse_iso_datetime(payload.timestamp) or now

    node, _ = AgentNode.objects.get_or_create(agent_id=agent_id)
    node.hostname = (payload.agent.hostname or "").strip()
    node.role = (payload.agent.role or "").strip()
    node.status = (payload.status or "unknown").strip() or "unknown"
    node.last_seen_at = heartbeat_dt
    node.last_heartbeat_payload = payload.model_dump()
    node.save()

    for item in payload.targets:
        target_name = (item.name or "").strip()
        if not target_name:
            continue
        AgentTargetState.objects.update_or_create(
            agent=node,
            target_name=target_name,
            defaults={
                "kind": (item.kind or "").strip(),
                "enabled": bool(item.enabled),
                "running": item.running,
                "fail_count": int(item.fail_count or 0),
                "restart_count": int(item.restart_count or 0),
                "last_checked_at": _parse_iso_datetime(item.last_checked_at),
                "last_restart_at": _parse_iso_datetime(item.last_restart_at),
                "last_error": (item.last_error or "").strip(),
            },
        )

    return {"ok": True, "agent_id": agent_id, "target_count": len(payload.targets)}


@agent_router.get(
    "/policy",
    auth=None,
    summary="Resolve watchdog policy by agent id",
    response=AgentPolicyResponse,
)
def policy(
    request,
    agent_id: str = Query(..., description="Agent node id"),
):
    agent_id = (agent_id or "").strip()
    if not agent_id:
        raise HttpError(400, "agent_id is required.")

    node = AgentNode.objects.filter(agent_id=agent_id).first()
    latest_login = (
        AccountLoginHistory.objects.filter(agent_id=agent_id)
        .select_related("account")
        .order_by("-logged_in_at", "-id")
        .first()
    )

    account = latest_login.account if latest_login else None
    role = _resolve_role(account)
    account_key = str(account.account_key) if account else (node.account_key_last if node else None)

    if latest_login:
        client_type = _normalize_client_type(latest_login.client_type)
    elif node:
        client_type = _normalize_client_type(node.client_type_last)
    else:
        client_type = "sub_viewer"

    has_dl_target = AgentTargetState.objects.filter(
        agent_id=agent_id,
        target_name__istartswith="dl",
    ).exists()
    enable_dl_watchdog = client_type == "main_viewer" and has_dl_target

    targets = [
        AgentPolicyTarget(name="gui", enabled=True, auto_restart=True),
        AgentPolicyTarget(
            name="dl",
            enabled=enable_dl_watchdog,
            auto_restart=enable_dl_watchdog,
        ),
    ]

    if node:
        node.account_key_last = account_key
        node.client_type_last = client_type
        if role:
            node.role = role
        node.save(update_fields=["account_key_last", "client_type_last", "role", "updated_at"])

    return AgentPolicyResponse(
        agent_id=agent_id,
        account_key=account_key,
        client_type=client_type,
        role=role,
        policy_version=_build_policy_version(
            latest_login.logged_in_at if latest_login else None,
            node.updated_at if node else None,
        ),
        targets=targets,
    )
