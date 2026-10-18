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

    def get_permissions(self):
        if self.action in {"decline_offer"}:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminRole()]

    @action(detail=False, methods=["post"], url_path="decline-offer")
    def decline_offer(self, request):
        from apps.drivers.models import DriverProfile
        from .services import handle_driver_declined_offer

        profile = getattr(request.user, "driver_profile", None) or DriverProfile.objects.filter(
            user=request.user, is_deleted=False
        ).first()
        if not profile:
            return success_response(
                {"detail": "Driver profile required."},
                message="Unauthorized",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        booking_id = request.data.get("booking_id")
        if not booking_id:
            return success_response(
                {"detail": "booking_id is required."},
                message="Bad Request",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        booking = Booking.objects.filter(id=booking_id).first()
        if not booking:
            return success_response(
                {"detail": "Booking not found"},
                message="Not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        handle_driver_declined_offer(booking=booking, driver_profile=profile)
        return success_response({"booking_id": str(booking.id), "declined": True}, message="Offer declined")

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
