from django.db import transaction

from core.services.base import BaseService

from apps.account.models import Account, AccountLoginHistory
from apps.account.schemas import LoginHistorySchema, PasswordChangeSchema


class AccountService(BaseService[Account, object]):
    model = Account

    def get_login_history(self, account: Account, limit: int = 90) -> list[LoginHistorySchema]:
        qs = (
            AccountLoginHistory.objects.filter(account=account)
            .order_by("-logged_in_at")[:limit]
        )
        return [
            LoginHistorySchema(
                logged_in_at=item.logged_in_at,
                ip_address=item.ip_address,
                user_agent=item.user_agent,
            )
            for item in qs
        ]

    @transaction.atomic
    def change_password(self, account: Account, payload: PasswordChangeSchema) -> Account:
        if not account.check_password(payload.current_password):
            raise ValueError("현재 비밀번호가 올바르지 않습니다.")
        account.set_password(payload.new_password)
        account.save(update_fields=["password"])
        return account
