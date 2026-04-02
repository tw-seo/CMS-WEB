from typing import List

from ninja import Schema
from pydantic import Field

from apps.masterdata.schemas.permissions import MenuPermissionSchema


class LoginSchema(Schema):
    username: str = Field(..., example="ksol", description="사용자 ID")
    password: str = Field(..., example="123123a!", description="비밀번호")


class TokenResponseSchema(Schema):
    id: int
    company_id: int
    access_token: str = Field(..., description="JWT 액세스 토큰")
    is_superuser: bool
    username: str = Field(..., description="로그인 ID")
    menu_permissions: List[MenuPermissionSchema] = Field(default_factory=list, description="메뉴 권한 트리")
    license_allowed: bool = Field(..., description="라이선스 허용 여부")
    license_expires_at: str | None = Field(None, description="라이선스 만료 일시 (없을 수도 있음)")
