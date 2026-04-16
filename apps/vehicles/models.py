from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class Vehicle(TimeStampedUUIDModel, SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        MAINTENANCE = "maintenance", "Maintenance"

    driver = models.ForeignKey("drivers.DriverProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicles")
    category = models.ForeignKey("vehicle_categories.VehicleCategory", on_delete=models.PROTECT, related_name="vehicles")
    registration_number = models.CharField(max_length=32, db_index=True)
    brand = models.CharField(max_length=64, blank=True)
    model_name = models.CharField(max_length=64, blank=True)
    manufacture_year = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["registration_number"],
                condition=Q(is_deleted=False),
                name="uniq_active_vehicle_registration",
            )
        ]
