from django.contrib.gis.geos import Polygon
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole
from .models import ServiceZone


class ServiceZoneSerializer(serializers.ModelSerializer):
    polygon_points = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
        write_only=True,
        required=False,
    )

    class Meta:
        model = ServiceZone
        fields = "__all__"

    def create(self, validated_data):
        points = validated_data.pop("polygon_points", None)
        if points:
            validated_data["polygon"] = Polygon(tuple((float(lng), float(lat)) for lat, lng in points))
        return super().create(validated_data)


class ServiceZoneViewSet(viewsets.ModelViewSet):
    queryset = ServiceZone.objects.filter(is_deleted=False)
    serializer_class = ServiceZoneSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("city_name", "active")
    search_fields = ("city_name", "zone_name")
    ordering_fields = ("created_at", "dispatch_radius_km")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsAdminRole()]
