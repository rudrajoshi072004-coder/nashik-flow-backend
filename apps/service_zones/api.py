from django.contrib.gis.geos import Polygon
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions.rbac import IsAdminRole
from .models import ServiceZone
from .services import (
    calculate_zone_availability,
    extract_polygon_coords,
    generate_default_directional_sections,
)


class ServiceZoneSerializer(serializers.ModelSerializer):
    polygon_points = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
        write_only=True,
        required=False,
    )
    polygon_coordinates = serializers.SerializerMethodField(read_only=True)
    center_point = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ServiceZone
        fields = [
            "id",
            "city_name",
            "zone_name",
            "active",
            "dispatch_radius_km",
            "service_radius_km",
            "directional_sections",
            "polygon_coordinates",
            "center_point",
            "polygon_points",
            "created_at",
            "updated_at",
        ]

    def get_polygon_coordinates(self, obj: ServiceZone) -> list[list[float]]:
        coords, _ = extract_polygon_coords(obj)
        return coords

    def get_center_point(self, obj: ServiceZone) -> list[float]:
        _, center = extract_polygon_coords(obj)
        return center

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure directional_sections is populated with default 4 directional wedges if empty
        sections = ret.get("directional_sections")
        if not sections or not isinstance(sections, dict) or len(sections) < 4:
            coords = ret.get("polygon_coordinates") or []
            center = ret.get("center_point") or [19.9975, 73.7898]
            ret["directional_sections"] = generate_default_directional_sections(coords, center)
        return ret

    def create(self, validated_data):
        points = validated_data.pop("polygon_points", None)
        if points and len(points) >= 3:
            # GEOS Polygon requires first and last point to be equal
            closed = list(points)
            if closed[0] != closed[-1]:
                closed.append(closed[0])
            validated_data["polygon"] = Polygon(tuple((float(lng), float(lat)) for lat, lng in closed))
        elif "polygon" not in validated_data:
            validated_data["polygon"] = Polygon(
                ((73.71, 19.92), (73.86, 19.92), (73.86, 20.06), (73.71, 20.06), (73.71, 19.92))
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        points = validated_data.pop("polygon_points", None)
        if points and len(points) >= 3:
            closed = list(points)
            if closed[0] != closed[-1]:
                closed.append(closed[0])
            instance.polygon = Polygon(tuple((float(lng), float(lat)) for lat, lng in closed))
        return super().update(instance, validated_data)


class ServiceZoneViewSet(viewsets.ModelViewSet):
    queryset = ServiceZone.objects.filter(is_deleted=False)
    serializer_class = ServiceZoneSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("city_name", "active")
    search_fields = ("city_name", "zone_name")
    ordering_fields = ("created_at", "dispatch_radius_km")

    def get_permissions(self):
        if self.action in {"list", "retrieve", "driver_availability", "availability_overview"}:
            return [IsAuthenticated()]
        return [IsAdminRole()]

    @action(detail=True, methods=["get"], url_path="driver-availability")
    def driver_availability(self, request, pk=None):
        """Returns real-time driver availability, directional sections, and red-green gradient metrics."""
        zone = self.get_object()
        data = calculate_zone_availability(zone)
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="availability-overview")
    def availability_overview(self, request):
        """Returns availability summaries for all active service zones."""
        city = request.query_params.get("city", "").strip()
        qs = self.get_queryset().filter(active=True)
        if city:
            qs = qs.filter(city_name__iexact=city)

        overview = [calculate_zone_availability(zone) for zone in qs]
        return Response({"count": len(overview), "zones": overview}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="configure-sections")
    def configure_sections(self, request, pk=None):
        """Configure or update the 4 directional sections (North, South, East, West)."""
        zone = self.get_object()
        sections_payload = request.data.get("directional_sections")
        if not sections_payload or not isinstance(sections_payload, dict):
            return Response(
                {"detail": "directional_sections must be a dictionary with keys north, south, east, west."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        zone.directional_sections = sections_payload
        zone.save(update_fields=["directional_sections", "updated_at"])

        availability = calculate_zone_availability(zone)
        return Response({
            "message": "Directional sections updated successfully",
            "directional_sections": zone.directional_sections,
            "availability": availability,
        }, status=status.HTTP_200_OK)
