"""Additive admin portal API — mount at /api/v1/admin/portal/ without changing existing routes."""
import re
from decimal import Decimal

from django.apps import apps
from django.db.models import Count, Prefetch, Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_portal.permissions import IsPortalAdmin
from apps.bookings.models import Booking
from apps.drivers.profile_service import ensure_driver_profile

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_VEHICLE_TYPE_LABELS = {
    "2w": "2-wheeler",
    "3w": "3-wheeler",
    "truck": "Truck",
    "part_load": "Part load",
}


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


def _looks_like_uuid(value: str) -> bool:
    return bool(value and _UUID_RE.match(str(value).strip()))


def _looks_like_phone(value: str) -> bool:
    if not value or _looks_like_uuid(value):
        return False
    digits = re.sub(r"\D", "", str(value))
    return 10 <= len(digits) <= 15


def _format_phone_display(value: str) -> str:
    if not _looks_like_phone(value):
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if value.startswith("+"):
        return value
    return f"+{digits}"


def _clean_text(value: str) -> str:
    text = (value or "").strip()
    if not text or _looks_like_uuid(text):
        return ""
    return text


def _resolve_display_name(profile, user, account_phone: str, driver_phone: str, user_name: str) -> str:
    for candidate in (profile.driver_name, profile.owner_name, user_name):
        cleaned = _clean_text(candidate)
        if cleaned:
            return cleaned

    for candidate in (driver_phone, account_phone):
        formatted = _format_phone_display(candidate)
        if formatted:
            return formatted

    return f"Driver {str(profile.pk)[-6:].upper()}"


def _resolve_contact_phone(account_phone: str, driver_phone: str) -> str:
    for candidate in (driver_phone, account_phone):
        formatted = _format_phone_display(candidate)
        if formatted:
            return formatted
    return ""


def _resolve_vehicle_type_label(raw: str, category_names: dict[str, str]) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if _looks_like_uuid(value):
        return category_names.get(value.lower(), "")
    return _VEHICLE_TYPE_LABELS.get(value.lower(), value.replace("_", " ").title())


def _active_vehicle(profile):
    vehicles = getattr(profile, "vehicles", None)
    if vehicles is None:
        return None
    for vehicle in vehicles.all():
        if getattr(vehicle, "is_deleted", False):
            continue
        return vehicle
    return None


def _serialize_driver_profile(profile, category_names: dict[str, str] | None = None) -> dict:
    category_names = category_names or {}
    user = profile.user
    account_phone = getattr(user, "phone", "") if user else ""
    driver_phone = (profile.driver_phone or "").strip()
    user_name = ""
    if user:
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    display_name = _resolve_display_name(profile, user, account_phone, driver_phone, user_name)
    contact_phone = _resolve_contact_phone(account_phone, driver_phone)

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
    vehicle = _active_vehicle(profile)
    vehicle_number = _clean_text(profile.vehicle_number) or (
        getattr(vehicle, "registration_number", "") if vehicle else ""
    )
    vehicle_type_raw = profile.vehicle_type or ""
    vehicle_type_label = _resolve_vehicle_type_label(vehicle_type_raw, category_names)
    if not vehicle_type_label and vehicle and getattr(vehicle, "category_id", None):
        category = getattr(vehicle, "category", None)
        if category is not None:
            vehicle_type_label = category.name

    profile_id = str(profile.pk)

    return {
        "id": profile_id,
        "display_id": f"DRV-{profile_id[-6:].upper()}",
        "user_id": str(user.pk) if user else None,
        "name": display_name,
        "owner_name": _clean_text(profile.owner_name),
        "phone": contact_phone,
        "account_phone": _format_phone_display(account_phone) or "",
        "driver_phone": _format_phone_display(driver_phone) or "",
        "email": getattr(user, "email", "") or "" if user else "",
        "city": profile.operation_city or getattr(user, "city", "") if user else "",
        "status": "online" if profile.is_online else "offline",
        "kyc_status": profile.kyc_status,
        "onboarding_completed": profile.onboarding_completed,
        "registration_status": _registration_status(profile),
        "registered_at": profile.created_at.isoformat() if profile.created_at else None,
        "vehicle_category": vehicle_type_label or "",
        "vehicle_type": vehicle_type_label or "",
        "vehicle_number": vehicle_number,
        "vehicle_body_type": vehicle_body,
        "fuel_type": profile.fuel_type or "",
        "will_drive_vehicle": profile.will_drive_vehicle,
        "rating": str(profile.rating_avg or "0"),
        "total_trips": profile.total_trips or 0,
        "wallet_balance": wallet_balance,
        "joined_at": user.date_joined.isoformat() if user and user.date_joined else None,
        "documents": documents,
        "vehicle_details": {
            "make": vehicle_type_label or "—",
            "model": vehicle_body or "—",
            "year": str(getattr(vehicle, "manufacture_year", "") or "—") if vehicle else "—",
            "color": "—",
            "plate": vehicle_number or "—",
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
        DriverProfile = apps.get_model("drivers", "DriverProfile")
        DriverDocument = apps.get_model("driver_documents", "DriverDocument")
        VehicleCategory = apps.get_model("vehicle_categories", "VehicleCategory")

        profiles = (
            DriverProfile.objects.select_related("user", "wallet")
            .prefetch_related(
                Prefetch(
                    "documents",
                    queryset=DriverDocument.objects.filter(is_deleted=False),
                ),
                Prefetch(
                    "vehicles",
                    queryset=apps.get_model("vehicles", "Vehicle").objects.filter(is_deleted=False).select_related(
                        "category"
                    ),
                ),
            )
            .filter(is_deleted=False)
            .order_by("-created_at")[:500]
        )

        category_ids: set[str] = set()
        for profile in profiles:
            raw_type = (profile.vehicle_type or "").strip()
            if _looks_like_uuid(raw_type):
                category_ids.add(raw_type.lower())

        category_names = {
            str(category.pk).lower(): category.name
            for category in VehicleCategory.objects.filter(pk__in=category_ids, is_deleted=False)
        }

        rows = [_serialize_driver_profile(profile, category_names) for profile in profiles]
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


class PortalDriverDetailView(APIView):
    """Approve/reject driver KYC from admin panel."""

    permission_classes = [IsPortalAdmin]

    def patch(self, request, driver_id):
        from apps.drivers.models import DriverProfile

        try:
            profile = DriverProfile.objects.select_related("user", "wallet").get(pk=driver_id, is_deleted=False)
        except DriverProfile.DoesNotExist:
            return _fail("Driver not found", code=status.HTTP_404_NOT_FOUND)

        payload = request.data if isinstance(request.data, dict) else {}
        allowed = {"kyc_status", "is_online"}
        changed = []
        for key in allowed:
            if key not in payload:
                continue
            value = payload[key]
            if key == "kyc_status":
                valid = {
                    DriverProfile.KYCStatus.PENDING,
                    DriverProfile.KYCStatus.APPROVED,
                    DriverProfile.KYCStatus.REJECTED,
                }
                if value not in valid:
                    return _fail("Invalid kyc_status")
            setattr(profile, key, value)
            changed.append(key)

        if changed:
            profile.save(update_fields=[*changed, "updated_at"])

        VehicleCategory = apps.get_model("vehicle_categories", "VehicleCategory")
        category_names = {}
        raw_type = (profile.vehicle_type or "").strip()
        if _looks_like_uuid(raw_type):
            cat = VehicleCategory.objects.filter(pk=raw_type, is_deleted=False).first()
            if cat:
                category_names[str(cat.pk).lower()] = cat.name

        row = _serialize_driver_profile(profile, category_names)
        return _ok(row, message="Driver updated")
