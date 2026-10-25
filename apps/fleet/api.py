from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api.idempotency import (
    check_and_set_idempotency_lock,
    generate_dedupe_fingerprint,
    get_cached_idempotency_response,
    get_idempotency_key,
    release_idempotency_lock,
    store_idempotency_response,
)
from apps.common.api.responses import success_response
from apps.common.api.throttling import FleetAddDriverRateThrottle, FleetOpsRateThrottle
from apps.common.permissions.rbac import HasRole

from .models import FleetDriverMembership, FleetOwnerDocument, FleetOwnerProfile
from .serializers import (
    AddFleetDriverSerializer,
    FleetAnalyticsFilterSerializer,
    FleetDocumentUploadSerializer,
    FleetOwnerDocumentSerializer,
    FleetOwnerProfileSerializer,
    OwnerKycSubmitSerializer,
    UpdateMembershipSerializer,
)
from .services import (
    add_driver_to_fleet,
    ensure_owner_profile,
    fleet_alerts,
    fleet_analytics,
    fleet_dashboard,
    fleet_earnings,
    fleet_trips,
    owner_active_memberships,
    serialize_membership,
    serialize_memberships_batch,
    submit_owner_kyc,
    upload_fleet_document,
)


class IsFleetOwnerRole(HasRole):
    allowed_roles = ("fleet_owner", "super_admin")


class OwnerMeView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response(FleetOwnerProfileSerializer(profile).data)

    def patch(self, request):
        profile = ensure_owner_profile(request.user)

        idempotency_key = get_idempotency_key(request)
        if not idempotency_key:
            fingerprint = generate_dedupe_fingerprint(
                user_id=request.user.id,
                path=request.path,
                payload=request.data,
            )
            idempotency_key = f"auto:fleet_me:{fingerprint}"

        cached = get_cached_idempotency_response(idempotency_key)
        if cached is not None:
            return Response(cached["data"], status=cached["status"], headers={"X-Cache-Lookup": "HIT"})

        if not check_and_set_idempotency_lock(idempotency_key):
            return success_response(
                {"detail": "Request currently processing, please wait."},
                message="Processing",
                status_code=status.HTTP_409_CONFLICT,
            )

        try:
            with transaction.atomic():
                serializer = FleetOwnerProfileSerializer(profile, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                if serializer.validated_data.get("city"):
                    request.user.city = serializer.validated_data["city"]
                    request.user.save(update_fields=["city", "updated_at"])
                if serializer.validated_data.get("owner_full_name") and not request.user.first_name:
                    request.user.first_name = serializer.validated_data["owner_full_name"][:150]
                    request.user.save(update_fields=["first_name", "updated_at"])

            resp = success_response(FleetOwnerProfileSerializer(profile).data, message="Business details saved")
            store_idempotency_response(idempotency_key, resp.data, resp.status_code, expiry=60)
            return resp
        except Exception:
            release_idempotency_lock(idempotency_key)
            raise


class OwnerDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response(fleet_dashboard(profile))


class OwnerAlertsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response({"alerts": fleet_alerts(profile)})


class OwnerDriversView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]

    def get_throttles(self):
        if self.request.method == "POST":
            return [FleetAddDriverRateThrottle()]
        return [FleetOpsRateThrottle()]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # High-traffic O(1) batch query: 2 SQL queries total instead of 3N queries
        rows = serialize_memberships_batch(owner_active_memberships(profile), today_start=today_start)
        return success_response({"drivers": rows})

    def post(self, request):
        profile = ensure_owner_profile(request.user)
        serializer = AddFleetDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = get_idempotency_key(request)
        if not idempotency_key:
            fingerprint = generate_dedupe_fingerprint(
                user_id=request.user.id,
                path=request.path,
                payload=serializer.validated_data,
            )
            idempotency_key = f"auto:fleet_add:{fingerprint}"

        cached = get_cached_idempotency_response(idempotency_key)
        if cached is not None:
            return Response(cached["data"], status=cached["status"], headers={"X-Cache-Lookup": "HIT"})

        if not check_and_set_idempotency_lock(idempotency_key):
            return success_response(
                {"detail": "Request currently processing, please wait."},
                message="Processing",
                status_code=status.HTTP_409_CONFLICT,
            )

        try:
            membership = add_driver_to_fleet(owner=profile, **serializer.validated_data)
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            data = serialize_membership(membership, today_start=today_start)
            resp = success_response(
                data,
                message="Driver added to your fleet",
                status_code=status.HTTP_201_CREATED,
            )
            store_idempotency_response(idempotency_key, resp.data, resp.status_code, expiry=60)
            return resp
        except ValueError as exc:
            release_idempotency_lock(idempotency_key)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            release_idempotency_lock(idempotency_key)
            raise


class OwnerDriverDetailView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def _membership(self, request, membership_id):
        profile = ensure_owner_profile(request.user)
        return (
            FleetDriverMembership.objects.filter(id=membership_id, owner=profile, is_deleted=False)
            .select_related("driver", "driver__user", "driver__live_location")
            .first()
        )

    def get(self, request, membership_id):
        membership = self._membership(request, membership_id)
        if not membership:
            return Response({"detail": "Driver not found in your fleet."}, status=status.HTTP_404_NOT_FOUND)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        data = serialize_membership(membership, today_start=today_start)
        # Fetch this specific driver's actual recent trips (filtered in SQL, not just in-memory slice of 20)
        data["recent_trips"] = fleet_trips(membership.owner, limit=10, driver_id=str(membership.driver_id))
        return success_response(data)

    def patch(self, request, membership_id):
        membership = self._membership(request, membership_id)
        if not membership:
            return Response({"detail": "Driver not found in your fleet."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UpdateMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        idempotency_key = get_idempotency_key(request)
        if not idempotency_key:
            fingerprint = generate_dedupe_fingerprint(
                user_id=request.user.id,
                path=request.path,
                payload=data,
            )
            idempotency_key = f"auto:fleet_update:{membership_id}:{fingerprint}"

        cached = get_cached_idempotency_response(idempotency_key)
        if cached is not None:
            return Response(cached["data"], status=cached["status"], headers={"X-Cache-Lookup": "HIT"})

        if not check_and_set_idempotency_lock(idempotency_key):
            return success_response(
                {"detail": "Request currently processing, please wait."},
                message="Processing",
                status_code=status.HTTP_409_CONFLICT,
            )

        try:
            with transaction.atomic():
                if "status" in data:
                    membership.status = data["status"]
                    if data["status"] == FleetDriverMembership.Status.REMOVED:
                        membership.is_deleted = True
                for field in ("driver_display_name", "vehicle_number", "vehicle_type", "notes"):
                    if field in data:
                        setattr(membership, field, data[field])
                membership.save()

            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            resp = success_response(
                serialize_membership(membership, today_start=today_start),
                message="Driver updated",
            )
            store_idempotency_response(idempotency_key, resp.data, resp.status_code, expiry=60)
            return resp
        except Exception:
            release_idempotency_lock(idempotency_key)
            raise


class OwnerTripsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response({"trips": fleet_trips(profile)})


class OwnerEarningsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        return success_response(fleet_earnings(profile))


class OwnerDocumentsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def get(self, request):
        profile = ensure_owner_profile(request.user)
        docs = FleetOwnerDocument.objects.filter(owner=profile, is_deleted=False).order_by("created_at")
        return success_response({
            "kyc_status": profile.kyc_status,
            "kyc_submitted_at": profile.kyc_submitted_at,
            "kyc_verified_at": profile.kyc_verified_at,
            "kyc_rejection_reason": profile.kyc_rejection_reason,
            "documents": FleetOwnerDocumentSerializer(docs, many=True).data,
        })

    def post(self, request):
        """Submit owner business details and document links for KYC review."""
        profile = ensure_owner_profile(request.user)
        serializer = OwnerKycSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_profile = submit_owner_kyc(profile, serializer.validated_data)
        return success_response(
            FleetOwnerProfileSerializer(updated_profile).data,
            message="KYC application submitted for review.",
            status_code=status.HTTP_200_OK,
        )


class FleetDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def post(self, request):
        """Upload a file or document URL for fleet owner KYC or a fleet driver's vehicle."""
        profile = ensure_owner_profile(request.user)
        serializer = FleetDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        file_obj = request.FILES.get("file") or data.get("file")
        try:
            result = upload_fleet_document(
                owner=profile,
                document_type=data["document_type"],
                file_obj=file_obj,
                file_url=data.get("file_url", ""),
                document_number=data.get("document_number", ""),
                target=data.get("target", "owner"),
                driver_id=data.get("driver_id"),
            )
            return success_response(result, message="Document uploaded successfully", status_code=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class OwnerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsFleetOwnerRole]
    throttle_classes = [FleetOpsRateThrottle]

    def get(self, request):
        """Real-time filtered fleet KPIs and driver leaderboard for owner app."""
        profile = ensure_owner_profile(request.user)
        filter_serializer = FleetAnalyticsFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        data = filter_serializer.validated_data

        analytics_data = fleet_analytics(
            profile,
            period=data.get("period", "today"),
            category=data.get("category", "all"),
            driver_id=data.get("driver_id"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )
        return success_response(analytics_data)
