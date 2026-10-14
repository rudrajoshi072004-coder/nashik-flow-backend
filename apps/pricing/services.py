"""Single source of truth for vehicle fare rates and estimates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.vehicle_categories.models import VehicleCategory

DEFAULT_CITY = "Nashik"
HELPER_CHARGE = Decimal("40.00")
ZERO = Decimal("0")
OUTSTATION_STEP_START_KM = Decimal("50")


@dataclass(frozen=True)
class ResolvedRates:
    base_fare: Decimal
    per_km_rate: Decimal
    minimum_fare: Decimal
    waiting_per_min: Decimal
    surge_multiplier: Decimal
    source: str
    base_fare_km: Decimal = ZERO
    step_start_km: Decimal = OUTSTATION_STEP_START_KM
    step_km: Decimal = ZERO
    step_discount: Decimal = ZERO
    pricing_rule_id: str | None = None


def chargeable_distance_km(distance_km: Decimal, included_km: Decimal | None) -> Decimal:
    """Kilometres billed at the per-km rate after the base-fare allowance."""
    extra = distance_km - (included_km or ZERO)
    return extra if extra > ZERO else ZERO


def _step_enabled(rates: ResolvedRates) -> bool:
    return (rates.step_km or ZERO) > ZERO and (rates.step_discount or ZERO) > ZERO


def per_km_rate_at(position_km: Decimal, rates: ResolvedRates) -> Decimal:
    """Per-km rate that applies at this point along the trip."""
    rate = rates.per_km_rate
    if not _step_enabled(rates):
        return rate
    start = rates.step_start_km or OUTSTATION_STEP_START_KM
    if position_km < start:
        return rate
    extra = position_km - start
    steps = (extra // rates.step_km) + 1
    reduced = rate - (rates.step_discount * steps)
    return reduced if reduced > ZERO else ZERO


def _next_rate_boundary(position_km: Decimal, end_km: Decimal, rates: ResolvedRates) -> Decimal:
    if not _step_enabled(rates):
        return end_km
    start = rates.step_start_km or OUTSTATION_STEP_START_KM
    if position_km < start:
        return min(start, end_km)
    extra = position_km - start
    steps = (extra // rates.step_km) + 1
    boundary = start + (steps * rates.step_km)
    if boundary <= position_km:
        boundary = position_km + rates.step_km
    return min(boundary, end_km)


def distance_charge(rates: ResolvedRates, distance_km: Decimal) -> Decimal:
    """Base fare + telescopic per-km charge for billed kilometres."""
    billed_from = rates.base_fare_km or ZERO
    if distance_km <= billed_from:
        return rates.base_fare
    total = rates.base_fare
    position = billed_from
    while position < distance_km:
        rate = per_km_rate_at(position, rates)
        nxt = _next_rate_boundary(position, distance_km, rates)
        if nxt <= position:
            nxt = min(distance_km, position + (rates.step_km or Decimal("0.01")))
        if nxt <= position:
            break
        total += (nxt - position) * rate
        position = nxt
    return total


def resolve_rates_for_category(
    category: VehicleCategory,
    city: str = DEFAULT_CITY,
    *,
    trip_type: str = "within_city",
) -> ResolvedRates:
    """Within-city rates from VehicleCategory only (admin Pricing page)."""
    _ = city, trip_type
    return ResolvedRates(
        base_fare=category.base_fare,
        per_km_rate=category.per_km_rate,
        minimum_fare=category.minimum_fare,
        waiting_per_min=category.waiting_per_min,
        surge_multiplier=Decimal("1.00"),
        source="vehicle_category",
        base_fare_km=category.base_fare_km or ZERO,
    )


def resolve_outstation_rates_for_category(category: VehicleCategory) -> ResolvedRates | None:
    """Direct outstation rates from VehicleCategory, if the admin has set a per-km rate."""
    per_km = category.outstation_per_km_rate or ZERO
    if per_km <= ZERO:
        return None
    return ResolvedRates(
        base_fare=category.outstation_base_fare or ZERO,
        per_km_rate=per_km,
        minimum_fare=category.outstation_minimum_fare or ZERO,
        waiting_per_min=ZERO,
        surge_multiplier=Decimal("1.00"),
        source="vehicle_category_outstation",
        base_fare_km=category.outstation_base_fare_km or ZERO,
        step_start_km=OUTSTATION_STEP_START_KM,
        step_km=getattr(category, "outstation_step_km", None) or ZERO,
        step_discount=getattr(category, "outstation_step_discount", None) or ZERO,
    )


def calculate_estimated_fare(
    rates: ResolvedRates,
    distance_km: Decimal,
    *,
    requires_helper: bool = False,
) -> Decimal:
    helper_charge = HELPER_CHARGE if requires_helper else ZERO
    subtotal = distance_charge(rates, distance_km) + helper_charge
    fare = max(rates.minimum_fare, subtotal) * rates.surge_multiplier
    return fare.quantize(Decimal("0.01"))


def fare_breakdown_payload(
    rates: ResolvedRates,
    distance_km: Decimal,
    estimated_fare: Decimal,
    *,
    requires_helper: bool = False,
) -> dict[str, str]:
    helper_charge = HELPER_CHARGE if requires_helper else ZERO
    billed_km = chargeable_distance_km(distance_km, rates.base_fare_km)
    payload = {
        "base_fare": str(rates.base_fare),
        "base_fare_km": str(rates.base_fare_km or ZERO),
        "per_km_rate": str(rates.per_km_rate),
        "minimum_fare": str(rates.minimum_fare),
        "waiting_per_min": str(rates.waiting_per_min),
        "surge_multiplier": str(rates.surge_multiplier),
        "distance_km": str(distance_km),
        "chargeable_km": str(billed_km),
        "helper_charge": str(helper_charge),
        "estimated_fare": str(estimated_fare),
        "rate_source": rates.source,
        "outstation_step_start_km": str(rates.step_start_km or OUTSTATION_STEP_START_KM),
        "outstation_step_km": str(rates.step_km or ZERO),
        "outstation_step_discount": str(rates.step_discount or ZERO),
    }
    if rates.pricing_rule_id:
        payload["pricing_rule_id"] = rates.pricing_rule_id
    return payload
