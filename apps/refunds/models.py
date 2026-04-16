from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Refund(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        PROCESSED = "processed", "Processed"
        REJECTED = "rejected", "Rejected"

    payment = models.ForeignKey("payments.Payment", on_delete=models.PROTECT, related_name="refunds")
    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    processed_reference = models.CharField(max_length=128, blank=True)
    processed_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]
