from core.schemas.file import FileSchema
from ninja import Schema


class CompanyCreateSchema(Schema):
    # TODO(0826): 필드 픽스는 추후
    name: str | None = None
    representative: str | None = None
    registration_number: str | None = None
    """
    name: str
    representative: Optional[str] = None
    registration_number: Optional[str] = None
    phone_number: Optional[str] = None
    fax_number: Optional[str] = None
    address: Optional[str] = None
    business_item: Optional[str] = None
    business_type: Optional[str] = None
    emission_factor_setting: Optional[str] = None
    esg_evaluation_setting: Optional[str] = None
    industry_setting: Optional[str] = None
    """


class CompanyUpdateSchema(Schema):
    name: str | None = None
    representative: str | None = None
    registration_number: str | None = None


class CompanyResponseSchema(Schema):
    id: int
    name: str | None
    representative: str | None
    registration_number: str | None
    file: FileSchema | None = None
