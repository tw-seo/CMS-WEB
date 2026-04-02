from ninja import Router, Schema
from ninja.errors import HttpError
from apps.account.models import Account, AccountLoginHistory
from apps.cms.schemas import AccountInfo, ApplyAccountInfo, AccountVerifyRequest
from django.db import transaction
from apps.cms.services.workers.viewer_notifier import notify_viewer_account_info_change
from apps.cms.models import AgentNode
account_apply_router = Router(tags=["Account"])

def _notify_lite_viewer(reason: str) -> None:
    try:
        notify_viewer_account_info_change(reason)
    except Exception as exc:
        print(f"[viewer-notify][account] failed ({reason}): {exc}")


@account_apply_router.post(
    "/apply_account_infos/",
    summary="Apply account infos",
    description="Insert/update accounts and delete by account_key list.",
    response=list[AccountInfo],
)
def apply_accounts(request, payload: ApplyAccountInfo):
    delete_ids: list[str] = []
    for raw in payload.delete_keys or []:
        text = str(raw).strip()
        if not text:
            continue
        delete_ids.append(text)

    infos = payload.account_infos or []
    if not infos and not delete_ids:
        raise HttpError(400, "account_infos or delete_keys is required.")

    with transaction.atomic():
        if delete_ids:
            Account.objects.filter(
                account_key__in=delete_ids, is_superuser=False
            ).delete()

        for info in infos:
            raw_id = str(info.account_key).strip() if info.account_key is not None else ""
            account_id = raw_id if raw_id else None

            username = (info.user_id or "").strip()
            if not username:
                raise HttpError(400, "account_infos.user_id is required.")

            is_superuser = bool(info.is_superuser)
            if username != "administrator":
                is_superuser = False

            password = (info.pw or "").strip() if info.pw is not None else ""
            defaults = {
                "username": username,
                "is_superuser": is_superuser,
                "is_staff": bool(info.is_admin),
                "is_active": bool(info.is_activate),
                "created_by": info.created_by or "admin",
                "is_deleted": bool(info.is_delete),
                "first_name": info.user_name or "",
            }

            if account_id is None:
                account = (
                    Account.objects.filter(username=username)
                    .order_by("account_key")
                    .first()
                )
                if account:
                    for key, value in defaults.items():
                        setattr(account, key, value)
                    account.save()
                else:
                    account = Account.objects.create(**defaults)
                if password:
                    account.set_password(password)
                else:
                    account.set_unusable_password()
                account.save(update_fields=["password"])
            else:
                account, created = Account.objects.update_or_create(
                    account_key=account_id, defaults=defaults
                )
                if password:
                    account.set_password(password)
                    account.save(update_fields=["password"])
                elif created:
                    account.set_unusable_password()
                    account.save(update_fields=["password"])

    _notify_lite_viewer("account_apply")
    rows = Account.objects.all().order_by("account_key")
    results: list[AccountInfo] = []
    for row in rows:
        results.append(
            AccountInfo(
                account_key=str(row.account_key),
                is_superuser=row.is_superuser,
                user_id=row.username or "",
                pw=None,
                user_name=row.first_name or "",
                is_admin=row.is_staff,
                is_activate=row.is_active,
                created_by=row.created_by or "",
                is_delete=row.is_deleted,
            )
        )
    return results


@account_apply_router.post(
    "/verify_account/",
    summary="Verify account credentials",
    description="Validate account id/password and return account info.",
    response=AccountInfo,
)
def verify_account(request, payload: AccountVerifyRequest):
    user_id = (payload.user_id or "").strip()
    pw = (payload.pw or "").strip()
    if not user_id or not pw:
        raise HttpError(400, "user_id and pw are required.")

    account = Account.objects.filter(username=user_id).first()
    if account is None:
        raise HttpError(404, "Account not found.")

    if not account.check_password(pw):
        raise HttpError(401, "Invalid credentials.")

    if account.is_deleted or not account.is_active:
        raise HttpError(403, "Account is inactive.")

    requested_client_type = (payload.client_type or "").strip().lower()
    if requested_client_type not in {"main_viewer", "sub_viewer"}:
        requested_client_type = ""

    # Server-side normalization:
    # - admin/superuser accounts are treated as main_viewer
    # - normal viewer accounts are treated as sub_viewer
    if account.is_superuser or account.is_staff:
        client_type = "main_viewer"
    else:
        client_type = "sub_viewer"

    if requested_client_type and requested_client_type != client_type:
        print(
            "[account-verify] client_type normalized",
            {
                "requested": requested_client_type,
                "normalized": client_type,
                "account_key": str(account.account_key),
                "is_superuser": account.is_superuser,
                "is_admin": account.is_staff,
            },
        )
    agent_id = (payload.agent_id or "").strip()

    ip_address = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR"))
    if isinstance(ip_address, str) and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    try:
        AccountLoginHistory.objects.create(
            account=account,
            ip_address=ip_address or None,
            user_agent=user_agent or "",
            client_type=client_type or None,
            agent_id=agent_id or None,
        )
    except Exception as exc:
        print(f"[account-verify] login history save failed: {exc}")

    if agent_id:
        try:
            node, _ = AgentNode.objects.get_or_create(agent_id=agent_id)
            node.account_key_last = str(account.account_key)
            if client_type:
                node.client_type_last = client_type
            node.role = (
                "superuser" if account.is_superuser else ("admin" if account.is_staff else "viewer")
            )
            node.save(update_fields=["account_key_last", "client_type_last", "role", "updated_at"])
        except Exception as exc:
            print(f"[account-verify] agent node link failed: {exc}")

    return AccountInfo(
        account_key=str(account.account_key),
        is_superuser=account.is_superuser,
        user_id=account.username or "",
        pw=None,
        user_name=account.first_name or "",
        is_admin=account.is_staff,
        is_activate=account.is_active,
        created_by=account.created_by or "",
        is_delete=account.is_deleted,
    )


@account_apply_router.post(
    "/select_account_infos/",
    summary="계정 정보 등록 / 작제 적용 API",
    description="ACCOUNT_TABLE?? Account_Info ??? ?????.",
    response=list[AccountInfo],
)
def select_account_infos(request):
    rows = Account.objects.all().order_by("account_key")
    results: list[AccountInfo] = []
    for row in rows:
        results.append(
            AccountInfo(
                account_key=str(row.account_key),
                is_superuser=row.is_superuser,
                user_id=row.username or "",
                pw=None,
                user_name=row.first_name or "",
                is_admin=row.is_staff,
                is_activate=row.is_active,
                created_by=row.created_by or "",
                is_delete=row.is_deleted,
            )
        )
    return results
