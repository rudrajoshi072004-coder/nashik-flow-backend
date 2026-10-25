from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class PricingRule(TimeStampedUUIDModel, SoftDeleteModel):
    class TripType(models.TextChoices):
        WITHIN_CITY = "within_city", "Within City"
        OUTSTATION = "outstation", "Outstation"

    city = models.CharField(max_length=64, default="Nashik", db_index=True)
    vehicle_category = models.ForeignKey("vehicle_categories.VehicleCategory", on_delete=models.CASCADE, related_name="pricing_rules")
    name = models.CharField(max_length=120)
    trip_type = models.CharField(
        max_length=32,
        choices=TripType.choices,
        default=TripType.WITHIN_CITY,
        db_index=True,
    )
    min_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
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
            models.CheckConstraint(condition=Q(surge_multiplier__gte=1), name="pricing_surge_gte_one"),
            models.CheckConstraint(condition=Q(base_fare__gte=0), name="pricing_base_fare_gte_zero"),
        ]


class RouteTollCache(TimeStampedUUIDModel):
    """
    Cached toll gate prices between route clusters (e.g. 5-char Geohash ~4.9km box).
    Strictly complies with Google Maps Platform 30-day caching limit with expires_at.
    Allows manual admin overrides so well-known corridors bypass external API queries entirely.
    """

    class Source(models.TextChoices):
        GOOGLE_ROUTES = "google_routes", "Google Routes API"
        MANUAL_OVERRIDE = "manual_override", "Manual Admin Override"
        MAPPLS = "mappls", "Mappls API"
        FALLBACK = "fallback", "Fallback Default"

    origin_geohash = models.CharField(max_length=12, db_index=True)
    destination_geohash = models.CharField(max_length=12, db_index=True)
    origin_name = models.CharField(max_length=120, blank=True, default="")
    destination_name = models.CharField(max_length=120, blank=True, default="")
    vehicle_category = models.ForeignKey(
        "vehicle_categories.VehicleCategory",
        on_delete=models.SET_NULL,
        related_name="route_tolls",
        null=True,
        blank=True,
    )
    vehicle_category_slug = models.CharField(max_length=64, blank=True, default="", db_index=True)
    toll_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="INR")
    has_tolls = models.BooleanField(default=True)
    toll_details = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.GOOGLE_ROUTES)
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["origin_geohash", "destination_geohash", "vehicle_category_slug", "is_active"]),
            models.Index(fields=["expires_at", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["origin_geohash", "destination_geohash", "vehicle_category_slug"],
                name="uniq_route_toll_corridor_category",
            )
        ]

    def __str__(self):
        cat = self.vehicle_category_slug or "all"
        return f"Toll {self.origin_geohash}->{self.destination_geohash} [{cat}]: ₹{self.toll_amount} ({self.source})"

