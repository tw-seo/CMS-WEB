from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict

import jwt
from core.exceptions import AppError
from django.contrib.auth.hashers import check_password

from apps.account.models.account import Account
from apps.account.models.login_history import AccountLoginHistory
from apps.masterdata.services import PermissionService
from apps.pms.services.auth import PmsLicenseAuthService


class AuthService:
    def __init__(self):
        self.secret = "0m-%p7jel*ft3%u5kt1^_dulf_&%78j$=_01w1ik&vb@%x%f93"
        self.alg = "HS256"
        self.pms_auth_service = PmsLicenseAuthService()
        self.ttl = timedelta(days=1)

    def _encode(self, payload: Dict) -> str:
        return jwt.encode(payload, self.secret, algorithm=self.alg)

    def create_access_token(self, user: Account) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "iat": int(now.timestamp()),
            "exp": int((now + self.ttl).timestamp()),
            "typ": "access",
        }
        return self._encode(payload)

    def login(self, request: Any, username: str, password: str) -> dict:
        user = (
            Account.objects.filter(username=username)
            .first()
        )

        if not user or not check_password(password, user.password):
            raise AppError(
                "아이디 또는 비밀번호가 올바르지 않습니다.", HTTPStatus.BAD_REQUEST
            )
        if not user.is_active:
            raise AppError("비활성화된 계정입니다.", HTTPStatus.BAD_REQUEST)

        # NOTE: Account model no longer has company_id/permission_group.
        # Keep login working by skipping these until the data model is aligned.
        license_info = self.pms_auth_service.verify_login(user.username, None)

        AccountLoginHistory.objects.create(
            account=user,
            ip_address=request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR")),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return {
            "id": user.id,
            "company_id": None,
            "access_token": self.create_access_token(user),
            "is_superuser": user.is_superuser,
            "username": user.username,
            "menu_permissions": [],
            "license_allowed": license_info.allowed,
            "license_expires_at": license_info.expires_at,
        }
