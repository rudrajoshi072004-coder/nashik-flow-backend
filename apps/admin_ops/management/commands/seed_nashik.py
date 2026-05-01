from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.drivers.models import DriverProfile
from apps.service_zones.models import ServiceZone
from apps.tracking.models import DriverLiveLocation
from apps.vehicle_categories.models import VehicleCategory
from apps.vehicles.models import Vehicle


class Command(BaseCommand):
    help = "Seed Nashik city baseline data"

    def handle(self, *args, **options):
        self._seed_admins()
        self._seed_demo_customer()
        self._seed_vehicle_categories()
        self._seed_demo_driver_dispatch()
        self._seed_service_zones()
        self.stdout.write(self.style.SUCCESS("Nashik seed completed."))

    def _seed_admins(self):
        user_model = get_user_model()
        user_model.objects.get_or_create(
            phone="+919100000001",
            defaults={
                "role": user_model.Role.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "city": "Nashik",
            },
        )

    def _seed_demo_customer(self):
        """Dev/demo customer for password login on mobile (see customer app login screen)."""
        user_model = get_user_model()
        u, _ = user_model.objects.update_or_create(
            phone="+919175504996",
            defaults={
                "role": user_model.Role.CUSTOMER,
                "is_active": True,
                "is_phone_verified": True,
                "city": "Nashik",
            },
        )
        u.set_password("Tran@123")
        u.save(update_fields=["password"])

    def _seed_vehicle_categories(self):
        rows = [
            ("2-wheeler", "parcel", 20, 0.15, 35, 9),
            ("3-wheeler", "light_goods", 450, 1.8, 90, 18),
            ("4-wheeler", "goods", 750, 2.5, 130, 23),
            ("mini tempo", "goods", 1200, 5, 180, 27),
            ("pickup truck", "heavy_goods", 1800, 9, 240, 33),
            ("big tempo", "heavy_goods", 3200, 14, 350, 43),
            ("truck", "bulk_goods", 7500, 35, 600, 52),
        ]
        for order, row in enumerate(rows, start=1):
            name, payload, max_w, max_v, base_fare, per_km = row
            VehicleCategory.objects.get_or_create(
                name=name,
                defaults={
                    "payload_type": payload,
                    "max_weight_kg": max_w,
                    "max_volume_m3": max_v,
                    "base_fare": base_fare,
                    "per_km_rate": per_km,
                    "waiting_per_min": 2,
                    "minimum_fare": base_fare,
                    "helper_supported": name not in {"2-wheeler", "3-wheeler"},
                    "intra_city_available": True,
                    "active": True,
                    "priority_order": order,
                },
            )

    def _seed_demo_driver_dispatch(self):
        """Demo drivers for local/LAN QA: approved KYC, vehicles for every category, Nashik-ish live coords."""
        for phone, lat, lng in (
            ("9175504999", 19.9975, 73.7898),
            ("9175504998", 19.9982, 73.7905),  # Slight offset (~100 m) vs first driver.
        ):
            self._ensure_dispatch_ready_driver(phone=phone, lat=lat, lng=lng)

    def _ensure_dispatch_ready_driver(self, *, phone: str, lat: float, lng: float):
        user_model = get_user_model()
        u, _ = user_model.objects.update_or_create(
            phone=phone,
            defaults={
                "role": user_model.Role.DRIVER,
                "is_active": True,
                "is_phone_verified": True,
                "city": "Nashik",
            },
        )
        u.set_password("Tran@123")
        u.save(update_fields=["password"])

        profile, _created = DriverProfile.objects.get_or_create(user=u)
        profile.kyc_status = DriverProfile.KYCStatus.APPROVED
        profile.is_online = True
        profile.save(update_fields=["kyc_status", "is_online", "updated_at"])

        uid_part = profile.id.hex[:12]
        for cat in VehicleCategory.objects.filter(active=True, is_deleted=False).order_by("priority_order"):
            reg_num = (f"S{uid_part}{cat.id.hex}"[:32]).upper()
            Vehicle.objects.get_or_create(
                registration_number=reg_num,
                defaults={
                    "driver": profile,
                    "category": cat,
                    "status": Vehicle.Status.ACTIVE,
                    "brand": "Seed",
                    "model_name": cat.name,
                },
            )

        DriverLiveLocation.objects.update_or_create(
            driver=profile,
            defaults={
                "location": Point(float(lng), float(lat), srid=4326),
                "booking": None,
                "heading": 0,
                "speed_kmph": 0,
                "accuracy_m": 30,
                "source_timestamp": timezone.now(),
            },
        )

    def _seed_service_zones(self):
        # Approximate Nashik core bounding polygon for development seeds.
        polygon = Polygon(
            (
                (73.6770, 19.8800),
                (73.9200, 19.8800),
                (73.9200, 20.0900),
                (73.6770, 20.0900),
                (73.6770, 19.8800),
            )
        )
        ServiceZone.objects.get_or_create(
            city_name="Nashik",
            zone_name="Nashik Core",
            defaults={"polygon": polygon, "active": True},
        )
