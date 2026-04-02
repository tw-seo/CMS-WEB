from django.db import models

from .agent_node import AgentNode


class AgentTargetState(models.Model):
    id = models.BigAutoField(primary_key=True)
    agent = models.ForeignKey(
        AgentNode,
        on_delete=models.CASCADE,
        related_name="target_states",
        db_column="agent_id",
        to_field="agent_id",
    )
    target_name = models.CharField(max_length=64)
    kind = models.CharField(max_length=32, blank=True, default="")
    enabled = models.BooleanField(default=True)
    running = models.BooleanField(blank=True, null=True)
    fail_count = models.IntegerField(default=0)
    restart_count = models.IntegerField(default=0)
    last_checked_at = models.DateTimeField(blank=True, null=True)
    last_restart_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "AGENT_TARGET_STATE"
        constraints = [
            models.UniqueConstraint(fields=["agent", "target_name"], name="uq_agent_target_name"),
        ]

