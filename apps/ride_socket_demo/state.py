"""In-memory demo store (replaces Node ride-backend + Mongo memory server)."""

from __future__ import annotations

import asyncio
import math
import uuid
from typing import Any

_lock = asyncio.Lock()
_drivers: dict[str, dict[str, Any]] = {}
_rides: dict[str, dict[str, Any]] = {}

# ~250 km demo radius (matches Node $maxDistance).
_MAX_DISTANCE_M = 250_000


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def seed_drivers_if_empty() -> None:
    """Idempotent sync seed (runs from AppConfig.ready)."""
    if _drivers:
        return
    # Nashik-ish coordinates [lng, lat], same as Node demo.
    raw = (
        ("Driver A", 73.7898, 19.9975),
        ("Driver B", 73.7900, 19.9980),
        ("Driver C", 73.8500, 20.0500),
    )
    for name, lng, lat in raw:
        did = str(uuid.uuid4())
        _drivers[did] = {
            "id": did,
            "name": name,
            "lng": lng,
            "lat": lat,
            "status": "available",
            "socket_id": None,
        }


async def drivers_snapshot() -> list[dict[str, Any]]:
    async with _lock:
        return [
            {
                "_id": d["id"],
                "name": d["name"],
                "status": d["status"],
                "currentLocation": {"type": "Point", "coordinates": [d["lng"], d["lat"]]},
            }
            for d in _drivers.values()
        ]


async def set_driver_socket(driver_id: str, socket_id: str | None, status: str = "available") -> dict[str, Any] | None:
    async with _lock:
        d = _drivers.get(driver_id)
        if not d:
            return None
        d["socket_id"] = socket_id
        d["status"] = status
        return dict(d)


async def unregister_socket(sid: str) -> None:
    async with _lock:
        for d in _drivers.values():
            if d.get("socket_id") == sid:
                d["socket_id"] = None
                d["status"] = "available"


async def create_ride(payload: dict[str, Any], customer_sid: str) -> dict[str, Any]:
    async with _lock:
        rid = str(uuid.uuid4())
        ride = {
            "id": rid,
            "customerId": payload.get("customerId") or "customer_1",
            "customer_socket_id": customer_sid,
            "pickup": payload["pickup"],
            "destination": payload["destination"],
            "fare": payload.get("fare"),
            "pickupAddressText": payload.get("pickupAddressText"),
            "dropAddressText": payload.get("dropAddressText"),
            "status": "pending",
            "driver_id": None,
            "notified_driver_ids": [],
        }
        _rides[rid] = ride
        return dict(ride)


async def nearby_available_online(
    pickup_lng: float, pickup_lat: float
) -> list[dict[str, Any]]:
    async with _lock:
        eligible: list[dict[str, Any]] = []
        for d in _drivers.values():
            if d["status"] != "available" or not d.get("socket_id"):
                continue
            dist = _haversine_m(pickup_lng, pickup_lat, d["lng"], d["lat"])
            if dist <= _MAX_DISTANCE_M:
                eligible.append(dict(d))
        if eligible:
            return eligible
        return [dict(d) for d in _drivers.values() if d["status"] == "available" and d.get("socket_id")]


async def save_ride_notified(rid: str, driver_ids: list[str]) -> None:
    async with _lock:
        r = _rides.get(rid)
        if not r:
            return
        r["notified_driver_ids"] = list(driver_ids)
        _rides[rid] = r


async def try_accept_ride(ride_id: str, driver_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Returns (ride, driver) copies if transitioned pending→accepted, else (None, None)."""
    async with _lock:
        r = _rides.get(ride_id)
        if not r or r["status"] != "pending":
            return None, None
        if driver_id not in _drivers:
            return None, None
        r["status"] = "accepted"
        r["driver_id"] = driver_id
        d = _drivers[driver_id]
        d["status"] = "available"
        _rides[ride_id] = r
        _drivers[driver_id] = d
        return dict(r), dict(d)


def ride_notified_ids(ride: dict[str, Any]) -> list[str]:
    return list(ride.get("notified_driver_ids") or [])
