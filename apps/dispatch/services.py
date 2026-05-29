from __future__ import annotations

import logging
import uuid
from typing import Any

from django.db import transaction

from apps.bookings.models import Booking
from apps.trip_events.models import TripEvent
from apps.trip_events.services import broadcast_event, record_trip_event

from .matching import find_any_online_drivers, find_drivers_in_ring, iter_rings, RingDef

# TripEvent.event_type (no new DB fields)
RIDE_REQUEST_SENT = "ride_request_sent"
RIDE_OFFER_ROUND = "ride_offer_round"

OFFER_WAIT_SECONDS = 25

logger = logging.getLogger(__name__)

# “is_available” is represented as: online + not on another active trip (see matching._not_on_active_trip)


def get_notified_driver_ids(*, booking: Booking) -> list[str]:
    return [
        str(x)
        for x in (
            TripEvent.objects.filter(booking=booking, event_type=RIDE_REQUEST_SENT, actor_driver__isnull=False)
            .values_list("actor_driver_id", flat=True)
            .distinct()
        )
    ]


def driver_had_ride_request(*, booking: Booking, driver_profile) -> bool:
    return TripEvent.objects.filter(
        booking=booking, event_type=RIDE_REQUEST_SENT, actor_driver=driver_profile
    ).exists()


def is_latest_offer_round(*, booking: Booking, round_id: str) -> bool:
    ev = (
        TripEvent.objects.filter(booking=booking, event_type=RIDE_OFFER_ROUND)
        .order_by("-sequence", "-created_at")
        .first()
    )
    if not ev or not ev.payload:
        return False
    return str(ev.payload.get("round_id")) == str(round_id)


def _broadcast_driver_provisional_assign(*, booking: Booking, driver_profile, distance_m: float) -> None:
    """Driver app treats `driver_assigned` like the legacy flow (sets current booking)."""
    pickup = booking.pickup_location
    drop = booking.drop_location
    assignment_payload = {
        "booking_id": str(booking.id),
        "driver_id": str(driver_profile.id),
        "driver_phone": driver_profile.user.phone,
        "distance_m": distance_m,
        "offer": True,
        # Include route snapshot so driver UI can render without waiting on REST fetch races.
        "pickup_address_text": booking.pickup_address_text or "",
        "drop_address_text": booking.drop_address_text or "",
        "pickup_lat": float(pickup.y) if pickup is not None else None,
        "pickup_lng": float(pickup.x) if pickup is not None else None,
        "drop_lat": float(drop.y) if drop is not None else None,
        "drop_lng": float(drop.x) if drop is not None else None,
        "estimated_fare": str(booking.estimated_fare) if booking.estimated_fare is not None else None,
        "customer_phone": getattr(booking.customer, "phone", None),
        "notes": booking.notes or "",
    }
    # Record before WebSocket so `GET /bookings/<id>/` and `/drivers/me/bookings/`
    # (queryset uses TripEvent) are consistent when the client fetches immediately.
    record_trip_event(
        booking=booking,
        event_type=RIDE_REQUEST_SENT,
        actor_driver=driver_profile,
        payload=assignment_payload,
    )
    broadcast_event(f"driver_{driver_profile.id}", "driver_assigned", assignment_payload)


def _record_offer_round(
    *, booking: Booking, ring: RingDef, round_id: str, driver_ids: list[str]
) -> None:
    record_trip_event(
        booking=booking,
        event_type=RIDE_OFFER_ROUND,
        payload={
            "round_id": round_id,
            "ring_index": ring.index,
            "inner_km": ring.inner_km,
            "outer_km": ring.outer_km,
            "driver_ids": driver_ids,
        },
    )


def _offer_drivers(
    *,
    booking: Booking,
    rows: list,
    ring: RingDef | None,
    previously_notified: list[str] | None,
) -> tuple[str | None, int]:
    """Shared path to push provisional offers and schedule the offer wait."""
    previously_notified = list(previously_notified or [])
    if not rows:
        return None, 0
    round_id = str(uuid.uuid4())
    driver_ids: list[str] = []
    for d, dist in rows:
        driver_ids.append(str(d.id))
        if dist is None:
            distance_m = 0.0
        elif hasattr(dist, "m"):
            distance_m = float(dist.m)
        else:
            distance_m = float(dist)
        _broadcast_driver_provisional_assign(
            booking=booking,
            driver_profile=d,
            distance_m=distance_m,
        )
    if ring is not None:
        _record_offer_round(booking=booking, ring=ring, round_id=round_id, driver_ids=driver_ids)
    else:
        record_trip_event(
            booking=booking,
            event_type=RIDE_OFFER_ROUND,
            payload={
                "round_id": round_id,
                "ring_index": -1,
                "inner_km": None,
                "outer_km": None,
                "driver_ids": driver_ids,
                "fallback": "any_online",
            },
        )
    logger.info(
        "dispatch: provisional offers pushed to drivers via WebSocket (driver_<id>)",
        extra={
            "booking_id": str(booking.id),
            "round_id": round_id,
            "ring_index": ring.index if ring else -1,
            "offered_driver_ids": driver_ids,
            "fallback": ring is None,
        },
    )
    from .tasks import wait_after_offer_round  # local import avoids circular

    cumulative = [str(x) for x in previously_notified] + [str(x) for x in driver_ids]
    completed_ring_index = ring.index if ring is not None else max(0, len(iter_rings()) - 1)
    try:
        wait_after_offer_round.apply_async(
            args=[str(booking.id), round_id, completed_ring_index, cumulative],
            countdown=OFFER_WAIT_SECONDS,
        )
    except Exception:
        logger.warning(
            "dispatch: Celery unavailable for offer wait; advancing rings in-process after countdown",
            extra={"booking_id": str(booking.id), "round_id": round_id},
            exc_info=True,
        )
        import threading
        import time

        def _advance_after_wait() -> None:
            time.sleep(OFFER_WAIT_SECONDS)
            wait_after_offer_round.run(str(booking.id), round_id, completed_ring_index, cumulative)

        threading.Thread(target=_advance_after_wait, daemon=True).start()
    return round_id, len(driver_ids)


def run_dispatch_any_online_fallback(
    *, booking: Booking, previously_notified: list[str] | None = None
) -> tuple[str | None, int]:
    """After ring expansion: offer nearest online drivers regardless of distance."""
    previously_notified = list(previously_notified or [])
    rows = find_any_online_drivers(booking=booking, exclude_driver_ids=previously_notified)
    return _offer_drivers(booking=booking, rows=rows, ring=None, previously_notified=previously_notified)


def run_dispatch_for_ring(
    *, booking: Booking, ring: RingDef, previously_notified: list[str] | None = None
) -> tuple[str | None, int]:
    """
    Find drivers in `ring` excluding all previously notified drivers.
    Returns (round_id or None if no new offers, count_offered).
    """
    previously_notified = list(previously_notified or [])
    rows = find_drivers_in_ring(booking=booking, ring=ring, exclude_driver_ids=previously_notified)
    pt = booking.pickup_location
    pickup_lat = float(pt.y) if pt is not None else None
    pickup_lng = float(pt.x) if pt is not None else None
    if not rows:
        logger.info(
            "dispatch: ring empty — no matched drivers online with live location within band",
            extra={
                "booking_id": str(booking.id),
                "ring_index": ring.index,
                "inner_km": ring.inner_km,
                "outer_km": ring.outer_km,
                "vehicle_category_id": str(booking.vehicle_category_id),
                "pickup_lat": pickup_lat,
                "pickup_lng": pickup_lng,
            },
        )
        return None, 0
    driver_rows = [(loc.driver, dist) for loc, dist in rows]
    return _offer_drivers(booking=booking, rows=driver_rows, ring=ring, previously_notified=previously_notified)


@transaction.atomic
def mark_no_driver_available(*, booking: Booking) -> None:
    booking.refresh_from_db()
    if booking.state != Booking.BookingState.SEARCHING_DRIVER or booking.driver_id:
        return
    booking.state = Booking.BookingState.FAILED
    booking.save(update_fields=["state", "updated_at"])
    record_trip_event(
        booking=booking,
        event_type="no_driver_found",
        from_state=Booking.BookingState.SEARCHING_DRIVER,
        to_state=Booking.BookingState.FAILED,
        payload={"reason": "no_driver_found"},
    )
    broadcast_event(
        f"booking_{booking.id}",
        "driver_found",
        {"booking_id": str(booking.id), "status": "no_driver_found"},
    )
    broadcast_event(
        f"user_{booking.customer_id}",
        "driver_found",
        {"booking_id": str(booking.id), "status": "no_driver_found"},
    )


def start_expanding_driver_dispatch(*, booking: Booking) -> None:
    """Entry point: begin ring 0 (or next ring) — used by tasks."""
    from .tasks import continue_dispatch_rings  # local import

    notified = [str(x) for x in get_notified_driver_ids(booking=booking)]
    # Same rationale as BookingViewSet.perform_create: ring matching must execute without relying on a
    # background worker for the kicked-off recursion that sends provisional offers over Channels.
    continue_dispatch_rings.run(str(booking.id), 0, notified)


def _broadcast_customer_driver_assigned(*, booking: Booking) -> None:
    driver_profile = booking.driver
    if not driver_profile:
        return
    assignment_payload = {
        "booking_id": str(booking.id),
        "driver_id": str(driver_profile.id),
        "driver_phone": driver_profile.user.phone,
    }
    broadcast_event(f"booking_{booking.id}", "driver_assigned", assignment_payload)
    broadcast_event(f"user_{booking.customer_id}", "driver_assigned", assignment_payload)
    broadcast_event(f"driver_{driver_profile.id}", "driver_assigned", assignment_payload)
    if booking.customer and booking.customer.city:
        broadcast_event(
            f"admin_city_{booking.customer.city.lower()}",
            "driver_assigned",
            assignment_payload,
        )


@transaction.atomic
def cancel_pending_offers_for_others(
    *, booking: Booking, winning_driver_id: str, candidate_driver_ids: list[str] | None = None
) -> None:
    cands = [d for d in (candidate_driver_ids or get_notified_driver_ids(booking=booking)) if str(d) != str(winning_driver_id)]
    for did in cands:
        broadcast_event(
            f"driver_{did}",
            "ride_request_cancelled",
            {"booking_id": str(booking.id)},
        )


def on_driver_won_ride(*, booking: Booking, winning_driver_id: str) -> None:
    """
    After booking has driver and state DRIVER_ACCEPTED; notify customer and cancel losers.
    """
    cancel_pending_offers_for_others(booking=booking, winning_driver_id=winning_driver_id)
    _broadcast_customer_driver_assigned(booking=booking)


# --- Legacy function name (dispatch API) ---------------------------------
def assign_driver_to_booking(*, booking: Booking, timeout_seconds: int = 30) -> Any:
    """
    Replaced by batch ring dispatch. Kept for API compatibility.
    `timeout_seconds` is kept for signature compatibility; offer wait is OFFER_WAIT_SECONDS.
    """
    booking.refresh_from_db()
    if booking.state != Booking.BookingState.SEARCHING_DRIVER or booking.driver_id:
        return booking.driver
    start_expanding_driver_dispatch(booking=booking)
    return None
