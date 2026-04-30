"""
Distance-based driver selection for ride matching (concentric ring expansion).

Rings (km from pickup), outer radius inclusive, inner exclusive (except first ring):
  Round 1 → 0–2
  Round 2 → 2–5
  Round 3 → 5–10
  Round 4 → 10–20
Maximum search radius: 20 km.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db.models import Q, QuerySet

from apps.bookings.models import Booking
from apps.drivers.models import DriverProfile
from apps.tracking.models import DriverLiveLocation
from apps.vehicles.models import Vehicle

# (inner_km, outer_km)
RADIUS_RINGS_KM: tuple[tuple[float, float], ...] = (
    (0.0, 2.0),
    (2.0, 5.0),
    (5.0, 10.0),
    (10.0, 20.0),
)

MAX_OFFER_BATCH = 5

# Driver is "busy" if they have an in-progress booking
_DRIVER_OCCUPIED_STATES: frozenset[str] = frozenset(
    {
        Booking.BookingState.DRIVER_ASSIGNED,
        Booking.BookingState.DRIVER_ACCEPTED,
        Booking.BookingState.DRIVER_ARRIVING,
        Booking.BookingState.DRIVER_ARRIVED,
        Booking.BookingState.PICKUP_OTP_PENDING,
        Booking.BookingState.TRIP_STARTED,
        Booking.BookingState.IN_TRANSIT,
        Booking.BookingState.NEARING_DROP,
        Booking.BookingState.PAYMENT_PENDING,
    }
)


@dataclass(frozen=True)
class RingDef:
    index: int
    inner_km: float
    outer_km: float


def iter_rings() -> list[RingDef]:
    return [RingDef(i, a, b) for i, (a, b) in enumerate(RADIUS_RINGS_KM)]


def _not_on_active_trip() -> Q:
    from apps.bookings.models import Booking as B

    busy_driver_ids = B.objects.filter(is_deleted=False, state__in=_DRIVER_OCCUPIED_STATES).values("driver_id")
    return ~Q(driver_id__in=busy_driver_ids)


def _base_live_qs() -> QuerySet[DriverLiveLocation]:
    return (
        DriverLiveLocation.objects.select_related("driver", "driver__user")
        .filter(
            driver__is_online=True,
            driver__kyc_status=DriverProfile.KYCStatus.APPROVED,
            driver__is_deleted=False,
        )
        .filter(_not_on_active_trip())
    )


def find_drivers_in_ring(
    *,
    booking: Booking,
    ring: RingDef,
    exclude_driver_ids: list | None = None,
) -> list[tuple[DriverLiveLocation, Any]]:
    """
    Return up to MAX_OFFER_BATCH nearest drivers within the ring, ordered by distance.
    Yields (DriverLiveLocation, distance measure).
    """
    exclude_driver_ids = [str(x) for x in (exclude_driver_ids or [])]
    inner, outer = ring.inner_km, ring.outer_km
    pt = booking.pickup_location
    assert pt is not None

    qs = (
        _base_live_qs()
        .filter(
            driver__vehicles__category=booking.vehicle_category,
            driver__vehicles__status=Vehicle.Status.ACTIVE,
        )
        .exclude(driver_id__in=exclude_driver_ids)
        .annotate(distance_m=Distance("location", pt))
    )
    if inner <= 0:
        qs = qs.filter(location__distance_lte=(pt, D(km=outer)))
    else:
        qs = qs.filter(
            location__distance_gt=(pt, D(km=inner)),
            location__distance_lte=(pt, D(km=outer)),
        )
    rows = list(qs.order_by("distance_m").distinct()[:MAX_OFFER_BATCH])
    return [(row, row.distance_m) for row in rows]
