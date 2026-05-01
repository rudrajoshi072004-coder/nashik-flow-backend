from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny

from apps.common.permissions.rbac import IsAdminRole
from .models import VehicleCategory


class VehicleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleCategory
        fields = "__all__"


class VehicleCategoryViewSet(viewsets.ModelViewSet):
    queryset = VehicleCategory.objects.filter(is_deleted=False)
    serializer_class = VehicleCategorySerializer
    filterset_fields = ("active", "helper_supported", "intra_city_available")
    search_fields = ("name", "payload_type")
    ordering_fields = ("priority_order", "base_fare", "per_km_rate")

    def get_authenticators(self):
        if self.action in {"list", "retrieve"}:
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdminRole()]
