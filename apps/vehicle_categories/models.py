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
    base_fare_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Kilometres covered by the base fare. Per-km rate applies after this distance.",
    )
    per_km_rate = models.DecimalField(max_digits=10, decimal_places=2)
    waiting_per_min = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstation_base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstation_base_fare_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Kilometres covered by the outstation base fare. Per-km rate applies after this distance.",
    )
    outstation_per_km_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstation_minimum_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstation_step_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10,
        help_text="After the 50 km outstation minimum, reduce the per-km rate on every extra block of this many kilometres.",
    )
    outstation_step_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount subtracted from the outstation per-km rate on each extra distance block.",
    )
    outstation_threshold_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Distance in km after which a trip is considered outstation for this vehicle. If 0, uses service zone radius.",
    )
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
