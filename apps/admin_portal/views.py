"""Additive admin portal API — mount at /api/v1/admin/portal/ without changing existing routes."""
from decimal import Decimal

from django.apps import apps
from django.db.models import Count, Prefetch, Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_portal.permissions import IsPortalAdmin
from apps.bookings.models import Booking
from apps.drivers.profile_service import ensure_driver_profile


def _ok(data, message="OK"):
    return Response({"success": True, "message": message, "data": data, "errors": None})


def _fail(message, errors=None, code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {"success": False, "message": message, "data": None, "errors": errors or {}},
        status=code,
    )


ACTIVE_BOOKING_STATES = (
    Booking.BookingState.SEARCHING_DRIVER,
    Booking.BookingState.DRIVER_ASSIGNED,
    Booking.BookingState.DRIVER_ACCEPTED,
    Booking.BookingState.DRIVER_ARRIVING,
    Booking.BookingState.DRIVER_ARRIVED,
    Booking.BookingState.PICKUP_OTP_PENDING,
    Booking.BookingState.TRIP_STARTED,
    Booking.BookingState.IN_TRANSIT,
    Booking.BookingState.NEARING_DROP,
    Booking.BookingState.PAYMENT_PENDING,
)


def _doc_status_label(raw: str) -> str:
    mapping = {
        "approved": "Verified",
        "pending": "Pending",
        "rejected": "Rejected",
    }
    return mapping.get(str(raw).lower(), "Pending")


def _registration_status(profile) -> str:
    if not profile.onboarding_completed:
        return "new"
    if profile.kyc_status == "approved":
        return "approved"
    if profile.kyc_status == "rejected":
        return "rejected"
    return "kyc_pending"


def _serialize_driver_profile(profile) -> dict:
    user = profile.user
    account_phone = getattr(user, "phone", "") if user else ""
    driver_phone = (profile.driver_phone or "").strip()
    contact_phone = driver_phone or account_phone
    user_name = ""
    if user:
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    wallet_balance = "0"
    wallet = getattr(profile, "wallet", None)
    if wallet is not None:
        wallet_balance = str(getattr(wallet, "current_balance", 0) or 0)

    documents = []
    for doc in profile.documents.all():
        if getattr(doc, "is_deleted", False):
            continue
        documents.append(
            {
                "type": doc.get_document_type_display() if hasattr(doc, "get_document_type_display") else doc.document_type,
                "number": doc.file_key or "—",
                "status": _doc_status_label(doc.status),
                "expiry": "—",
            }
        )

    vehicle_body = profile.vehicle_body_type or profile.three_wheeler_body_type or profile.truck_body_detail or ""

    return {
        "id": str(profile.pk),
        "user_id": str(user.pk) if user else None,
        "name": profile.driver_name or profile.owner_name or user_name or account_phone,
        "owner_name": profile.owner_name or "",
        "phone": contact_phone,
        "account_phone": account_phone,
        "driver_phone": driver_phone,
        "email": getattr(user, "email", "") or "" if user else "",
        "city": profile.operation_city or getattr(user, "city", "") if user else "",
        "status": "online" if profile.is_online else "offline",
        "kyc_status": profile.kyc_status,
        "onboarding_completed": profile.onboarding_completed,
        "registration_status": _registration_status(profile),
        "registered_at": profile.created_at.isoformat() if profile.created_at else None,
        "vehicle_category": profile.vehicle_type or "",
        "vehicle_type": profile.vehicle_type or "",
        "vehicle_number": profile.vehicle_number or "",
        "vehicle_body_type": vehicle_body,
        "fuel_type": profile.fuel_type or "",
        "will_drive_vehicle": profile.will_drive_vehicle,
        "rating": str(profile.rating_avg or "0"),
        "total_trips": profile.total_trips or 0,
        "wallet_balance": wallet_balance,
        "joined_at": user.date_joined.isoformat() if user and user.date_joined else None,
        "documents": documents,
        "vehicle_details": {
            "make": profile.vehicle_type or "—",
            "model": vehicle_body or "—",
            "year": "—",
            "color": "—",
            "plate": profile.vehicle_number or "—",
            "insurance": next(
                (d["status"] for d in documents if "insurance" in d["type"].lower()),
                "—",
            ),
            "fitness": next(
                (d["status"] for d in documents if "rc" in d["type"].lower() or "registration" in d["type"].lower()),
                "—",
            ),
        },
    }


class PortalOverviewView(APIView):
    """Dashboard KPIs for admin panel."""

    permission_classes = [IsPortalAdmin]

    def get(self, request):
        BookingModel = apps.get_model("bookings", "Booking")
        VehicleCategory = apps.get_model("vehicle_categories", "VehicleCategory")
        User = apps.get_model("users", "User")

        qs = BookingModel.objects.filter(is_deleted=False)
        completed = qs.filter(state=Booking.BookingState.COMPLETED).count()
        cancelled = qs.filter(state__icontains="cancel").count()
        active = qs.filter(state__in=ACTIVE_BOOKING_STATES).count()
        revenue = (
            qs.filter(state=Booking.BookingState.COMPLETED).aggregate(total=Sum("estimated_fare"))["total"]
            or Decimal("0")
        )

        data = {
            "total_bookings": qs.count(),
            "active_bookings": active,
            "completed_bookings": completed,
            "cancelled_bookings": cancelled,
            "estimated_revenue": str(revenue),
            "vehicle_types_active": VehicleCategory.objects.filter(active=True, is_deleted=False).count(),
            "total_customers": User.objects.filter(role=User.Role.CUSTOMER, is_deleted=False).count(),
            "total_drivers": User.objects.filter(
                role__in=[User.Role.DRIVER, User.Role.FLEET_DRIVER],
                is_deleted=False,
            ).count(),
        }
        return _ok(data)


class PortalDriversView(APIView):
    permission_classes = [IsPortalAdmin]

    def get(self, request):
        User = apps.get_model("users", "User")
        DriverProfile = apps.get_model("drivers", "DriverProfile")
        DriverDocument = apps.get_model("driver_documents", "DriverDocument")

        driver_users = (
            User.objects.filter(
                role__in=[User.Role.DRIVER, User.Role.FLEET_DRIVER],
                is_deleted=False,
            )
            .select_related("driver_profile", "driver_profile__wallet")
            .order_by("-date_joined")[:500]
        )

        profile_ids: list = []
        for user in driver_users:
            profile = getattr(user, "driver_profile", None)
            if profile is None or profile.is_deleted:
                profile = ensure_driver_profile(user)
            if profile and not profile.is_deleted:
                profile_ids.append(profile.pk)

        profiles = (
            DriverProfile.objects.select_related("user", "wallet")
            .prefetch_related(
                Prefetch(
                    "documents",
                    queryset=DriverDocument.objects.filter(is_deleted=False),
                )
            )
            .filter(pk__in=profile_ids, is_deleted=False)
            .order_by("-created_at")
        )

        rows = [_serialize_driver_profile(profile) for profile in profiles]
        return _ok({"count": len(rows), "results": rows})


class PortalCustomersView(APIView):
    permission_classes = [IsPortalAdmin]

    def get(self, request):
        User = apps.get_model("users", "User")
        BookingModel = apps.get_model("bookings", "Booking")
        rows = []
        customers = User.objects.filter(role=User.Role.CUSTOMER, is_deleted=False).order_by("-date_joined")[:200]
        booking_counts = dict(
            BookingModel.objects.filter(is_deleted=False)
            .values("customer_id")
            .annotate(c=Count("id"))
            .values_list("customer_id", "c")
        )
        for user in customers:
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            rows.append(
                {
                    "id": str(user.pk),
                    "phone": user.phone,
                    "name": name or user.phone,
                    "city": user.city,
                    "bookings_count": booking_counts.get(user.pk, 0),
                }
            )
        return _ok({"count": len(rows), "results": rows})


class PortalSettingsView(APIView):
    """Read/write platform settings (AppSetting key-value store)."""

    permission_classes = [IsPortalAdmin]

    def get(self, request):
        AppSetting = apps.get_model("app_settings", "AppSetting")
        settings = {row.key: row.value for row in AppSetting.objects.all()}
        return _ok(settings)

    def patch(self, request):
        AppSetting = apps.get_model("app_settings", "AppSetting")
        payload = request.data if isinstance(request.data, dict) else {}
        for key, value in payload.items():
            AppSetting.objects.update_or_create(key=key, defaults={"value": value})
        settings = {row.key: row.value for row in AppSetting.objects.all()}
        return _ok(settings, message="Settings updated")


class PortalAuditLogsView(APIView):
    """Expose audit logs for admin System Logs page."""

    permission_classes = [IsPortalAdmin]

    def get(self, request):
        AdminLog = apps.get_model("audit_logs", "AdminLog")
        rows = []
        for log in AdminLog.objects.order_by("-created_at")[:500]:
            rows.append(
                {
                    "id": str(log.pk),
                    "action": log.action,
                    "actor": str(log.actor_id or ""),
                    "detail": log.metadata if isinstance(log.metadata, str) else str(log.metadata or ""),
                    "module": log.module,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
            )
        return _ok({"count": len(rows), "results": rows})
