from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api.responses import success_response
from apps.common.permissions.rbac import HasRole

from .models import FleetDriverMembership
from .serializers import AddFleetDriverSerializer, FleetOwnerProfileSerializer, UpdateMembershipSerializer
from .services import (
    add_driver_to_fleet,
    ensure_owner_profile,
    fleet_alerts,
    fleet_dashboard,
    fleet_earnings,
    fleet_trips,
    owner_active_memberships,
    serialize_membership,
)


class IsFleetOwnerRole(HasRole):
    allowed_roles = ("fleet_owner", "super_admin")


class OwnerMeView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response(FleetOwnerProfileSerializer(profile).data)

    def patch(self, request):
        profile = ensure_owner_profile(request.user)
        serializer = FleetOwnerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if serializer.validated_data.get("city"):
            request.user.city = serializer.validated_data["city"]
            request.user.save(update_fields=["city", "updated_at"])
        if serializer.validated_data.get("owner_full_name") and not request.user.first_name:
            request.user.first_name = serializer.validated_data["owner_full_name"][:150]
            request.user.save(update_fields=["first_name", "updated_at"])
        return success_response(FleetOwnerProfileSerializer(profile).data, message="Business details saved")


class OwnerDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response(fleet_dashboard(profile))


class OwnerAlertsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response({"alerts": fleet_alerts(profile)})


class OwnerDriversView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = [serialize_membership(m, today_start=today_start) for m in owner_active_memberships(profile)]
        return success_response({"drivers": rows})

    def post(self, request):
        profile = ensure_owner_profile(request.user)
        serializer = AddFleetDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = add_driver_to_fleet(owner=profile, **serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return success_response(
            serialize_membership(membership, today_start=today_start),
            message="Driver added to your fleet",
            status_code=status.HTTP_201_CREATED,
        )


class OwnerDriverDetailView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def _membership(self, request, membership_id):
        profile = ensure_owner_profile(request.user)
        return FleetDriverMembership.objects.filter(id=membership_id, owner=profile, is_deleted=False).select_related("driver", "driver__user").first()

    def get(self, request, membership_id):
        membership = self._membership(request, membership_id)
        if not membership:
            return Response({"detail": "Driver not found in your fleet."}, status=status.HTTP_404_NOT_FOUND)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        data = serialize_membership(membership, today_start=today_start)
        trips = fleet_trips(membership.owner, limit=20)
        data["recent_trips"] = [t for t in trips if t.get("driver_id") == data["driver_id"]][:10]
        return success_response(data)

    def patch(self, request, membership_id):
        membership = self._membership(request, membership_id)
        if not membership:
            return Response({"detail": "Driver not found in your fleet."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UpdateMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "status" in data:
            membership.status = data["status"]
            if data["status"] == FleetDriverMembership.Status.REMOVED:
                membership.is_deleted = True
        for field in ("driver_display_name", "vehicle_number", "vehicle_type", "notes"):
            if field in data:
                setattr(membership, field, data[field])
        membership.save()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return success_response(serialize_membership(membership, today_start=today_start), message="Driver updated")


class OwnerTripsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response({"trips": fleet_trips(profile)})


class OwnerEarningsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response(fleet_earnings(profile))
