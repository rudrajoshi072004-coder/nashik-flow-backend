from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from apps.bookings.models import Booking
from apps.bookings.querysets import bookings_queryset_for_driver_user
from apps.bookings.serializers import BookingSerializer
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsDriverRoleOrProfile
from apps.users.models import User
from .models import DriverProfile
from .onboarding_serializers import DriverOnboardingSubmitSerializer
from .onboarding_service import submit_driver_onboarding
from .serializers import DriverAvailabilitySerializer, DriverLocationSerializer, DriverProfileSerializer


class DriverViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsDriverRoleOrProfile]

    def get_permissions(self):
        if self.action in {"submit_onboarding", "list", "update_profile"}:
            return [IsAuthenticated()]
        return super().get_permissions()

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

    @action(detail=False, methods=["post"], url_path="onboarding")
    def submit_onboarding(self, request):
        serializer = DriverOnboardingSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = submit_driver_onboarding(request.user, serializer.validated_data)
        return success_response(
            DriverProfileSerializer(profile).data,
            message="Driver onboarding submitted",
            status_code=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["patch"], url_path="profile")
    def update_profile(self, request):
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        serializer = DriverProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, message="Driver profile updated")

    @action(detail=False, methods=["post"], url_path="location")
    def post_location(self, request):
        """REST fallback when WebSocket location events are delayed (common on mobile)."""
        serializer = DriverLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        if not profile.is_online:
            return success_response(
                {"detail": "Driver is offline; go online to publish location."},
                message="Offline",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        from apps.tracking.services import update_driver_location

        data = serializer.validated_data
        update_driver_location(
            driver_profile=profile,
            lat=float(data["lat"]),
            lng=float(data["lng"]),
            heading=float(data.get("heading") or 0),
            speed_kmph=float(data.get("speed_kmph") or 0),
            accuracy_m=float(data.get("accuracy_m") or 0),
            booking_id=str(data["booking_id"]) if data.get("booking_id") else None,
        )
        return success_response({"ok": True}, message="Location updated")

    @action(detail=False, methods=["post"], url_path="availability")
    def availability(self, request):
        serializer = DriverAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        going_online = serializer.validated_data["is_online"]
        profile.is_online = going_online
        profile.save(update_fields=["is_online", "updated_at"])
        if not going_online:
            from apps.tracking.redis_geo import remove_driver_geo

            remove_driver_geo(str(profile.id))
        if going_online:
            data = serializer.validated_data
            lat = data.get("lat")
            lng = data.get("lng")
            if lat is not None and lng is not None:
                from apps.tracking.services import update_driver_location

                update_driver_location(
                    driver_profile=profile,
                    lat=float(lat),
                    lng=float(lng),
                    heading=float(data.get("heading") or 0),
                    speed_kmph=float(data.get("speed_kmph") or 0),
                    accuracy_m=float(data.get("accuracy_m") or 0),
                    booking_id=None,
                )
        return success_response(DriverProfileSerializer(profile).data, message="Availability updated")

    @action(detail=False, methods=["get"], url_path="bookings")
    def bookings(self, request):
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        queryset = bookings_queryset_for_driver_user(request.user)
        return success_response(BookingSerializer(queryset, many=True).data)

    @action(detail=False, methods=["get"], url_path="nearby-demand")
    def nearby_demand(self, request):
        profile = self.get_object()
        if not profile:
            return self._missing_profile_response()
        count = Booking.objects.filter(state=Booking.BookingState.SEARCHING_DRIVER, is_deleted=False).count()
        return success_response({"driver_online": profile.is_online, "searching_bookings_count": count})

    @action(detail=False, methods=["post"], url_path="fcm-token")
    def fcm_token(self, request):
        token = request.data.get("fcm_token")
        if not token:
            return success_response(
                {"detail": "fcm_token required"},
                message="Bad request",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        user.fcm_token = str(token)
        user.save(update_fields=["fcm_token", "updated_at"])
        return success_response({"status": "ok"}, message="FCM token saved")
