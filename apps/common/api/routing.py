import json
import urllib.error
import urllib.request

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

OSRM_BASES = (
    "https://router.project-osrm.org",
    "https://routing.openstreetmap.de/routed-car",
)


def _fetch_osrm_route_payload(origin_lng: float, origin_lat: float, dest_lng: float, dest_lat: float) -> dict | None:
    path = (
        f"/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        "?overview=simplified&geometries=geojson"
    )
    for base in OSRM_BASES:
        try:
            url = f"{base}{path}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "nashik-logistics-backend/1.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("code") != "Ok":
                continue
            routes = payload.get("routes")
            if not routes or not isinstance(routes, list):
                continue
            route = routes[0]
            coords = route.get("geometry", {}).get("coordinates")
            if not isinstance(coords, list) or len(coords) < 2:
                continue
            return route
        except (urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError, Exception):
            continue
    return None


def fetch_osrm_route_metrics(
    origin_lng: float,
    origin_lat: float,
    dest_lng: float,
    dest_lat: float,
) -> dict | None:
    """Return driving distance/duration from OSRM, or None if unavailable."""
    route = _fetch_osrm_route_payload(origin_lng, origin_lat, dest_lng, dest_lat)
    if route is None:
        return None
    try:
        distance_m = float(route.get("distance") or 0)
        duration_s = float(route.get("duration") or 0)
        if distance_m <= 0:
            return None
        coords = route.get("geometry", {}).get("coordinates", [])
        points = [{"lat": float(c[1]), "lng": float(c[0])} for c in coords if len(c) >= 2]
        return {
            "distance_km": distance_m / 1000.0,
            "duration_min": max(1, int(round(duration_s / 60.0))),
            "points": points,
        }
    except Exception:
        return None


def _fetch_osrm_route(origin_lng: float, origin_lat: float, dest_lng: float, dest_lat: float) -> list[dict]:
    metrics = fetch_osrm_route_metrics(origin_lng, origin_lat, dest_lng, dest_lat)
    if metrics is None:
        return []
    return metrics["points"]


class DrivingRouteView(APIView):
    """Public driving route polyline (OSRM). Used by customer app trip maps."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            origin_lat = float(request.query_params["origin_lat"])
            origin_lng = float(request.query_params["origin_lng"])
            dest_lat = float(request.query_params["dest_lat"])
            dest_lng = float(request.query_params["dest_lng"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "origin_lat, origin_lng, dest_lat, dest_lng are required numbers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        points = _fetch_osrm_route(origin_lng, origin_lat, dest_lng, dest_lat)
        if len(points) < 2:
            return Response({"detail": "No driving route found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"points": points}, status=status.HTTP_200_OK)
