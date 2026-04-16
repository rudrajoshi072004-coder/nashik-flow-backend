from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.bookings.models import Booking
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsAdminRole

from .serializers import DispatchReassignSerializer, DispatchTriggerSerializer
from .services import assign_driver_to_booking
from .tasks import dispatch_booking


class DispatchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @action(detail=False, methods=["post"], url_path="trigger")
    def trigger(self, request):
        serializer = DispatchTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking_id = str(serializer.validated_data["booking_id"])
        dispatch_booking.delay(booking_id)
        return success_response({"booking_id": booking_id}, message="Dispatch started")

    @action(detail=False, methods=["post"], url_path="reassign")
    def reassign(self, request):
        serializer = DispatchReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = Booking.objects.filter(id=serializer.validated_data["booking_id"]).first()
        if not booking:
            return success_response(
                {"detail": "Booking not found"},
                message="Not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        booking.driver = None
        booking.state = Booking.BookingState.SEARCHING_DRIVER
        booking.save(update_fields=["driver", "state", "updated_at"])
        driver = assign_driver_to_booking(booking=booking, timeout_seconds=serializer.validated_data["timeout_seconds"])
        return success_response(
            {
                "booking_id": str(booking.id),
                "driver_id": str(driver.id) if driver else None,
                "state": booking.state,
            },
            message="Reassignment processed",
        )
