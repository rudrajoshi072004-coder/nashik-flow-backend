import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.admin_portal.bootstrap import bootstrap_admin_phones_e164, is_bootstrap_admin_phone


class Command(BaseCommand):
    help = "Promote phones listed in ADMIN_BOOTSTRAP_PHONES to super_admin."

    def handle(self, *args, **options):
        phones = bootstrap_admin_phones_e164()
        if not phones:
            self.stdout.write("No ADMIN_BOOTSTRAP_PHONES configured.")
            return

        user_model = get_user_model()
        for phone in sorted(phones):
            user, created = user_model.objects.get_or_create(
                phone=phone,
                defaults={
                    "role": user_model.Role.SUPER_ADMIN,
                    "is_staff": True,
                    "is_active": True,
                    "is_phone_verified": True,
                    "city": "Nashik",
                },
            )
            if user.role != user_model.Role.SUPER_ADMIN:
                user.role = user_model.Role.SUPER_ADMIN
                user.is_staff = True
            user.is_active = True
            if created or not user.has_usable_password():
                user.set_password(os.getenv("ADMIN_BOOTSTRAP_PASSWORD") or "Tran@123")
            user.save(update_fields=["role", "is_staff", "is_active", "password", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"Bootstrap admin ready: {phone}"))

        # Also promote legacy phone formats already in DB (e.g. 9175504996 without +91).
        for user in user_model.objects.filter(is_deleted=False):
            if is_bootstrap_admin_phone(user.phone) and user.role != user_model.Role.SUPER_ADMIN:
                user.role = user_model.Role.SUPER_ADMIN
                user.is_staff = True
                user.is_active = True
                user.save(update_fields=["role", "is_staff", "is_active", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"Promoted legacy record {user.phone} to super_admin"))
