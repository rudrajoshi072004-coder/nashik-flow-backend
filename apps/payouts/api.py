import uuid
from decimal import Decimal

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsAdminRole, IsDriverRole
from apps.wallet_transactions.models import WalletTransaction
from .models import Payout
from .serializers import PayoutSerializer


class PayoutRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1.00"))
    notes = serializers.CharField(required=False, allow_blank=True)


class PayoutUpdateStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Payout.Status.choices)
    processed_reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class PayoutViewSet(viewsets.ModelViewSet):
    queryset = Payout.objects.select_related("driver", "wallet", "requested_by", "processed_by")
    serializer_class = PayoutSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("status",)
    search_fields = ("driver__user__phone", "processed_reference")
    ordering_fields = ("created_at", "amount")

    def get_queryset(self):
        user = self.request.user
        if user.role in {"driver", "fleet_driver"}:
            return self.queryset.filter(driver__user=user)
        return self.queryset

    @action(detail=False, methods=["post"], url_path="request", permission_classes=[IsDriverRole])
    def request_payout(self, request):
        serializer = PayoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        driver = request.user.driver_profile
        wallet = driver.wallet
        amount = serializer.validated_data["amount"]
        if wallet.withdrawable_balance < amount:
            return success_response(
                data={"detail": "Insufficient withdrawable balance."},
                message="Validation failed",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        payout = Payout.objects.create(
            driver=driver,
            wallet=wallet,
            amount=amount,
            requested_by=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=WalletTransaction.TransactionType.PAYOUT_REQUEST,
            amount=-amount,
            balance_before=wallet.current_balance,
            balance_after=wallet.current_balance - amount,
            reference_id=f"payout-req-{uuid.uuid4()}",
            initiated_by=request.user,
            metadata={"payout_id": str(payout.id)},
        )
        wallet.current_balance -= amount
        wallet.withdrawable_balance -= amount
        wallet.save(update_fields=["current_balance", "withdrawable_balance", "updated_at"])
        return success_response(PayoutSerializer(payout).data, message="Payout requested", status_code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="update-status", permission_classes=[IsAdminRole])
    def update_status(self, request, pk=None):
        payout = self.get_object()
        serializer = PayoutUpdateStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payout.status = serializer.validated_data["status"]
        payout.processed_by = request.user
        payout.processed_reference = serializer.validated_data.get("processed_reference", payout.processed_reference)
        payout.notes = serializer.validated_data.get("notes", payout.notes)
        payout.save(update_fields=["status", "processed_by", "processed_reference", "notes", "updated_at"])
        return success_response(PayoutSerializer(payout).data, message="Payout status updated")
