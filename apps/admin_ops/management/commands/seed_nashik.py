from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon
from django.contrib.auth import get_user_model

from apps.service_zones.models import ServiceZone
from apps.vehicle_categories.models import VehicleCategory


class Command(BaseCommand):
    help = "Seed Nashik city baseline data"

    def handle(self, *args, **options):
        self._seed_admins()
        self._seed_vehicle_categories()
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
