"""
Driver-facing booking visibility — must match ``GET /drivers/me/bookings/`` so
``GET /bookings/<uuid>/`` (retrieve) never 404s when the list endpoint includes that row.
"""

from django.db.models import Q

from apps.trip_events.models import TripEvent

from .models import Booking

RIDE_REQUEST_SENT = "ride_request_sent"


def bookings_queryset_for_driver_user(user):
    """
    Bookings a driver may list and retrieve via ``BookingViewSet``.
    Uses the same rules as ``DriverViewSet.bookings`` (offered + assigned).
    """
    from apps.drivers.models import DriverProfile

    profile, _ = DriverProfile.objects.get_or_create(user=user)
    offered_booking_ids = TripEvent.objects.filter(
        actor_driver=profile,
        event_type=RIDE_REQUEST_SENT,
        booking__state=Booking.BookingState.SEARCHING_DRIVER,
        booking__driver__isnull=True,
    ).values_list("booking_id", flat=True)
    return (
        Booking.objects.filter(is_deleted=False)
        .select_related("customer", "driver", "vehicle_category", "service_zone")
        .filter(Q(driver=profile) | Q(id__in=offered_booking_ids))
        .distinct()
        .order_by("-created_at")
    )
