from typing import Optional

from ninja import Field, Schema


class MessageSchema(Schema):
    message: str


class ErrorSchema(Schema):
    detail: str


class PaginationSchema(Schema):
    current_page: int = Field(..., description="현재 보고 있는 페이지의 번호")
    total_pages: int = Field(
        ...,
        description="전체 페이지 수를 나타냅니다. ex) total_times = 100개 per_page = 10개 = total_pages는 10",
    )
    per_page: int = Field(..., description="각 페이지에 표시할 아이템의 수 (단위)")
    total_items: int = Field(..., description="전체 아이템의 수")
    has_previous: bool = Field(
        ...,
        description="현재 페이지가 첫 페이지인지 아닌지를 나타냅니다. 첫 페이지면 False, 아니면 True",
    )
    has_next: bool = Field(
        ...,
        description="현재 페이지가 마지막 페이지인지 아닌지를 나타냅니다. 마지막 페이지면 False, 아니면 True",
    )


class FileResponseSchema(Schema):
    file_url: Optional[str] = None
    file_name: Optional[str] = None


class LinkSchema(Schema):
    id: int = Field(..., description="글 ID")
    title: str = Field(..., description="글 제목")
