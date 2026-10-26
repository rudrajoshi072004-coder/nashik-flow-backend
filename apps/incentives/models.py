from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


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

    def __str__(self) -> str:
        return f"{self.name} - {self.driver_id} ({self.amount})"


class DriverOffer(TimeStampedUUIDModel, SoftDeleteModel):
    title = models.CharField(max_length=140, help_text="Headline for the offer e.g. First 3 Rides 0% Commission")
    description = models.TextField(blank=True, default="", help_text="Promotional description / rules for the driver")
    rides_count = models.PositiveIntegerField(
        default=3,
        help_text="Number of commission-free rides (e.g. 3)",
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Commission % charged during these rides (0.00% = 100% earnings to driver)",
    )
    valid_days = models.PositiveIntegerField(
        default=7,
        help_text="Validity period in days (e.g. 7)",
    )
    start_date = models.DateField(help_text="Start date of the offer period", db_index=True)
    end_date = models.DateField(help_text="End date of the offer period", db_index=True)
    banner_url = models.TextField(
        blank=True,
        default="",
        help_text="Mandatory image banner URL or Cloudflare R2 / media path",
    )
    banner_image = models.BinaryField(null=True, blank=True)
    banner_content_type = models.CharField(max_length=64, default="image/jpeg", blank=True)
    vehicle_categories = models.ManyToManyField(
        "vehicle_categories.VehicleCategory",
        blank=True,
        related_name="driver_offers",
        help_text="If empty, applies to all vehicle categories.",
    )
    active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["active", "start_date", "end_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.rides_count} rides @ {self.commission_rate}%)"


class DriverOfferUsage(TimeStampedUUIDModel):
    offer = models.ForeignKey(DriverOffer, on_delete=models.CASCADE, related_name="usages")
    driver = models.ForeignKey("drivers.DriverProfile", on_delete=models.CASCADE, related_name="offer_usages")
    booking = models.ForeignKey("bookings.Booking", on_delete=models.CASCADE, related_name="offer_usages")
    ride_number = models.PositiveIntegerField(help_text="Ride sequence under this offer (e.g. 1, 2, 3)")
    original_commission_percent = models.DecimalField(max_digits=5, decimal_places=2)
    applied_commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    saved_commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ("offer", "booking")
        indexes = [
            models.Index(fields=["offer", "driver"]),
            models.Index(fields=["driver", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Driver {self.driver_id} - Offer {self.offer.title} - Ride #{self.ride_number}"
