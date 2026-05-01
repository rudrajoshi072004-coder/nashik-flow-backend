from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q

from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsDriverRole
from apps.trip_events.models import TripEvent
from apps.users.models import User
from .models import DriverProfile
from .serializers import DriverAvailabilitySerializer, DriverProfileSerializer


class DriverViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsDriverRole]

    def get_object(self):
        """Resolve or lazily create the driver's profile.

        Routes like ``/drivers/me/bookings/`` are registered correctly; callers often
        mistake an application-level HTTP 404 (no profile row) for a missing endpoint.
        Auth/onboarding flows may create users with driver role before a profile exists.
        """
        user = self.request.user
        role = getattr(user, "role", None)
        profile = DriverProfile.objects.filter(user=user).first()
        if profile is None and role in (User.Role.DRIVER, User.Role.FLEET_DRIVER):
            profile, _ = DriverProfile.objects.get_or_create(user=user)
        return profile

    def _missing_profile_response(self):
        return success_response(
            {"detail": "Driver profile not found for this account."},
            message="Not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    def list(self, request):
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        return success_response(DriverProfileSerializer(profile).data)

    @action(detail=False, methods=["patch"], url_path="profile")
    def update_profile(self, request):
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        serializer = DriverProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, message="Driver profile updated")

    @action(detail=False, methods=["post"], url_path="availability")
    def availability(self, request):
        serializer = DriverAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        profile.is_online = serializer.validated_data["is_online"]
        profile.save(update_fields=["is_online", "updated_at"])
        return success_response(DriverProfileSerializer(profile).data, message="Availability updated")

    @action(detail=False, methods=["get"], url_path="bookings")
    def bookings(self, request):
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        offered_booking_ids = TripEvent.objects.filter(
            actor_driver=profile,
            event_type="ride_request_sent",
            booking__state=Booking.BookingState.SEARCHING_DRIVER,
            booking__driver__isnull=True,
        ).values_list("booking_id", flat=True)
        queryset = Booking.objects.filter(is_deleted=False).filter(
            Q(driver=profile) | Q(id__in=offered_booking_ids)
        ).distinct().order_by("-created_at")
        return success_response(BookingSerializer(queryset, many=True).data)

    @action(detail=False, methods=["get"], url_path="nearby-demand")
    def nearby_demand(self, request):
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        count = Booking.objects.filter(state=Booking.BookingState.SEARCHING_DRIVER, is_deleted=False).count()
        return success_response({"driver_online": profile.is_online, "searching_bookings_count": count})
