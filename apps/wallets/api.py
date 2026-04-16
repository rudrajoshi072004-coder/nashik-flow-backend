from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole, IsDriverOrAdmin
from .models import Wallet
from .serializers import WalletSerializer


class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wallet.objects.select_related("driver", "driver__user")
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("driver",)
    search_fields = ("driver__user__phone",)
    ordering_fields = ("current_balance", "updated_at")

    def get_permissions(self):
        if self.action == "list":
            return [IsAdminRole()]
        return [IsDriverOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role in {"driver", "fleet_driver"}:
            return self.queryset.filter(driver__user=user)
        return self.queryset
