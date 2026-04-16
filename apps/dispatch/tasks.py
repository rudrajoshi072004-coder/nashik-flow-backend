from celery import shared_task

from apps.bookings.models import Booking
from apps.trip_events.services import broadcast_event, record_trip_event

from .services import assign_driver_to_booking


@shared_task
def dispatch_booking(booking_id: str):
    booking = Booking.objects.filter(id=booking_id).first()
    if not booking:
        return
    if booking.state not in {Booking.BookingState.PENDING_QUOTE, Booking.BookingState.SEARCHING_DRIVER}:
        return
    booking.state = Booking.BookingState.SEARCHING_DRIVER
    booking.save(update_fields=["state", "updated_at"])
    record_trip_event(booking=booking, event_type="booking_created", to_state=booking.state)
    broadcast_event(f"booking_{booking.id}", "booking_created", {"booking_id": str(booking.id)})
    assign_driver_to_booking(booking=booking)


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
    assign_driver_to_booking(booking=booking)
