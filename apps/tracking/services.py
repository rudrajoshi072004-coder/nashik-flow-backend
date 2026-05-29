from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt

from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.utils import timezone

from apps.bookings.models import Booking
from apps.trip_events.services import broadcast_event, record_trip_event
from .models import DriverLiveLocation


LOCATION_THROTTLE_SECONDS = 2


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    r = 6371.0
    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return Decimal(str(round(r * 2 * atan2(sqrt(a), sqrt(1 - a)), 2)))


def update_driver_location(
    *,
    driver_profile,
    lat: float,
    lng: float,
    heading: float = 0,
    speed_kmph: float = 0,
    accuracy_m: float = 0,
    booking_id: str | None = None,
):
    throttle_key = f"driver_location_throttle:{driver_profile.id}"
    # First GPS row is required for ring matching; never throttle go-online / first fix.
    has_live_row = DriverLiveLocation.objects.filter(driver=driver_profile).exists()
    if has_live_row and cache.get(throttle_key):
        return None

    booking = None
    if booking_id:
        booking = Booking.objects.filter(id=booking_id).first()

    location_obj, _ = DriverLiveLocation.objects.update_or_create(
        driver=driver_profile,
        defaults={
            "booking": booking,
            "location": Point(float(lng), float(lat), srid=4326),
            "heading": heading,
            "speed_kmph": speed_kmph,
            "accuracy_m": accuracy_m,
            "source_timestamp": timezone.now(),
        },
    )
    cache.set(throttle_key, "1", timeout=LOCATION_THROTTLE_SECONDS)

    payload = {
        "driver_id": str(driver_profile.id),
        "lat": lat,
        "lng": lng,
        "heading": float(heading),
        "speed_kmph": float(speed_kmph),
        "booking_id": str(booking.id) if booking else None,
        "timestamp": timezone.now().isoformat(),
    }

    broadcast_event(f"driver_{driver_profile.id}", "driver_location_updated", payload)
    broadcast_event(f"admin_city_{driver_profile.user.city.lower()}", "driver_location_updated", payload)

    if booking:
        eta_min = None
        if booking.drop_location:
            drop_lat = booking.drop_location.y
            drop_lng = booking.drop_location.x
            distance_km = _distance_km(lat, lng, drop_lat, drop_lng)
            eta_min = int(max(1, (float(distance_km) / max(float(speed_kmph), 20)) * 60))
        booking_payload = {**payload, "eta_min": eta_min}
        broadcast_event(f"booking_{booking.id}", "live_trip_tracking", booking_payload)
        broadcast_event(f"user_{booking.customer_id}", "live_trip_tracking", booking_payload)
        if eta_min is not None:
            record_trip_event(
                booking=booking,
                actor_driver=driver_profile,
                event_type="eta_updated",
                payload={"eta_min": eta_min, "driver_id": str(driver_profile.id)},
            )
            broadcast_event(
                f"booking_{booking.id}",
                "eta_updated",
                {"booking_id": str(booking.id), "eta_min": eta_min, "driver_id": str(driver_profile.id)},
            )

    return location_obj
