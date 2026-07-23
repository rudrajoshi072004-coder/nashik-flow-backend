"""Single source of truth for vehicle fare rates and estimates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.pricing.models import PricingRule
from apps.vehicle_categories.models import VehicleCategory

DEFAULT_CITY = "Nashik"
HELPER_CHARGE = Decimal("40.00")


@dataclass(frozen=True)
class ResolvedRates:
    base_fare: Decimal
    per_km_rate: Decimal
    minimum_fare: Decimal
    waiting_per_min: Decimal
    surge_multiplier: Decimal
    source: str
    pricing_rule_id: str | None = None


def resolve_rates_for_category(category: VehicleCategory, city: str = DEFAULT_CITY) -> ResolvedRates:
    """
    Default rates come from VehicleCategory (edited in admin Pricing page).
    Active city pricing rules override base/per-km/minimum for that vehicle.
    """
    city_norm = (city or DEFAULT_CITY).strip()
    rule = (
        PricingRule.objects.filter(
            is_deleted=False,
            active=True,
            vehicle_category=category,
            city__iexact=city_norm,
        )
        .order_by("-updated_at")
        .first()
    )
    if rule:
        return ResolvedRates(
            base_fare=rule.base_fare,
            per_km_rate=rule.per_km_rate,
            minimum_fare=rule.minimum_fare or category.minimum_fare,
            waiting_per_min=rule.per_min_rate or category.waiting_per_min,
            surge_multiplier=rule.surge_multiplier,
            source="pricing_rule",
            pricing_rule_id=str(rule.id),
        )
    return ResolvedRates(
        base_fare=category.base_fare,
        per_km_rate=category.per_km_rate,
        minimum_fare=category.minimum_fare,
        waiting_per_min=category.waiting_per_min,
        surge_multiplier=Decimal("1.00"),
        source="vehicle_category",
    )


def calculate_estimated_fare(
    rates: ResolvedRates,
    distance_km: Decimal,
    *,
    requires_helper: bool = False,
) -> Decimal:
    helper_charge = HELPER_CHARGE if requires_helper else Decimal("0.00")
    subtotal = rates.base_fare + (rates.per_km_rate * distance_km) + helper_charge
    fare = max(rates.minimum_fare, subtotal) * rates.surge_multiplier
    return fare.quantize(Decimal("0.01"))


def fare_breakdown_payload(
    rates: ResolvedRates,
    distance_km: Decimal,
    estimated_fare: Decimal,
    *,
    requires_helper: bool = False,
) -> dict[str, str]:
    helper_charge = HELPER_CHARGE if requires_helper else Decimal("0.00")
    payload = {
        "base_fare": str(rates.base_fare),
        "per_km_rate": str(rates.per_km_rate),
        "minimum_fare": str(rates.minimum_fare),
        "waiting_per_min": str(rates.waiting_per_min),
        "surge_multiplier": str(rates.surge_multiplier),
        "distance_km": str(distance_km),
        "helper_charge": str(helper_charge),
        "estimated_fare": str(estimated_fare),
        "rate_source": rates.source,
    }
    if rates.pricing_rule_id:
        payload["pricing_rule_id"] = rates.pricing_rule_id
    return payload
