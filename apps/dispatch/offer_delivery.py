"""Guaranteed offer delivery: WebSocket ack tracking, FCM fallback, assignment locks."""

from __future__ import annotations

import logging

from django.conf import settings

from apps.tracking.redis_geo import get_redis

logger = logging.getLogger(__name__)

ASSIGN_LOCK_PREFIX = "dispatch:lock:"
OFFER_ACK_PREFIX = "offer:ack:"
ASSIGN_LOCK_TTL = 60
OFFER_ACK_TTL = getattr(settings, "OFFER_WINDOW_SECONDS", 30)


def try_assign_driver(booking_id: str, driver_id: str) -> bool:
    r = get_redis()
    if r is None:
        return True
    lock_key = f"{ASSIGN_LOCK_PREFIX}{driver_id}"
    return bool(r.set(lock_key, str(booking_id), nx=True, ex=ASSIGN_LOCK_TTL))


def release_driver_lock(driver_id: str) -> None:
    r = get_redis()
    if r is None:
        return
    r.delete(f"{ASSIGN_LOCK_PREFIX}{driver_id}")


def register_offer_pending(booking_id: str, driver_id: str) -> None:
    r = get_redis()
    if r is None:
        return
    r.set(f"{OFFER_ACK_PREFIX}{booking_id}:{driver_id}", "pending", ex=OFFER_ACK_TTL)


def record_driver_ack(booking_id: str, driver_id: str) -> None:
    r = get_redis()
    if r is None:
        return
    r.set(f"{OFFER_ACK_PREFIX}{booking_id}:{driver_id}", "acked", ex=OFFER_ACK_TTL)


def get_offer_ack_status(booking_id: str, driver_id: str) -> str | None:
    r = get_redis()
    if r is None:
        return None
    return r.get(f"{OFFER_ACK_PREFIX}{booking_id}:{driver_id}")


def schedule_fcm_fallback(booking_id: str, driver_id: str, offer_payload: dict) -> None:
    wait = getattr(settings, "OFFER_ACK_WAIT_SECONDS", 4)
    try:
        from apps.dispatch.tasks import send_fcm_offer_fallback

        send_fcm_offer_fallback.apply_async(
            args=[str(booking_id), str(driver_id), offer_payload],
            countdown=wait,
        )
    except Exception:
        logger.exception("Failed to schedule FCM fallback for booking %s driver %s", booking_id, driver_id)
