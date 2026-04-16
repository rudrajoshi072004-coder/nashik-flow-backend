from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole
from .models import SupportTicket
from .serializers import SupportTicketSerializer


class SupportTicketViewSet(viewsets.ModelViewSet):
    queryset = SupportTicket.objects.filter(is_deleted=False).select_related("created_by", "assigned_to", "booking")
    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("status", "priority", "assigned_to")
    search_fields = ("id", "subject", "created_by__phone", "assigned_to__phone")
    ordering_fields = ("created_at", "priority")

    def get_queryset(self):
        user = self.request.user
        if user.role in {"customer", "driver", "fleet_driver"}:
            return self.queryset.filter(created_by=user)
        return self.queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_permissions(self):
        if self.action in {"destroy"}:
            return [IsAdminRole()]
        return [IsAuthenticated()]
