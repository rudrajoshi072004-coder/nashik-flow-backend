"""Authoritative billable distance for fare calculation."""

from __future__ import annotations

from decimal import Decimal
import math

from apps.common.api.routing import fetch_osrm_route_metrics


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return Decimal(str(round(r * c, 2)))


def authoritative_distance_km(
    pickup_lat: float,
    pickup_lng: float,
    drop_lat: float,
    drop_lng: float,
) -> tuple[Decimal, str, int | None]:
    """
    Prefer OSRM driving distance; fall back to haversine.
    Returns (distance_km, source, duration_min_or_none).
    """
    metrics = fetch_osrm_route_metrics(pickup_lng, pickup_lat, drop_lng, drop_lat)
    if metrics is not None:
        distance_km = Decimal(str(round(metrics["distance_km"], 2)))
        duration_min = metrics.get("duration_min")
        return distance_km, "osrm", duration_min
    return haversine_km(pickup_lat, pickup_lng, drop_lat, drop_lng), "haversine", None
