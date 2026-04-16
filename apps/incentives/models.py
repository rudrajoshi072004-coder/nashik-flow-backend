from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Incentive(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        EARNED = "earned", "Earned"
        PAID = "paid", "Paid"
        EXPIRED = "expired", "Expired"

    driver = models.ForeignKey("drivers.DriverProfile", on_delete=models.CASCADE, related_name="incentives")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL, related_name="incentives")
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    criteria = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["driver", "status", "created_at"])]
