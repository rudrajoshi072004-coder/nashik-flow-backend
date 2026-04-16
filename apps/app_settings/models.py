from django.db import models

from apps.common.models import TimeStampedUUIDModel


class AppSetting(TimeStampedUUIDModel):
    key = models.CharField(max_length=128, unique=True)
    value = models.JSONField(default=dict, blank=True)
    value_type = models.CharField(max_length=32, default="json")
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["is_public", "key"])]
