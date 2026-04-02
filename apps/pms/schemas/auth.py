from ninja import Schema

class PmsLicenseRequest(Schema):
    username: str
    company_id: int

class PmsLicenseResponse(Schema):
    allowed: bool
    expires_at: str | None
    message: str | None = None
