from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Payment(TimeStampedUUIDModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        WALLET = "wallet", "Wallet"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT, related_name="payments")
    customer = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=16, choices=Method.choices, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_ref = models.CharField(max_length=128, unique=True)
    gateway_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["booking", "status"])]
