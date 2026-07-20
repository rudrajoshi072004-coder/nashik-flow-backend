import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Promote phones listed in ADMIN_BOOTSTRAP_PHONES to super_admin."

    def handle(self, *args, **options):
        raw = (os.getenv("ADMIN_BOOTSTRAP_PHONES") or "+919175504996").strip()
        phones = [part.strip() for part in raw.split(",") if part.strip()]
        if not phones:
            self.stdout.write("No ADMIN_BOOTSTRAP_PHONES configured.")
            return

        user_model = get_user_model()
        for phone in phones:
            digits = "".join(ch for ch in phone if ch.isdigit())
            if len(digits) == 10:
                normalized = f"+91{digits}"
            elif len(digits) == 12 and digits.startswith("91"):
                normalized = f"+{digits}"
            elif phone.startswith("+") and len(digits) >= 10:
                normalized = f"+{digits}"
            else:
                self.stderr.write(self.style.WARNING(f"Skipping invalid phone: {phone}"))
                continue

            user, created = user_model.objects.get_or_create(
                phone=normalized,
                defaults={
                    "role": user_model.Role.SUPER_ADMIN,
                    "is_staff": True,
                    "is_active": True,
                    "is_phone_verified": True,
                    "city": "Nashik",
                },
            )
            if user.role == user_model.Role.CUSTOMER:
                user.role = user_model.Role.SUPER_ADMIN
                user.is_staff = True
            if created or not user.has_usable_password():
                user.set_password(os.getenv("ADMIN_BOOTSTRAP_PASSWORD") or "Tran@123")
            user.save(update_fields=["role", "is_staff", "password", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"Bootstrap admin ready: {normalized}"))
