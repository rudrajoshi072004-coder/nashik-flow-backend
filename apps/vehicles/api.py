from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole, IsDriverOrAdmin
from .models import Vehicle
from .serializers import VehicleSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related("driver", "category", "driver__user", "category")
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("status", "category", "driver")
    search_fields = ("registration_number", "brand", "model_name", "driver__user__phone")
    ordering_fields = ("created_at", "registration_number")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsDriverOrAdmin()]
        return [IsAdminRole()]
