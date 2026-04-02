from django.db import models


class SMSInfoTable(models.Model):
    """Represents a single row in the legacy `SMS_INFO` table."""

    user_name = models.CharField(max_length=100, null=True, blank=True)
    ph_num = models.CharField(max_length=30, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    title = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "SMS_INFO"
        indexes = [
            models.Index(fields=["user_name"]),
            models.Index(fields=["ph_num"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_name or 'Unknown'} ({self.ph_num or 'no number'})"
