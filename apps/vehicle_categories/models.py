from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class VehicleCategory(TimeStampedUUIDModel, SoftDeleteModel):
    name = models.CharField(max_length=64, unique=True)
    icon = models.CharField(max_length=128, blank=True)
    payload_type = models.CharField(max_length=64)
    max_weight_kg = models.DecimalField(max_digits=10, decimal_places=2)
    max_volume_m3 = models.DecimalField(max_digits=10, decimal_places=2)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2)
    per_km_rate = models.DecimalField(max_digits=10, decimal_places=2)
    waiting_per_min = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    helper_supported = models.BooleanField(default=False)
    intra_city_available = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    priority_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["priority_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(is_deleted=False),
                name="uniq_active_vehicle_category_name",
            )
        ]

    def __str__(self) -> str:
        return self.name
