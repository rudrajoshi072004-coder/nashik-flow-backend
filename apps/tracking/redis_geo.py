"""Redis GEO index for live driver locations (primary dispatch index)."""

from __future__ import annotations

import logging
import time
from typing import Any

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

DRIVER_GEO_KEY = "drivers:geo"
DRIVER_META_PREFIX = "driver:meta:"
LOCATION_TTL_SECONDS = getattr(settings, "DRIVER_LOCATION_TTL_SECONDS", 45)

_redis_client: redis.Redis | None = None


def redis_enabled() -> bool:
    return bool(getattr(settings, "USE_REDIS", False) and getattr(settings, "REDIS_URL", ""))


def get_redis() -> redis.Redis | None:
    global _redis_client
    if not redis_enabled():
        return None
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def write_driver_geo(
    *,
    driver_id: str,
    lat: float,
    lng: float,
    heading: float = 0,
    speed_kmph: float = 0,
    accuracy_m: float = 0,
    booking_id: str | None = None,
) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.geoadd(DRIVER_GEO_KEY, (float(lng), float(lat), str(driver_id)))
        meta_key = f"{DRIVER_META_PREFIX}{driver_id}"
        r.hset(
            meta_key,
            mapping={
                "lat": lat,
                "lng": lng,
                "heading": heading,
                "speed": speed_kmph,
                "accuracy": accuracy_m,
                "booking_id": booking_id or "",
                "updated_at": int(time.time()),
            },
        )
        r.expire(meta_key, LOCATION_TTL_SECONDS)
    except Exception:
        logger.exception("Redis GEO write failed for driver %s", driver_id)


def remove_driver_geo(driver_id: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.zrem(DRIVER_GEO_KEY, str(driver_id))
        r.delete(f"{DRIVER_META_PREFIX}{driver_id}")
    except Exception:
        logger.exception("Redis GEO remove failed for driver %s", driver_id)


def georadius_active_drivers(
    pickup_lat: float,
    pickup_lng: float,
    radius_km: float,
    *,
    exclude_driver_ids: list[str] | None = None,
    count: int = 20,
) -> list[tuple[str, float]]:
    """
    Nearest-first driver IDs within radius_km whose metadata TTL is still alive.
    Returns [(driver_id, distance_km), ...].
    """
    r = get_redis()
    if r is None:
        return []

    exclude = {str(x) for x in (exclude_driver_ids or [])}
    try:
        nearby = r.georadius(
            DRIVER_GEO_KEY,
            float(pickup_lng),
            float(pickup_lat),
            float(radius_km),
            unit="km",
            withcoord=False,
            withdist=True,
            sort="ASC",
            count=count,
        )
    except Exception:
        logger.exception("Redis GEORADIUS failed")
        return []

    active: list[tuple[str, float]] = []
    for row in nearby:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            driver_id_str, dist = str(row[0]), float(row[1])
        else:
            driver_id_str, dist = str(row), 0.0
        if driver_id_str in exclude:
            continue
        if r.exists(f"{DRIVER_META_PREFIX}{driver_id_str}"):
            active.append((driver_id_str, dist))
    return active


def driver_meta(driver_id: str) -> dict[str, Any] | None:
    r = get_redis()
    if r is None:
        return None
    data = r.hgetall(f"{DRIVER_META_PREFIX}{driver_id}")
    return data or None
