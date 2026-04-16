from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import WalletTransaction
from .serializers import WalletTransactionSerializer


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("transaction_type", "booking")
    search_fields = ("reference_id", "booking__id")
    ordering_fields = ("created_at", "amount")

    def get_queryset(self):
        user = self.request.user
        if user.role not in {"driver", "fleet_driver", "super_admin", "finance_admin", "city_manager"}:
            return WalletTransaction.objects.none()
        if user.role in {"driver", "fleet_driver"}:
            return WalletTransaction.objects.filter(wallet__driver__user=user).select_related("wallet", "booking")
        return WalletTransaction.objects.select_related("wallet", "booking", "initiated_by")
