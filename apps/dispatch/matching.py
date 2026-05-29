"""
Distance-based driver selection for ride matching (concentric ring expansion).

Rings (km from pickup), outer radius inclusive, inner exclusive (except first ring):
  Round 1 → 0–2
  Round 2 → 2–5
  Round 3 → 5–10
  Round 4 → 10–20
Maximum ring radius: 100 km (plus any-online fallback).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils import timezone
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
    # Wide ring for QA / emulator GPS drift (phones often report coords far from Nashik pickup).
    (20.0, 100.0),
)

# Last resort when ring expansion finds nobody: any online driver with a live location row.
FALLBACK_ANY_ONLINE_MAX = 5

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

# If an active-trip booking is stale for too long, avoid blocking new dispatch forever.
# This protects drivers from being stuck "busy" due abandoned test/failed lifecycle updates.
OCCUPIED_BOOKING_STALE_AFTER = timedelta(hours=2)


@dataclass(frozen=True)
class RingDef:
    index: int
    inner_km: float
    outer_km: float


def iter_rings() -> list[RingDef]:
    return [RingDef(i, a, b) for i, (a, b) in enumerate(RADIUS_RINGS_KM)]


def _not_on_active_trip() -> Q:
    from apps.bookings.models import Booking as B

    recent_cutoff = timezone.now() - OCCUPIED_BOOKING_STALE_AFTER
    busy_driver_ids = (
        B.objects.filter(
            is_deleted=False,
            state__in=_DRIVER_OCCUPIED_STATES,
            updated_at__gte=recent_cutoff,
        ).values("driver_id")
    )
    return ~Q(driver_id__in=busy_driver_ids)


def _base_live_qs(*, strict_kyc: bool = True) -> QuerySet[DriverLiveLocation]:
    kyc_filter = {"driver__kyc_status": DriverProfile.KYCStatus.APPROVED} if strict_kyc else {}
    return (
        DriverLiveLocation.objects.select_related("driver", "driver__user")
        .filter(
            driver__is_online=True,
            driver__is_deleted=False,
            **kyc_filter,
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

    def build_qs(*, strict_kyc: bool, strict_category: bool, require_active_vehicle: bool = True) -> QuerySet[DriverLiveLocation]:
        q = _base_live_qs(strict_kyc=strict_kyc).exclude(driver_id__in=exclude_driver_ids).annotate(
            distance_m=Distance("location", pt)
        )
        
        if strict_category:
            q = q.filter(driver__vehicles__category=booking.vehicle_category)
            
        if require_active_vehicle:
            q = q.filter(driver__vehicles__status=Vehicle.Status.ACTIVE)
            
        if inner <= 0:
            q = q.filter(location__distance_lte=(pt, D(km=outer)))
        else:
            q = q.filter(
                location__distance_gt=(pt, D(km=inner)),
                location__distance_lte=(pt, D(km=outer)),
            )
        return q.order_by("distance_m").distinct()

    # Fast Porter-style dispatch:
    # 1. First attempt strict match (KYC + exact vehicle + active)
    qs = build_qs(strict_kyc=True, strict_category=True, require_active_vehicle=True)
    rows = list(qs[:MAX_OFFER_BATCH])
    
    # 2. Immediate fallback if no strict matches are found (to ensure smooth flow, especially for test drivers)
    if not rows:
        qs = build_qs(strict_kyc=False, strict_category=False, require_active_vehicle=False)
        rows = list(qs[:MAX_OFFER_BATCH])
        
    return [(row, row.distance_m) for row in rows]


def _busy_driver_ids() -> list:
    from apps.bookings.models import Booking as B

    recent_cutoff = timezone.now() - OCCUPIED_BOOKING_STALE_AFTER
    return list(
        B.objects.filter(
            is_deleted=False,
            state__in=_DRIVER_OCCUPIED_STATES,
            updated_at__gte=recent_cutoff,
        ).values_list("driver_id", flat=True)
    )


def find_online_profiles_without_live_location(
    *,
    exclude_driver_ids: list | None = None,
    limit: int = FALLBACK_ANY_ONLINE_MAX,
) -> list[DriverProfile]:
    """Drivers marked online on the server but with no GPS row yet (common on mobile app reopen)."""
    exclude_driver_ids = [str(x) for x in (exclude_driver_ids or [])]
    located_ids = DriverLiveLocation.objects.values_list("driver_id", flat=True)
    return list(
        DriverProfile.objects.filter(is_online=True, is_deleted=False)
        .exclude(id__in=exclude_driver_ids)
        .exclude(id__in=_busy_driver_ids())
        .exclude(id__in=located_ids)[:limit]
    )


def find_any_online_drivers(
    *,
    booking: Booking,
    exclude_driver_ids: list | None = None,
) -> list[tuple[DriverProfile, Any]]:
    """
    Nearest online drivers with live GPS, then online drivers without a GPS row yet.
    Used after normal rings are exhausted.
    """
    exclude_driver_ids = [str(x) for x in (exclude_driver_ids or [])]
    pt = booking.pickup_location
    if pt is None:
        return []

    results: list[tuple[DriverProfile, Any]] = []
    qs = (
        _base_live_qs(strict_kyc=False)
        .exclude(driver_id__in=exclude_driver_ids)
        .annotate(distance_m=Distance("location", pt))
        .order_by("distance_m")
        .distinct()
    )
    for row in qs[:FALLBACK_ANY_ONLINE_MAX]:
        results.append((row.driver, row.distance_m))

    if len(results) < FALLBACK_ANY_ONLINE_MAX:
        remaining = FALLBACK_ANY_ONLINE_MAX - len(results)
        for profile in find_online_profiles_without_live_location(
            exclude_driver_ids=exclude_driver_ids + [str(d.id) for d, _ in results],
            limit=remaining,
        ):
            results.append((profile, None))

    return results
