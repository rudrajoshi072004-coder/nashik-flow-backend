from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole
from .models import FareRule
from .serializers import FareRuleSerializer


class FareRuleViewSet(viewsets.ModelViewSet):
    queryset = FareRule.objects.filter(is_deleted=False).select_related("pricing_rule")
    serializer_class = FareRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("rule_type", "active", "pricing_rule")
    search_fields = ("rule_type", "pricing_rule__name")
    ordering_fields = ("created_at", "amount", "percentage")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsAdminRole()]
