from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Promote a user phone number to super_admin for the admin portal."

    def add_arguments(self, parser):
        parser.add_argument("phone", help="Phone number, e.g. +919175504996 or 9175504996")

    def handle(self, *args, **options):
        raw = str(options["phone"]).strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 10:
            phone = f"+91{digits}"
        elif len(digits) == 12 and digits.startswith("91"):
            phone = f"+{digits}"
        elif raw.startswith("+") and len(digits) >= 10:
            phone = f"+{digits}"
        else:
            raise CommandError(f"Invalid phone number: {options['phone']}")

        user_model = get_user_model()
        try:
            user = user_model.objects.get(phone=phone, is_deleted=False)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"No user found for phone {phone}") from exc

        user.role = user_model.Role.SUPER_ADMIN
        user.is_staff = True
        user.is_active = True
        user.save(update_fields=["role", "is_staff", "is_active", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"Promoted {phone} to super_admin"))
