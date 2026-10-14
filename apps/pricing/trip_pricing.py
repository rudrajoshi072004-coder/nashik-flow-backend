"""Trip-type aware fare estimation — single backend source of truth."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.bookings.models import Booking
from apps.pricing.constants import CUSTOMER_TRUCK_CATEGORY_NAMES
from apps.pricing.distance import authoritative_distance_km
from apps.pricing.models import PricingRule
from apps.pricing.services import (
    ResolvedRates,
    calculate_estimated_fare,
    fare_breakdown_payload,
    resolve_outstation_rates_for_category,
    resolve_rates_for_category,
)
from apps.service_zones.services import classify_trip_type, resolve_service_zone, service_radius_km_for_city
from apps.vehicle_categories.models import VehicleCategory


@dataclass(frozen=True)
class FareQuote:
    distance_km: Decimal
    distance_source: str
    estimated_duration_min: int
    estimated_fare: Decimal
    trip_type: str
    resolved_trip_type: str
    service_radius_km: Decimal
    service_zone_id: str | None
    rates: ResolvedRates
    breakdown: dict[str, str]
    requires_helper: bool


def is_customer_truck_category(category: VehicleCategory) -> bool:
    return (category.name or "").strip().lower() in CUSTOMER_TRUCK_CATEGORY_NAMES


def _duration_minutes(distance_km: Decimal, osrm_duration: int | None) -> int:
    if osrm_duration is not None and osrm_duration > 0:
        return max(10, osrm_duration)
    return int(max(10, float(distance_km) * 4))


def resolve_outstation_slab(
    category: VehicleCategory,
    city: str,
    distance_km: Decimal,
) -> PricingRule:
    city_norm = (city or "Nashik").strip()
    rules = (
        PricingRule.objects.filter(
            is_deleted=False,
            active=True,
            trip_type=PricingRule.TripType.OUTSTATION,
            vehicle_category=category,
            city__iexact=city_norm,
        )
        .order_by("min_distance_km", "-updated_at")
    )
    matches: list[PricingRule] = []
    for rule in rules:
        min_km = rule.min_distance_km
        max_km = rule.max_distance_km
        if min_km is not None and distance_km < min_km:
            continue
        if max_km is not None and distance_km > max_km:
            continue
        matches.append(rule)

    if not matches:
        raise DRFValidationError(
            {
                "trip_type": (
                    f"No active outstation pricing slab for {category.name} at {distance_km} km in {city_norm}."
                )
            }
        )

    def slab_width(rule: PricingRule) -> Decimal:
        if rule.max_distance_km is None:
            return Decimal("999999")
        return Decimal(str(rule.max_distance_km)) - Decimal(str(rule.min_distance_km or 0))

    rule = min(matches, key=slab_width)
    return rule


def _slab_to_rates(rule: PricingRule) -> ResolvedRates:
    return ResolvedRates(
        base_fare=rule.base_fare,
        per_km_rate=rule.per_km_rate,
        minimum_fare=rule.minimum_fare or Decimal("0"),
        waiting_per_min=rule.per_min_rate or Decimal("0"),
        surge_multiplier=rule.surge_multiplier,
        source="pricing_rule_outstation",
        pricing_rule_id=str(rule.id),
    )


def validate_trip_type_selection(
    *,
    requested_trip_type: str | None,
    resolved_trip_type: str,
    distance_km: Decimal,
    category: VehicleCategory,
    service_radius_km: Decimal,
) -> str:
    """
    Validate customer-selected trip type against backend classification.
    Always returns resolved_trip_type (backend is source of truth).
    """
    customer_truck = is_customer_truck_category(category)

    if not customer_truck:
        return Booking.TripType.WITHIN_CITY

    if not requested_trip_type:
        return resolved_trip_type

    req = requested_trip_type.strip().lower()
    if req not in {Booking.TripType.WITHIN_CITY, Booking.TripType.OUTSTATION}:
        raise DRFValidationError({"trip_type": "Must be within_city or outstation."})

    if req != resolved_trip_type:
        if req == Booking.TripType.WITHIN_CITY and resolved_trip_type == Booking.TripType.OUTSTATION:
            raise DRFValidationError(
                {
                    "trip_type": (
                        f"Trip distance ({distance_km} km) exceeds the {service_radius_km} km service radius. "
                        "Please select Outstation."
                    )
                }
            )
        raise DRFValidationError(
            {
                "trip_type": (
                    f"Trip distance ({distance_km} km) is within the {service_radius_km} km service radius. "
                    "Please select Within City."
                )
            }
        )

    return resolved_trip_type


def compute_fare_quote(
    *,
    category: VehicleCategory,
    pickup_lat: float,
    pickup_lng: float,
    drop_lat: float,
    drop_lng: float,
    city: str = "Nashik",
    requested_trip_type: str | None = None,
    requires_helper: bool = False,
) -> FareQuote:
    if not (-90.0 <= pickup_lat <= 90.0 and -180.0 <= pickup_lng <= 180.0):
        raise DRFValidationError({"pickup_lat": "Invalid pickup coordinates."})
    if not (-90.0 <= drop_lat <= 90.0 and -180.0 <= drop_lng <= 180.0):
        raise DRFValidationError({"drop_lat": "Invalid drop coordinates."})

    distance_km, distance_source, osrm_duration = authoritative_distance_km(
        pickup_lat, pickup_lng, drop_lat, drop_lng
    )
    if distance_km <= 0:
        raise DRFValidationError({"distance_km": "Distance must be greater than zero."})

    city_norm = (city or "Nashik").strip()
    customer_truck = is_customer_truck_category(category)
    needs_trip_classification = customer_truck or bool((requested_trip_type or "").strip())

    zone = resolve_service_zone(city_norm) if needs_trip_classification else None
    if needs_trip_classification:
        if getattr(category, "outstation_threshold_km", None) and category.outstation_threshold_km > 0:
            service_radius = category.outstation_threshold_km
        else:
            service_radius = service_radius_km_for_city(city_norm)
        resolved_trip_type = classify_trip_type(distance_km, city_norm, category=category)
    else:
        service_radius = Decimal("0")
        resolved_trip_type = Booking.TripType.WITHIN_CITY

    trip_type = validate_trip_type_selection(
        requested_trip_type=requested_trip_type,
        resolved_trip_type=resolved_trip_type,
        distance_km=distance_km,
        category=category,
        service_radius_km=service_radius,
    )

    slab_rule = None
    if trip_type == Booking.TripType.OUTSTATION:
        rates = resolve_outstation_rates_for_category(category)
        if rates is None:
            slab_rule = resolve_outstation_slab(category, city_norm, distance_km)
            rates = _slab_to_rates(slab_rule)
    else:
        rates = resolve_rates_for_category(category, city=city_norm, trip_type=Booking.TripType.WITHIN_CITY)

    estimated_fare = calculate_estimated_fare(rates, distance_km, requires_helper=requires_helper)
    breakdown = fare_breakdown_payload(
        rates,
        distance_km,
        estimated_fare,
        requires_helper=requires_helper,
    )
    breakdown["trip_type"] = trip_type
    breakdown["resolved_trip_type"] = resolved_trip_type
    breakdown["distance_source"] = distance_source
    if needs_trip_classification:
        breakdown["service_radius_km"] = str(service_radius)
    if trip_type == Booking.TripType.OUTSTATION:
        breakdown["pricing_mode"] = "outstation"
        if slab_rule is not None:
            breakdown["pricing_mode"] = "outstation_slab"
            breakdown["outstation_slab_min_km"] = str(slab_rule.min_distance_km)
            breakdown["outstation_slab_max_km"] = (
                str(slab_rule.max_distance_km) if slab_rule.max_distance_km is not None else "500+"
            )
    else:
        breakdown["pricing_mode"] = "within_city"

    return FareQuote(
        distance_km=distance_km,
        distance_source=distance_source,
        estimated_duration_min=_duration_minutes(distance_km, osrm_duration),
        estimated_fare=estimated_fare,
        trip_type=trip_type,
        resolved_trip_type=resolved_trip_type,
        service_radius_km=service_radius,
        service_zone_id=str(zone.id) if zone else None,
        rates=rates,
        breakdown=breakdown,
        requires_helper=requires_helper,
    )
