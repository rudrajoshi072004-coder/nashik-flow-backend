from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole
from .models import PricingRule
from .serializers import PricingRuleSerializer


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
