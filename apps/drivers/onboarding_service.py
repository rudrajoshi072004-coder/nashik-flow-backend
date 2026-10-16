from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.driver_documents.models import DriverDocument
from apps.drivers.models import DriverProfile
from apps.vehicle_categories.models import VehicleCategory
from apps.vehicles.models import Vehicle


VEHICLE_TYPE_TO_CATEGORY = {
    "2w": "2-wheeler",
    "3w": "3-wheeler",
    "truck": "truck",
    "part_load": "pickup truck",
}

TRUCK_BODY_TO_CATEGORY = {
    "7ft_075t": "mini tempo",
    "8ft_125t": "pickup truck",
}

DOCUMENT_TYPE_MAP = {
    "owner_aadhaar_front": DriverDocument.DocumentType.AADHAAR_FRONT,
    "owner_aadhaar_back": DriverDocument.DocumentType.AADHAAR_BACK,
    "owner_pan_front": DriverDocument.DocumentType.PAN_FRONT,
    "owner_pan_back": DriverDocument.DocumentType.PAN_BACK,
    "owner_selfie": DriverDocument.DocumentType.OWNER_SELFIE,
    "vehicle_rc": DriverDocument.DocumentType.RC,
    "license_front": DriverDocument.DocumentType.LICENSE_FRONT,
    "license_back": DriverDocument.DocumentType.LICENSE_BACK,
}


def _resolve_category(data: dict) -> VehicleCategory:
    vehicle_type = (data.get("vehicle_type") or "").strip().lower()
    truck_body = (data.get("truck_body_detail") or "").strip().lower()
    category_name = TRUCK_BODY_TO_CATEGORY.get(truck_body) or VEHICLE_TYPE_TO_CATEGORY.get(vehicle_type, "3-wheeler")
    category = VehicleCategory.objects.filter(name__iexact=category_name, is_deleted=False).first()
    if category:
        return category
    return VehicleCategory.objects.filter(is_deleted=False).order_by("priority_order").first()


def _upsert_document(profile: DriverProfile, doc_key: str, file_uri: str | None) -> None:
    if not file_uri or not str(file_uri).strip():
        return
    doc_type = DOCUMENT_TYPE_MAP.get(doc_key)
    if not doc_type:
        return
    DriverDocument.objects.update_or_create(
        driver=profile,
        document_type=doc_type,
        defaults={
            "file_key": str(file_uri).strip()[:255],
            "status": DriverDocument.Status.PENDING,
        },
    )


@transaction.atomic
def submit_driver_onboarding(user, data: dict) -> DriverProfile:
    user_model = get_user_model()

    if user.role not in (user_model.Role.DRIVER, user_model.Role.FLEET_DRIVER):
        user.role = user_model.Role.DRIVER
        user.save(update_fields=["role", "updated_at"])

    owner_name = (data.get("owner_name") or "").strip()
    operation_city = (data.get("operation_city") or "").strip()
    driver_name = (data.get("driver_name") or "").strip()
    driver_phone = (data.get("driver_phone") or "").strip()

    user_updates: list[str] = []
    if owner_name:
        user.first_name = owner_name[:150]
        user_updates.append("first_name")
    if operation_city:
        user.city = operation_city[:64]
        user_updates.append("city")
    if user_updates:
        user_updates.append("updated_at")
        user.save(update_fields=user_updates)

    profile, _ = DriverProfile.objects.get_or_create(user=user)

    will_drive = data.get("will_drive_vehicle")
    if will_drive in ("yes", "no", True, False):
        profile.will_drive_vehicle = will_drive in ("yes", True)

    profile.owner_name = owner_name[:128]
    profile.driver_name = driver_name[:128]
    profile.driver_phone = driver_phone[:20]
    profile.vehicle_number = (data.get("vehicle_number") or "").strip()[:32]
    profile.vehicle_type = (data.get("vehicle_type") or "").strip()[:32]
    profile.vehicle_body_type = (data.get("vehicle_body_type") or "").strip()[:32]
    profile.truck_body_detail = (data.get("truck_body_detail") or "").strip()[:32]
    profile.three_wheeler_body_type = (data.get("three_wheeler_body_type") or "").strip()[:32]
    profile.fuel_type = (data.get("fuel_type") or "").strip()[:16]
    profile.operation_city = operation_city[:64]
    # 2W cannot do outstation trips; 3W and 4W can opt-in/out
    if profile.vehicle_type == "2w":
        profile.accepts_outstation = False
    elif "accepts_outstation" in data:
        profile.accepts_outstation = bool(data["accepts_outstation"])
    else:
        profile.accepts_outstation = True
    profile.onboarding_completed = True
    profile.kyc_status = DriverProfile.KYCStatus.PENDING
    profile.onboarding_submitted_at = timezone.now()
    profile.save()

    documents = data.get("documents") or {}
    if isinstance(documents, dict):
        for doc_key, file_uri in documents.items():
            _upsert_document(profile, str(doc_key), file_uri if isinstance(file_uri, str) else None)

    vehicle_number = profile.vehicle_number
    if vehicle_number:
        category = _resolve_category(data)
        if category:
            Vehicle.objects.update_or_create(
                registration_number=vehicle_number,
                defaults={
                    "driver": profile,
                    "category": category,
                    "status": Vehicle.Status.ACTIVE,
                    "brand": profile.vehicle_type or "",
                    "model_name": profile.truck_body_detail or profile.three_wheeler_body_type or profile.vehicle_body_type or "",
                },
            )

    return profile
