import logging

from celery import shared_task

from apps.bookings.models import Booking
from apps.trip_events.services import broadcast_event, record_trip_event

from .matching import iter_rings
from .services import (
    is_latest_offer_round,
    mark_no_driver_available,
    run_dispatch_for_ring,
)

logger = logging.getLogger(__name__)


@shared_task
def dispatch_booking(booking_id: str):
    booking = (
        Booking.objects.select_related("vehicle_category", "customer")
        .filter(id=booking_id)
        .first()
    )
    if not booking:
        return
    if booking.state not in {Booking.BookingState.PENDING_QUOTE, Booking.BookingState.SEARCHING_DRIVER}:
        return
    if not booking.pickup_location or not booking.drop_location:
        logger.error(
            "dispatch_booking: booking missing geometry; cannot match drivers",
            extra={"booking_id": str(booking_id)},
        )
        return

    booking.state = Booking.BookingState.SEARCHING_DRIVER
    booking.save(update_fields=["state", "updated_at"])
    record_trip_event(booking=booking, event_type="booking_created", to_state=booking.state)
    broadcast_event(f"booking_{booking.id}", "booking_created", {"booking_id": str(booking.id)})

    from .services import assign_driver_to_booking

    assign_driver_to_booking(booking=booking)


@shared_task
def continue_dispatch_rings(booking_id: str, ring_index: int, cumulative_notified: list | None = None):
    """
    Recursively process dispatch rings. `cumulative_notified` = driver ids already offered this search.
    """
    cumulative_notified = list(cumulative_notified or [])
    booking = Booking.objects.select_related("vehicle_category", "customer").filter(id=booking_id).first()
    if not booking:
        return
    if booking.state != Booking.BookingState.SEARCHING_DRIVER or booking.driver_id:
        return

    rings = iter_rings()
    if ring_index >= len(rings):
        mark_no_driver_available(booking=booking)
        return

    ring = rings[ring_index]
    round_id, offered = run_dispatch_for_ring(
        booking=booking, ring=ring, previously_notified=cumulative_notified
    )
    if offered:
        return

    # No drivers in this ring — advance immediately (in-process chain; avoids lost tasks without a worker).
    next_index = ring_index + 1
    continue_dispatch_rings.run(str(booking.id), next_index, cumulative_notified)


@shared_task
def wait_after_offer_round(booking_id: str, round_id: str, completed_ring_index: int, cumulative_notified: list | None = None):
    """
    Fires after offer wait. If no driver accepted, continue with next ring.
    `completed_ring_index` is the ring that just completed its offer window.
    """
    cumulative_notified = list(cumulative_notified or [])
    booking = Booking.objects.select_related("vehicle_category", "customer").filter(id=booking_id).first()
    if not booking:
        return
    if booking.state != Booking.BookingState.SEARCHING_DRIVER or booking.driver_id:
        return
    if not is_latest_offer_round(booking=booking, round_id=round_id):
        return

    next_index = completed_ring_index + 1
    continue_dispatch_rings.delay(str(booking.id), next_index, cumulative_notified)


@shared_task
def handle_assignment_timeout(booking_id: str, driver_id: str):
    booking = Booking.objects.filter(id=booking_id).select_related("driver").first()
    if not booking:
        return
    if booking.state != Booking.BookingState.DRIVER_ASSIGNED:
        return
    if not booking.driver or str(booking.driver.id) != driver_id:
        return

    booking.driver = None
    booking.state = Booking.BookingState.SEARCHING_DRIVER
    booking.save(update_fields=["driver", "state", "updated_at"])
    from apps.trip_events.services import broadcast_event, record_trip_event

    record_trip_event(
        booking=booking,
        event_type="driver_assignment_timeout",
        from_state=Booking.BookingState.DRIVER_ASSIGNED,
        to_state=Booking.BookingState.SEARCHING_DRIVER,
        payload={"driver_id": driver_id},
    )
    broadcast_event(
        f"booking_{booking.id}",
        "driver_found",
        {"booking_id": str(booking.id), "status": "reassigning"},
    )
    from .services import assign_driver_to_booking

    assign_driver_to_booking(booking=booking)
