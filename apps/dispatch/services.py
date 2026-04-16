from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction

from apps.bookings.models import Booking
from apps.drivers.models import DriverProfile
from apps.tracking.models import DriverLiveLocation
from apps.trip_events.services import broadcast_event, record_trip_event


DISPATCH_RADIUS_KM = 8


def find_nearest_available_drivers(*, booking: Booking, radius_km: float = DISPATCH_RADIUS_KM, exclude_driver_ids=None):
    exclude_driver_ids = exclude_driver_ids or []
    return (
        DriverLiveLocation.objects.select_related("driver", "driver__user")
        .filter(
            driver__is_online=True,
            driver__kyc_status=DriverProfile.KYCStatus.APPROVED,
            driver__is_deleted=False,
            driver__vehicles__category=booking.vehicle_category,
            driver__vehicles__status="active",
        )
        .exclude(driver_id__in=exclude_driver_ids)
        .annotate(distance_m=Distance("location", booking.pickup_location))
        .filter(location__distance_lte=(booking.pickup_location, D(km=radius_km)))
        .order_by("distance_m")
        .distinct()
    )


@transaction.atomic
def assign_driver_to_booking(*, booking: Booking, timeout_seconds: int = 30):
    previous_driver_ids = list(
        booking.trip_events.filter(event_type="driver_assigned").values_list("actor_driver_id", flat=True)
    )
    candidates = find_nearest_available_drivers(booking=booking, exclude_driver_ids=previous_driver_ids)
    candidate = candidates.first()
    if not candidate:
        record_trip_event(
            booking=booking,
            event_type="driver_found",
            payload={"status": "none_available"},
        )
        broadcast_event(
            f"booking_{booking.id}",
            "driver_found",
            {"booking_id": str(booking.id), "status": "none_available"},
        )
        return None

    driver_profile = candidate.driver
    booking.driver = driver_profile
    booking.state = Booking.BookingState.DRIVER_ASSIGNED
    booking.save(update_fields=["driver", "state", "updated_at"])

    record_trip_event(
        booking=booking,
        event_type="driver_found",
        actor_driver=driver_profile,
        payload={"driver_id": str(driver_profile.id), "distance_m": float(candidate.distance_m.m)},
    )
    record_trip_event(
        booking=booking,
        event_type="driver_assigned",
        actor_driver=driver_profile,
        from_state=Booking.BookingState.SEARCHING_DRIVER,
        to_state=Booking.BookingState.DRIVER_ASSIGNED,
        payload={"timeout_seconds": timeout_seconds},
    )

    assignment_payload = {
        "booking_id": str(booking.id),
        "driver_id": str(driver_profile.id),
        "driver_phone": driver_profile.user.phone,
    }
    broadcast_event(f"booking_{booking.id}", "driver_assigned", assignment_payload)
    broadcast_event(f"user_{booking.customer_id}", "driver_assigned", assignment_payload)
    broadcast_event(f"driver_{driver_profile.id}", "driver_assigned", assignment_payload)
    broadcast_event(
        f"admin_city_{booking.customer.city.lower()}",
        "driver_assigned",
        assignment_payload,
    )

    from .tasks import handle_assignment_timeout

    handle_assignment_timeout.apply_async(args=[str(booking.id), str(driver_profile.id)], countdown=timeout_seconds)
    return driver_profile
