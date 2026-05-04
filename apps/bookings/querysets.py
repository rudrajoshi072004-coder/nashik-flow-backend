"""
Driver-facing booking visibility — must match ``GET /drivers/me/bookings/`` so
``GET /bookings/<uuid>/`` (retrieve) never 404s when the list endpoint includes that row.
"""

from django.db import connection
from django.db.models import Q, Subquery

from apps.trip_events.models import TripEvent

from .models import Booking

RIDE_REQUEST_SENT = "ride_request_sent"
RIDE_OFFER_ROUND = "ride_offer_round"


def bookings_queryset_for_driver_user(user):
    """
    Bookings a driver may list and retrieve via ``BookingViewSet``.
    Uses the same rules as ``DriverViewSet.bookings`` (offered + assigned).

    Includes provisional offers matched either by per-driver ``ride_request_sent`` events
    or by ``ride_offer_round`` payloads (``driver_ids``), so retrieve stays consistent
    with WebSocket dispatch if one event type lags or is missing on a replica.
    """
    from apps.drivers.models import DriverProfile

    profile, _ = DriverProfile.objects.get_or_create(user=user)
    offered_booking_ids = TripEvent.objects.filter(
        actor_driver=profile,
        event_type=RIDE_REQUEST_SENT,
        booking__state=Booking.BookingState.SEARCHING_DRIVER,
        booking__driver__isnull=True,
    ).values_list("booking_id", flat=True)

    visibility = Q(driver=profile) | Q(id__in=offered_booking_ids)

    # Same booking, searching, no assignee: driver listed in ring offer payload.
    pid = str(profile.id)
    if connection.vendor == "postgresql":
        round_booking_ids = (
            TripEvent.objects.filter(
                event_type=RIDE_OFFER_ROUND,
                booking__state=Booking.BookingState.SEARCHING_DRIVER,
                booking__driver__isnull=True,
                booking__is_deleted=False,
            )
            .extra(
                where=[
                    "%s = ANY (SELECT jsonb_array_elements_text(COALESCE((payload::jsonb)->'driver_ids','[]'::jsonb)))"
                ],
                params=[pid],
            )
            .values("booking_id")
        )
        visibility |= Q(id__in=Subquery(round_booking_ids))
    else:
        # SQLite / dev: coarse filter (UUID substring is specific enough for local tests).
        round_booking_ids = (
            TripEvent.objects.filter(
                event_type=RIDE_OFFER_ROUND,
                booking__state=Booking.BookingState.SEARCHING_DRIVER,
                booking__driver__isnull=True,
                booking__is_deleted=False,
                payload__icontains=pid,
            ).values("booking_id")
        )
        visibility |= Q(id__in=Subquery(round_booking_ids))

    return (
        Booking.objects.filter(is_deleted=False)
        .select_related("customer", "driver", "vehicle_category", "service_zone")
        .filter(visibility)
        .distinct()
        .order_by("-created_at")
    )
