from __future__ import annotations

from typing import List, Optional

from ninja import Schema
from pydantic import Field


class PermissionGroupSchema(Schema):
    name: str


class PermissionGroupResponseSchema(PermissionGroupSchema):
    id: int


class MenuPermissionSchema(Schema):
    id: int = Field(..., description="메뉴 ID")
    name: str = Field(..., description="메뉴명")
    permissions: bool = Field(..., description="접근/표시 허용 여부")
    parent: Optional[int] = Field(None, description="부모 메뉴 ID")
    submenu: List["MenuPermissionSchema"] = Field(
        default_factory=list, description="하위 메뉴"
    )


class UpdatePermissionSchema(Schema):
    permissions: bool
