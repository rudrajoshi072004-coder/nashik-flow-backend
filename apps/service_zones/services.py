"""Service zone resolution for trip classification."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.service_zones.models import ServiceZone

if TYPE_CHECKING:
    from apps.vehicle_categories.models import VehicleCategory


def resolve_service_zone(city: str) -> ServiceZone | None:
    city_norm = (city or "Nashik").strip()
    return (
        ServiceZone.objects.filter(is_deleted=False, active=True, city_name__iexact=city_norm)
        .order_by("-updated_at")
        .first()
    )


def service_radius_km_for_city(city: str) -> Decimal:
    """Return configured service radius; fallback to 50 if unconfigured."""
    city_norm = (city or "Nashik").strip()
    zone = resolve_service_zone(city_norm)
    if zone is None:
        return Decimal("50")
    radius = zone.service_radius_km
    if radius is None or radius <= 0:
        return Decimal("50")
    return Decimal(str(radius))


def classify_trip_type(
    distance_km: Decimal,
    city: str,
    category: VehicleCategory | None = None,
) -> str:
    """Return Booking.TripType value based on distance vs configured outstation threshold."""
    from apps.bookings.models import Booking

    if category and getattr(category, "outstation_threshold_km", None) and category.outstation_threshold_km > 0:
        radius = category.outstation_threshold_km
    else:
        radius = service_radius_km_for_city(city)

    if distance_km <= radius:
        return Booking.TripType.WITHIN_CITY
    return Booking.TripType.OUTSTATION
