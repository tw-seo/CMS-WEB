from ninja import Schema

from datetime import datetime

class AccountUpdateSchema(Schema):
    department: str | None = None
    position: str | None = None
    phone_number: str | None = None
    office_phone: str | None = None

class PasswordChangeSchema(Schema):
    current_password: str
    new_password: str

class LoginHistorySchema(Schema):
    logged_in_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
