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


def _fetch_osrm_route(origin_lng: float, origin_lat: float, dest_lng: float, dest_lat: float) -> list[dict]:
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
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("code") != "Ok":
                continue
            coords = payload["routes"][0]["geometry"]["coordinates"]
            if not isinstance(coords, list) or len(coords) < 2:
                continue
            return [{"lat": float(c[1]), "lng": float(c[0])} for c in coords]
        except (urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return []


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
