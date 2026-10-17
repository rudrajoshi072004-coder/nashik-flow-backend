"""Service zone resolution for trip classification."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.service_zones.models import ServiceZone

if TYPE_CHECKING:
    from apps.vehicle_categories.models import VehicleCategory


def resolve_service_zone(city: str) -> ServiceZone | None:
    city_norm = (city or "Nashik").strip()
    return (
        ServiceZone.objects.filter(is_deleted=False, active=True, city_name__iexact=city_norm)
        .order_by("-updated_at")
        .first()
    )


def service_radius_km_for_city(city: str) -> Decimal:
    """Return configured service radius; fallback to 50 if unconfigured."""
    city_norm = (city or "Nashik").strip()
    zone = resolve_service_zone(city_norm)
    if zone is None:
        return Decimal("50")
    radius = zone.service_radius_km
    if radius is None or radius <= 0:
        return Decimal("50")
    return Decimal(str(radius))


def classify_trip_type(
    distance_km: Decimal,
    city: str,
    category: VehicleCategory | None = None,
) -> str:
    """Return Booking.TripType value based on distance vs configured outstation threshold."""
    from apps.bookings.models import Booking

    if category and getattr(category, "outstation_threshold_km", None) and category.outstation_threshold_km > 0:
        radius = category.outstation_threshold_km
    else:
        radius = service_radius_km_for_city(city)

    if distance_km <= radius:
        return Booking.TripType.WITHIN_CITY
    return Booking.TripType.OUTSTATION


def point_in_polygon(lat: float, lng: float, polygon_points: list[list[float]]) -> bool:
    """Ray casting point in polygon algorithm. Points format: [[lat, lng], ...]"""
    if not polygon_points or len(polygon_points) < 3:
        return False
    inside = False
    n = len(polygon_points)
    p1_lat, p1_lng = polygon_points[0]
    for i in range(1, n + 1):
        p2_lat, p2_lng = polygon_points[i % n]
        if min(p1_lng, p2_lng) < lng <= max(p1_lng, p2_lng):
            lat_intersect = (lng - p1_lng) * (p2_lat - p1_lat) / (p2_lng - p1_lng) + p1_lat
            if lat <= lat_intersect:
                inside = not inside
        p1_lat, p1_lng = p2_lat, p2_lng
    return inside


def interpolate_gradient_color(ratio: float) -> str:
    """
    Interpolate between Red (#ef4444) -> Amber (#f59e0b) -> Green (#22c55e).
    ratio in [0.0, 1.0].
    0.0 -> #ef4444 (Critical Deficit)
    0.5 -> #f59e0b (Moderate Availability)
    1.0 -> #22c55e (Optimal Availability)
    """
    clamped = max(0.0, min(1.0, float(ratio)))
    if clamped <= 0.5:
        t = clamped / 0.5
        r = int(239 + t * (245 - 239))
        g = int(68 + t * (158 - 68))
        b = int(68 + t * (11 - 68))
    else:
        t = (clamped - 0.5) / 0.5
        r = int(245 + t * (34 - 245))
        g = int(158 + t * (197 - 158))
        b = int(11 + t * (94 - 11))
    return f"#{r:02x}{g:02x}{b:02x}"


def extract_polygon_coords(zone: ServiceZone) -> tuple[list[list[float]], list[float]]:
    """Return ([[lat, lng], ...], [center_lat, center_lng])."""
    coords: list[list[float]] = []
    if getattr(zone, "polygon", None):
        try:
            # GEOSPolygon coordinates are ((lng, lat), ...)
            raw_ring = zone.polygon[0]
            coords = [[round(float(pt[1]), 6), round(float(pt[0]), 6)] for pt in raw_ring]
        except Exception:
            coords = []

    if not coords or len(coords) < 3:
        # Fallback Nashik Core polygon
        coords = [
            [19.9200, 73.7100],
            [20.0600, 73.7100],
            [20.0600, 73.8600],
            [19.9200, 73.8600],
            [19.9200, 73.7100],
        ]

    lats = [pt[0] for pt in coords]
    lngs = [pt[1] for pt in coords]
    center = [round((min(lats) + max(lats)) / 2, 6), round((min(lngs) + max(lngs)) / 2, 6)]
    return coords, center


def generate_default_directional_sections(
    coords: list[list[float]],
    center: list[float],
) -> dict:
    """Generate 4 directional polygon wedges (North, South, East, West) partition."""
    lats = [pt[0] for pt in coords]
    lngs = [pt[1] for pt in coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    c_lat, c_lng = center[0], center[1]

    return {
        "north": {
            "id": "north",
            "name": "North Section (Panchavati / Dindori)",
            "direction": "N",
            "angle_deg": 0,
            "target_drivers": 8,
            "active": True,
            "dispatch_radius_km": 6.0,
            "polygon_points": [
                [round(c_lat, 6), round(c_lng, 6)],
                [round(max_lat, 6), round(min_lng, 6)],
                [round(max_lat, 6), round(max_lng, 6)],
                [round(c_lat, 6), round(c_lng, 6)],
            ],
        },
        "east": {
            "id": "east",
            "name": "East Section (Dwarka / Gandhinagar)",
            "direction": "E",
            "angle_deg": 90,
            "target_drivers": 6,
            "active": True,
            "dispatch_radius_km": 5.5,
            "polygon_points": [
                [round(c_lat, 6), round(c_lng, 6)],
                [round(max_lat, 6), round(max_lng, 6)],
                [round(min_lat, 6), round(max_lng, 6)],
                [round(c_lat, 6), round(c_lng, 6)],
            ],
        },
        "south": {
            "id": "south",
            "name": "South Section (Nashik Rd / Deolali)",
            "direction": "S",
            "angle_deg": 180,
            "target_drivers": 8,
            "active": True,
            "dispatch_radius_km": 6.5,
            "polygon_points": [
                [round(c_lat, 6), round(c_lng, 6)],
                [round(min_lat, 6), round(max_lng, 6)],
                [round(min_lat, 6), round(min_lng, 6)],
                [round(c_lat, 6), round(c_lng, 6)],
            ],
        },
        "west": {
            "id": "west",
            "name": "West Section (Satpur / Ambad MIDC)",
            "direction": "W",
            "angle_deg": 270,
            "target_drivers": 10,
            "active": True,
            "dispatch_radius_km": 7.0,
            "polygon_points": [
                [round(c_lat, 6), round(c_lng, 6)],
                [round(min_lat, 6), round(min_lng, 6)],
                [round(max_lat, 6), round(min_lng, 6)],
                [round(c_lat, 6), round(c_lng, 6)],
            ],
        },
    }


def calculate_zone_availability(zone: ServiceZone) -> dict:
    """Calculate real-time driver availability and red-green gradient color per section."""
    from apps.tracking.models import DriverLiveLocation

    coords, center = extract_polygon_coords(zone)
    sections = zone.directional_sections or {}
    if not sections or not isinstance(sections, dict) or len(sections) < 4:
        sections = generate_default_directional_sections(coords, center)

    # Fetch active driver live locations
    live_rows = (
        DriverLiveLocation.objects.select_related("driver", "driver__user", "booking")
        .filter(driver__user__city__iexact=zone.city_name)
    )

    drivers_data: list[dict] = []
    for row in live_rows:
        try:
            pt = row.location
            d_lng = float(pt.x)
            d_lat = float(pt.y)
        except Exception:
            continue

        u = row.driver.user
        name = u.name if getattr(u, "name", None) else f"Driver {str(row.driver.id)[:6]}"
        is_online = getattr(row.driver, "is_online", True)
        is_busy = row.booking is not None
        status = "Busy" if is_busy else ("Online" if is_online else "Offline")

        drivers_data.append({
            "id": str(row.driver.id),
            "name": name,
            "phone": u.phone,
            "lat": d_lat,
            "lng": d_lng,
            "status": status,
            "is_available": is_online and not is_busy,
            "speed_kmph": float(row.speed_kmph or 0),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })

    # Group drivers by the 4 sections
    section_results: dict = {}
    zone_total_drivers = 0
    zone_available_drivers = 0
    zone_busy_drivers = 0
    zone_target_quota = 0

    direction_keys = ["north", "south", "east", "west"]
    for key in direction_keys:
        sec_cfg = sections.get(key) or {}
        pts = sec_cfg.get("polygon_points", [])
        target = int(sec_cfg.get("target_drivers") or 8)
        zone_target_quota += target

        sec_drivers: list[dict] = []
        for d in drivers_data:
            if point_in_polygon(d["lat"], d["lng"], pts):
                sec_drivers.append(d)

        total_cnt = len(sec_drivers)
        avail_cnt = sum(1 for d in sec_drivers if d["is_available"])
        busy_cnt = sum(1 for d in sec_drivers if d["status"] == "Busy")

        zone_total_drivers += total_cnt
        zone_available_drivers += avail_cnt
        zone_busy_drivers += busy_cnt

        ratio = min(1.0, avail_cnt / max(target, 1))
        color = interpolate_gradient_color(ratio)
        if ratio >= 0.70:
            status_level = "optimal"
        elif ratio >= 0.35:
            status_level = "moderate"
        else:
            status_level = "critical"

        section_results[key] = {
            "id": key,
            "name": sec_cfg.get("name", f"{key.capitalize()} Section"),
            "direction": sec_cfg.get("direction", key[0].upper()),
            "angle_deg": sec_cfg.get("angle_deg", 0),
            "active": sec_cfg.get("active", True),
            "dispatch_radius_km": float(sec_cfg.get("dispatch_radius_km", zone.dispatch_radius_km or 5.0)),
            "polygon_points": pts,
            "target_drivers": target,
            "driver_count": total_cnt,
            "available_count": avail_cnt,
            "busy_count": busy_cnt,
            "availability_ratio": round(ratio, 2),
            "gradient_color": color,
            "status_level": status_level,
            "drivers": sec_drivers,
        }

    overall_ratio = min(1.0, zone_available_drivers / max(zone_target_quota, 1))
    overall_color = interpolate_gradient_color(overall_ratio)

    return {
        "zone_id": str(zone.id),
        "zone_name": zone.zone_name,
        "city_name": zone.city_name,
        "active": zone.active,
        "dispatch_radius_km": float(zone.dispatch_radius_km or 5.0),
        "service_radius_km": float(zone.service_radius_km or 50.0),
        "polygon_coordinates": coords,
        "center_point": center,
        "sections": section_results,
        "total_drivers": zone_total_drivers,
        "available_drivers": zone_available_drivers,
        "busy_drivers": zone_busy_drivers,
        "target_quota": zone_target_quota,
        "overall_availability_ratio": round(overall_ratio, 2),
        "overall_gradient_color": overall_color,
        "overall_status": "optimal" if overall_ratio >= 0.7 else ("moderate" if overall_ratio >= 0.35 else "critical"),
    }

