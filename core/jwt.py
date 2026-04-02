import os
from typing import Any, Optional, cast

import jwt
from apps.account.models import Account
from jwt import ExpiredSignatureError, InvalidTokenError
from ninja.security import HttpBearer

SECRET_KEY = "0m-%p7jel*ft3%u5kt1^_dulf_&%78j$=_01w1ik&vb@%x%f93"
ALGORITHM = "HS256"
LEEWAY_SECONDS = 60


def _need_auth() -> bool:
    return os.getenv("NEED_AUTH", "true").lower() == "true"


class JWTAuth(HttpBearer):
    def __call__(self, request: Any):
        if not _need_auth():
            return self._bypass_user()
        return super().__call__(request)

    def authenticate(self, request: Any, token: str) -> Optional[Account]:
        if not _need_auth():
            return self._bypass_user()
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"require": ["exp", "iat"]},
                leeway=LEEWAY_SECONDS,
            )

            # typ 검사
            typ = payload.get("typ")
            if typ and typ != "access":
                return None

            sub = payload.get("sub")
            if not sub:
                return None

            # DB 조회 (권한/그룹이 필요하면 select_related 추후 추가 해야함)
            user = cast(
                Account,
                Account.objects.select_related("permission_group").get(id=int(sub)),
            )

            # 비활성화 사용자 차단
            if not user.is_active:
                return None

            return user

        except ExpiredSignatureError:
            return None
        except (InvalidTokenError, Account.DoesNotExist, ValueError, TypeError):
            return None

    def _bypass_user(self) -> Account:
        try:
            user = Account.objects.select_related("permission_group", "company").first()
        except Exception:
            user = None
        if user:
            return user
        try:
            from apps.company.models import Company
            from apps.masterdata.models import PermissionGroup

            company = Company.objects.first()
            group = PermissionGroup.objects.first()
            if company and group:
                return Account(
                    company=company,
                    permission_group=group,
                    is_active=True,
                    username="dev-bypass",
                )
            if company:
                return Account(company=company, is_active=True, username="dev-bypass")
        except Exception:
            pass
        return Account(is_active=True, username="dev-bypass")
