from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsDriverRole
from .models import DriverProfile
from .serializers import DriverAvailabilitySerializer, DriverProfileSerializer


class DriverViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsDriverRole]

    def get_object(self):
        return self.request.user.driver_profile

    def list(self, request):
        return success_response(DriverProfileSerializer(self.get_object()).data)

    @action(detail=False, methods=["patch"], url_path="profile")
    def update_profile(self, request):
        profile = self.get_object()
        serializer = DriverProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, message="Driver profile updated")

    @action(detail=False, methods=["post"], url_path="availability")
    def availability(self, request):
        serializer = DriverAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = self.get_object()
        profile.is_online = serializer.validated_data["is_online"]
        profile.save(update_fields=["is_online", "updated_at"])
        return success_response(DriverProfileSerializer(profile).data, message="Availability updated")

    @action(detail=False, methods=["get"], url_path="bookings")
    def bookings(self, request):
        profile = self.get_object()
        queryset = Booking.objects.filter(driver=profile, is_deleted=False).order_by("-created_at")
        return success_response(BookingSerializer(queryset, many=True).data)

    @action(detail=False, methods=["get"], url_path="nearby-demand")
    def nearby_demand(self, request):
        profile = self.get_object()
        count = Booking.objects.filter(state=Booking.BookingState.SEARCHING_DRIVER, is_deleted=False).count()
        return success_response({"driver_online": profile.is_online, "searching_bookings_count": count})
