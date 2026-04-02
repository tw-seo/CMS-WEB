from django.db import models


class AgentNode(models.Model):
    agent_id = models.CharField(
        max_length=128,
        primary_key=True,
        db_column="agent_id",
    )
    hostname = models.CharField(max_length=255, blank=True, default="")
    role = models.CharField(max_length=64, blank=True, default="")
    account_key_last = models.CharField(max_length=50, blank=True, null=True)
    client_type_last = models.CharField(max_length=32, blank=True, null=True)
    status = models.CharField(max_length=32, blank=True, default="unknown")
    last_seen_at = models.DateTimeField(blank=True, null=True)
    last_heartbeat_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "AGENT_NODE"

