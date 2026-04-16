from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class Notification(TimeStampedUUIDModel, SoftDeleteModel):
    class Category(models.TextChoices):
        BOOKING = "booking", "Booking"
        WALLET = "wallet", "Wallet"
        SYSTEM = "system", "System"
        SUPPORT = "support", "Support"

    recipient = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=16, choices=Category.choices, db_index=True)
    title = models.CharField(max_length=140)
    message = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["recipient", "is_read", "created_at"])]
