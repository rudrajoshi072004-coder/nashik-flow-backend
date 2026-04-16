from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedUUIDModel


class Payout(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PROCESSED = "processed", "Processed"

    driver = models.ForeignKey("drivers.DriverProfile", on_delete=models.PROTECT, related_name="payouts")
    wallet = models.ForeignKey("wallets.Wallet", on_delete=models.PROTECT, related_name="payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    requested_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_payouts")
    processed_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="processed_payouts")
    processed_reference = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [models.CheckConstraint(check=Q(amount__gt=0), name="payout_amount_gt_zero")]
