from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions.rbac import IsAdminRole
from apps.vehicle_categories.models import VehicleCategory
from .models import PricingRule, RouteTollCache
from .serializers import PricingRuleSerializer, RouteTollCacheSerializer
from .toll_service import clear_route_toll_cache, get_or_fetch_route_toll


class PricingRuleViewSet(viewsets.ModelViewSet):
    queryset = PricingRule.objects.filter(is_deleted=False).select_related("vehicle_category")
    serializer_class = PricingRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("city", "vehicle_category", "active")
    search_fields = ("name", "city", "vehicle_category__name")
    ordering_fields = ("created_at", "base_fare", "per_km_rate")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsAdminRole()]


class RouteTollViewSet(viewsets.ModelViewSet):
    """
    CRUD and cache management for route toll charges.
    Allows admins to inspect, add manual overrides, or clear cached corridor tolls.
    """
    queryset = RouteTollCache.objects.select_related("vehicle_category").order_by("-updated_at")
    serializer_class = RouteTollCacheSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ("origin_geohash", "destination_geohash", "vehicle_category_slug", "is_active", "source")
    search_fields = ("origin_name", "destination_name", "origin_geohash", "destination_geohash")
    ordering_fields = ("created_at", "updated_at", "expires_at", "toll_amount")

    def get_permissions(self):
        # Allow authenticated users (e.g. customer/driver apps during quote check) to use estimate
        if self.action == "estimate":
            return [IsAuthenticated()]
        return [IsAdminRole()]

    @action(detail=False, methods=["post"], url_path="estimate")
    def estimate(self, request):
        """Test or estimate toll for any arbitrary coordinates."""
        try:
            pickup_lat = float(request.data["pickup_lat"])
            pickup_lng = float(request.data["pickup_lng"])
            drop_lat = float(request.data["drop_lat"])
            drop_lng = float(request.data["drop_lng"])
        except (KeyError, ValueError, TypeError):
            return Response(
                {"detail": "pickup_lat, pickup_lng, drop_lat, drop_lng are required floating point numbers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cat = None
        cat_id = request.data.get("vehicle_category_id")
        if cat_id:
            try:
                cat = VehicleCategory.objects.get(id=cat_id)
            except Exception:
                pass

        result = get_or_fetch_route_toll(
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            drop_lat=drop_lat,
            drop_lng=drop_lng,
            category=cat,
        )
        return Response(
            {
                "toll_amount": str(result.get("toll_amount", "0.00")),
                "currency": result.get("currency", "INR"),
                "has_tolls": result.get("has_tolls", False),
                "source": result.get("source", "none"),
                "cached": result.get("cached", False),
                "origin_geohash": result.get("origin_geohash", ""),
                "destination_geohash": result.get("destination_geohash", ""),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="flush-cache")
    def flush_cache(self, request):
        """Flushes Redis and DB toll cache for refreshed calculation."""
        count = clear_route_toll_cache()
        return Response(
            {"detail": f"Successfully flushed {count} cached route toll records from cache and database."},
            status=status.HTTP_200_OK,
        )

