from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class PricingRule(TimeStampedUUIDModel, SoftDeleteModel):
    city = models.CharField(max_length=64, default="Nashik", db_index=True)
    vehicle_category = models.ForeignKey("vehicle_categories.VehicleCategory", on_delete=models.CASCADE, related_name="pricing_rules")
    name = models.CharField(max_length=120)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    per_km_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    per_min_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    surge_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    night_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cancellation_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["city", "active", "starts_at"])]
        constraints = [
            models.CheckConstraint(check=Q(surge_multiplier__gte=1), name="pricing_surge_gte_one"),
            models.CheckConstraint(check=Q(base_fare__gte=0), name="pricing_base_fare_gte_zero"),
        ]
