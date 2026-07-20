from dataclasses import dataclass

from django.db import transaction

from apps.trip_events.models import TripEvent
from apps.trip_events.services import broadcast_event, record_trip_event

from .models import Booking


@dataclass(frozen=True)
class TransitionResult:
    booking_id: str
    new_state: str
    seq: int


VALID_TRANSITIONS = {
    Booking.BookingState.DRAFT: {Booking.BookingState.PENDING_QUOTE, Booking.BookingState.CANCELLED_BY_CUSTOMER},
    Booking.BookingState.PENDING_QUOTE: {Booking.BookingState.SEARCHING_DRIVER, Booking.BookingState.CANCELLED_BY_CUSTOMER},
    Booking.BookingState.SEARCHING_DRIVER: {
        Booking.BookingState.DRIVER_ASSIGNED,
        Booking.BookingState.DRIVER_ACCEPTED,
        Booking.BookingState.CANCELLED_BY_CUSTOMER,
        Booking.BookingState.FAILED,
    },
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


def _driver_is_busy_on_another_trip(*, profile, current_booking: Booking) -> bool:
    busy = {
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
    return (
        Booking.objects.filter(driver=profile, is_deleted=False, state__in=busy)
        .exclude(id=current_booking.id)
        .exists()
    )


def _accept_ride_while_searching(
    *, booking: Booking, actor, payload: dict
) -> TransitionResult:
    from apps.dispatch.services import driver_had_ride_request, on_driver_won_ride
    from apps.drivers.models import DriverProfile

    profile = getattr(actor, "driver_profile", None)
    if profile is None:
        profile = DriverProfile.objects.filter(user=actor, is_deleted=False).first()
    if profile is None:
        raise ValueError("Driver profile required to accept offers.")
    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(id=booking.id)
        if locked.state != Booking.BookingState.SEARCHING_DRIVER:
            raise ValueError("Booking is not accepting offers.")
        if locked.driver_id:
            raise ValueError("Trip already accepted by another driver.")
        if not driver_had_ride_request(booking=locked, driver_profile=profile):
            raise ValueError("This driver is not in the current offer pool.")
        if _driver_is_busy_on_another_trip(profile=profile, current_booking=locked):
            raise ValueError("You already have an active trip.")

        from_state = locked.state
        current_seq = (
            TripEvent.objects.filter(booking=locked).order_by("-sequence").values_list("sequence", flat=True).first()
            or 0
        )
        next_seq = current_seq + 1
        locked.driver = profile
        locked.state = Booking.BookingState.DRIVER_ACCEPTED
        locked.save(update_fields=["driver", "state", "updated_at"])
        event = TripEvent.objects.create(
            booking=locked,
            actor_user=actor,
            actor_driver=profile,
            event_type="booking_state_changed",
            from_state=from_state,
            to_state=locked.state,
            sequence=next_seq,
            payload=payload,
        )

    on_driver_won_ride(booking=locked, winning_driver_id=str(profile.id))
    event_payload = {"booking_id": str(locked.id), "state": locked.state, "sequence": event.sequence}
    broadcast_event(f"booking_{locked.id}", "booking_status_update", event_payload)
    broadcast_event(f"user_{locked.customer_id}", "booking_status_update", event_payload)
    broadcast_event(f"driver_{locked.driver_id}", "booking_status_update", event_payload)

    # Porter-style customer event: driver accepted — includes contact + vehicle for live tracking UI.
    from apps.vehicles.models import Vehicle

    vehicle = profile.vehicles.filter(status=Vehicle.Status.ACTIVE).select_related("category").first()
    trip_accepted_payload = {
        **event_payload,
        "driver_id": str(profile.id),
        "driver_phone": profile.user.phone,
        "driver_name": profile.user.phone,
        "vehicle_number": vehicle.registration_number if vehicle else "",
        "vehicle_type": vehicle.category.name if vehicle and vehicle.category_id else "",
        "rating_avg": str(profile.rating_avg),
        "pickup_address_text": locked.pickup_address_text or "",
        "drop_address_text": locked.drop_address_text or "",
    }
    broadcast_event(f"booking_{locked.id}", "trip_accepted", trip_accepted_payload)
    broadcast_event(f"user_{locked.customer_id}", "trip_accepted", trip_accepted_payload)
    broadcast_event(f"booking_{locked.id}", "trip_status_update", trip_accepted_payload)
    broadcast_event(f"user_{locked.customer_id}", "trip_status_update", trip_accepted_payload)
    lifecycle_event = _map_state_event(locked.state)
    if lifecycle_event:
        broadcast_event(f"booking_{locked.id}", lifecycle_event, event_payload)
        broadcast_event(f"user_{locked.customer_id}", lifecycle_event, event_payload)
        if locked.driver_id:
            broadcast_event(f"driver_{locked.driver_id}", lifecycle_event, event_payload)
    return TransitionResult(str(locked.id), locked.state, event.sequence)


# When the same customer books again, close their prior in-progress trip so the driver can receive the new offer.
_CUSTOMER_REBOOK_RELEASE_STATES = frozenset(
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


def release_customer_previous_active_trips(*, customer, new_booking_id: str) -> int:
    """Complete this customer's other active trips (repeat booking / QA flow)."""
    qs = (
        Booking.objects.filter(
            customer=customer,
            is_deleted=False,
            driver_id__isnull=False,
            state__in=_CUSTOMER_REBOOK_RELEASE_STATES,
        )
        .exclude(id=new_booking_id)
        .select_related("driver", "driver__user")
    )
    count = 0
    for booking in qs:
        from_state = booking.state
        booking.state = Booking.BookingState.COMPLETED
        booking.save(update_fields=["state", "updated_at"])
        record_trip_event(
            booking=booking,
            event_type="booking_state_changed",
            from_state=from_state,
            to_state=booking.state,
            payload={"reason": "customer_new_booking"},
        )
        payload = {
            "booking_id": str(booking.id),
            "state": booking.state,
            "previous_state": from_state,
        }
        broadcast_event(f"booking_{booking.id}", "booking_status_update", payload)
        broadcast_event(f"user_{booking.customer_id}", "booking_status_update", payload)
        if booking.driver_id:
            broadcast_event(f"driver_{booking.driver_id}", "booking_status_update", payload)
            broadcast_event(f"user_{booking.driver.user_id}", "booking_status_update", payload)
            broadcast_event(
                f"driver_{booking.driver_id}",
                "ride_request_cancelled",
                {"booking_id": str(booking.id), "reason": "customer_new_booking"},
            )
        count += 1
    return count


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
    if from_state == Booking.BookingState.SEARCHING_DRIVER and to_state == Booking.BookingState.DRIVER_ACCEPTED and actor:
        from apps.drivers.models import DriverProfile

        can_accept = getattr(actor, "role", None) in {"driver", "fleet_driver"} or DriverProfile.objects.filter(
            user=actor, is_deleted=False
        ).exists()
        if can_accept:
            return _accept_ride_while_searching(booking=booking, actor=actor, payload=payload)
    if (
        from_state == Booking.BookingState.SEARCHING_DRIVER
        and to_state == Booking.BookingState.DRIVER_ASSIGNED
        and not booking.driver_id
    ):
        raise ValueError("Cannot move to driver_assigned without a driver on the booking.")
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
