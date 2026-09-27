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
    onboarding_submitted_at = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False, db_index=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_trips = models.PositiveIntegerField(default=0)
    owner_name = models.CharField(max_length=128, blank=True, default="")
    will_drive_vehicle = models.BooleanField(null=True, blank=True)
    driver_name = models.CharField(max_length=128, blank=True, default="")
    driver_phone = models.CharField(max_length=20, blank=True, default="")
    vehicle_number = models.CharField(max_length=32, blank=True, default="")
    vehicle_type = models.CharField(max_length=32, blank=True, default="")
    vehicle_body_type = models.CharField(max_length=32, blank=True, default="")
    truck_body_detail = models.CharField(max_length=32, blank=True, default="")
    three_wheeler_body_type = models.CharField(max_length=32, blank=True, default="")
    fuel_type = models.CharField(max_length=16, blank=True, default="")
    operation_city = models.CharField(max_length=64, blank=True, default="")

    def public_display_name(self) -> str:
        """Name shown to the customer. Never fall back to the phone number."""
        user = self.user
        phone = (getattr(user, "phone", "") or "").strip()
        first = (getattr(user, "first_name", "") or "").strip()
        last = (getattr(user, "last_name", "") or "").strip()
        full = " ".join(part for part in (first, last) if part).strip()
        for raw in (self.driver_name, self.owner_name, full, first):
            text = (raw or "").strip()
            if not text or text == phone:
                continue
            digits = "".join(ch for ch in text if ch.isdigit())
            if len(digits) >= 10:
                continue
            return text
        return "Driver"

    class Meta:
        indexes = [models.Index(fields=["kyc_status", "is_online"])]
