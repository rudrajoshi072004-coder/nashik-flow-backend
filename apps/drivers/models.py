from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class DriverProfile(TimeStampedUUIDModel, SoftDeleteModel):
    class KYCStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField("users.User", on_delete=models.CASCADE, related_name="driver_profile")
    kyc_status = models.CharField(max_length=16, choices=KYCStatus.choices, default=KYCStatus.PENDING, db_index=True)
    onboarding_completed = models.BooleanField(default=False, db_index=True)
    is_online = models.BooleanField(default=False, db_index=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_trips = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["kyc_status", "is_online"])]
