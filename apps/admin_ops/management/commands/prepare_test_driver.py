from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from apps.drivers.models import DriverProfile
from apps.tracking.models import DriverLiveLocation
from apps.vehicle_categories.models import VehicleCategory
from apps.vehicles.models import Vehicle


def _normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    if raw.strip().startswith("+"):
        return raw.strip()
    return f"+{digits}"


class Command(BaseCommand):
    help = "Prepare a test driver (mini tempo + online + live location) for dispatch testing."

    def add_arguments(self, parser):
        parser.add_argument("--phone", default="9175504999", help="Driver phone number (with or without +91)")
        parser.add_argument("--password", default="Tran@123", help="Password to set for the test driver")
        parser.add_argument("--lat", type=float, default=20.0059, help="Driver latitude")
        parser.add_argument("--lng", type=float, default=73.7910, help="Driver longitude")

    def handle(self, *args, **options):
        phone = _normalize_phone(options["phone"])
        if not phone:
            raise CommandError("Provide a valid --phone value.")

        user_model = get_user_model()
        user, _ = user_model.objects.update_or_create(
            phone=phone,
            defaults={
                "role": user_model.Role.DRIVER,
                "is_active": True,
                "is_phone_verified": True,
                "city": "Nashik",
            },
        )
        user.set_password(options["password"])
        user.save(update_fields=["password"])

        profile, _ = DriverProfile.objects.update_or_create(
            user=user,
            defaults={
                "kyc_status": DriverProfile.KYCStatus.APPROVED,
                "onboarding_completed": True,
                "is_online": True,
            },
        )

        category = VehicleCategory.objects.filter(name__iexact="mini tempo", is_deleted=False, active=True).first()
        if not category:
            raise CommandError("Vehicle category 'mini tempo' not found. Run seed command first.")

        vehicle, created = Vehicle.objects.get_or_create(
            registration_number="MH15MT4999",
            defaults={
                "driver": profile,
                "category": category,
                "brand": "Test",
                "model_name": "Mini Tempo",
                "status": Vehicle.Status.ACTIVE,
            },
        )
        if not created:
            vehicle.driver = profile
            vehicle.category = category
            vehicle.status = Vehicle.Status.ACTIVE
            vehicle.save(update_fields=["driver", "category", "status", "updated_at"])

        DriverLiveLocation.objects.update_or_create(
            driver=profile,
            defaults={
                "location": Point(float(options["lng"]), float(options["lat"]), srid=4326),
                "speed_kmph": 0,
                "heading": 0,
                "accuracy_m": 10,
            },
        )

        self.stdout.write(self.style.SUCCESS(f"Driver ready for Mini Tempo dispatch: {phone}"))
