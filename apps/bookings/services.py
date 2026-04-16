from dataclasses import dataclass
from django.db import transaction
from apps.trip_events.models import TripEvent
from apps.trip_events.services import broadcast_event
from .models import Booking


@dataclass(frozen=True)
class TransitionResult:
    booking_id: str
    new_state: str
    seq: int


VALID_TRANSITIONS = {
    Booking.BookingState.DRAFT: {Booking.BookingState.PENDING_QUOTE, Booking.BookingState.CANCELLED_BY_CUSTOMER},
    Booking.BookingState.PENDING_QUOTE: {Booking.BookingState.SEARCHING_DRIVER, Booking.BookingState.CANCELLED_BY_CUSTOMER},
    Booking.BookingState.SEARCHING_DRIVER: {Booking.BookingState.DRIVER_ASSIGNED, Booking.BookingState.CANCELLED_BY_CUSTOMER, Booking.BookingState.FAILED},
    Booking.BookingState.DRIVER_ASSIGNED: {Booking.BookingState.DRIVER_ACCEPTED, Booking.BookingState.SEARCHING_DRIVER},
    Booking.BookingState.DRIVER_ACCEPTED: {Booking.BookingState.DRIVER_ARRIVING, Booking.BookingState.CANCELLED_BY_DRIVER},
    Booking.BookingState.DRIVER_ARRIVING: {Booking.BookingState.DRIVER_ARRIVED, Booking.BookingState.CANCELLED_BY_DRIVER},
    Booking.BookingState.DRIVER_ARRIVED: {Booking.BookingState.PICKUP_OTP_PENDING},
    Booking.BookingState.PICKUP_OTP_PENDING: {Booking.BookingState.TRIP_STARTED},
    Booking.BookingState.TRIP_STARTED: {Booking.BookingState.IN_TRANSIT},
    Booking.BookingState.IN_TRANSIT: {Booking.BookingState.NEARING_DROP},
    Booking.BookingState.NEARING_DROP: {Booking.BookingState.COMPLETED, Booking.BookingState.PAYMENT_PENDING},
    Booking.BookingState.PAYMENT_PENDING: {Booking.BookingState.COMPLETED, Booking.BookingState.REFUNDED},
}


def transition_booking_state(
    *,
    booking: Booking,
    to_state: str,
    actor=None,
    idempotency_key: str = "",
    payload: dict | None = None,
) -> TransitionResult:
    payload = payload or {}
    from_state = booking.state
    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise ValueError(f"Invalid transition: {from_state} -> {to_state}")

    with transaction.atomic():
        current_seq = (
            TripEvent.objects.filter(booking=booking).order_by("-sequence").values_list("sequence", flat=True).first()
            or 0
        )
        next_seq = current_seq + 1
        booking.state = to_state
        booking.save(update_fields=["state", "updated_at"])

        event = TripEvent.objects.create(
            booking=booking,
            actor_user=actor,
            event_type="booking_state_changed",
            from_state=from_state,
            to_state=to_state,
            sequence=next_seq,
            payload=payload,
        )
    event_payload = {"booking_id": str(booking.id), "state": booking.state, "sequence": event.sequence}
    broadcast_event(f"booking_{booking.id}", "booking_status_update", event_payload)
    broadcast_event(f"user_{booking.customer_id}", "booking_status_update", event_payload)
    if booking.driver_id:
        broadcast_event(f"driver_{booking.driver_id}", "booking_status_update", event_payload)
    lifecycle_event = _map_state_event(booking.state)
    if lifecycle_event:
        broadcast_event(f"booking_{booking.id}", lifecycle_event, event_payload)
        broadcast_event(f"user_{booking.customer_id}", lifecycle_event, event_payload)
        if booking.driver_id:
            broadcast_event(f"driver_{booking.driver_id}", lifecycle_event, event_payload)

    return TransitionResult(str(booking.id), booking.state, event.sequence)


def _map_state_event(state: str) -> str | None:
    mapper = {
        Booking.BookingState.DRIVER_ARRIVED: "driver_arrived",
        Booking.BookingState.TRIP_STARTED: "trip_started",
        Booking.BookingState.COMPLETED: "trip_completed",
        Booking.BookingState.CANCELLED_BY_CUSTOMER: "booking_cancelled",
        Booking.BookingState.CANCELLED_BY_DRIVER: "booking_cancelled",
        Booking.BookingState.CANCELLED_BY_ADMIN: "booking_cancelled",
    }
    return mapper.get(state)
