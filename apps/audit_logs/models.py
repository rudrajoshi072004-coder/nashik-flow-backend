from django.db import models

from apps.common.models import TimeStampedUUIDModel


class AdminLog(TimeStampedUUIDModel):
    actor = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="admin_logs")
    action = models.CharField(max_length=128, db_index=True)
    module = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["module", "action", "created_at"])]
