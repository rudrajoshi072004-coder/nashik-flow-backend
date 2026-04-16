from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole, IsDriverOrAdmin
from .models import DriverLiveLocation
from .serializers import DriverLiveLocationSerializer


class DriverLiveLocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DriverLiveLocation.objects.select_related("driver", "driver__user", "booking")
    serializer_class = DriverLiveLocationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("booking", "driver")
    search_fields = ("driver__user__phone", "booking__id")
    ordering_fields = ("created_at", "source_timestamp")

    def get_permissions(self):
        if self.action == "list":
            return [IsAdminRole()]
        return [IsDriverOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role in {"driver", "fleet_driver"}:
            return self.queryset.filter(driver__user=user)
        return self.queryset
