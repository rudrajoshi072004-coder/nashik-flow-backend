from django.core.management.base import BaseCommand
from apps.rbac.models import Role


class Command(BaseCommand):
    help = "Seed baseline platform roles"

    def handle(self, *args, **options):
        roles = [
            ("guest", "Guest"),
            ("customer", "Customer"),
            ("driver", "Driver"),
            ("fleet_driver", "Fleet Driver"),
            ("city_manager", "City Manager"),
            ("support_agent", "Support Agent"),
            ("finance_admin", "Finance Admin"),
            ("super_admin", "Super Admin"),
        ]
        for code, name in roles:
            Role.objects.get_or_create(code=code, defaults={"name": name, "is_system": True, "active": True})
        self.stdout.write(self.style.SUCCESS("Baseline roles seeded."))
