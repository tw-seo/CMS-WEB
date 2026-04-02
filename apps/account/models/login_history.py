from django.db import models

class AccountLoginHistory(models.Model):
    account = models.ForeignKey("account.Account", on_delete=models.CASCADE)
    logged_in_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    client_type = models.CharField(max_length=32, blank=True, null=True)
    agent_id = models.CharField(max_length=128, blank=True, null=True, db_index=True)

    class Meta:
        db_table = "account_login_history"
