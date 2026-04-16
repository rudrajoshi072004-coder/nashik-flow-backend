from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.audit_logs.models import AdminLog
from apps.audit_logs.serializers import AdminLogSerializer
from apps.bookings.models import Booking
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsAdminRole
from apps.drivers.models import DriverProfile
from apps.payouts.models import Payout
from apps.users.models import User


class AdminOpsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):
        data = {
            "users_total": User.objects.filter(is_deleted=False).count(),
            "drivers_total": DriverProfile.objects.filter(is_deleted=False).count(),
            "drivers_online": DriverProfile.objects.filter(is_online=True, is_deleted=False).count(),
            "bookings_total": Booking.objects.filter(is_deleted=False).count(),
            "bookings_active": Booking.objects.filter(
                state__in=[
                    Booking.BookingState.SEARCHING_DRIVER,
                    Booking.BookingState.DRIVER_ASSIGNED,
                    Booking.BookingState.IN_TRANSIT,
                ],
                is_deleted=False,
            ).count(),
            "payouts_requested": Payout.objects.filter(status=Payout.Status.REQUESTED).count(),
        }
        return success_response(data)


class AdminAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AdminLog.objects.select_related("actor")
    serializer_class = AdminLogSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ("module", "action")
    search_fields = ("request_id", "target_id", "actor__phone")
    ordering_fields = ("created_at",)
