from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.authn.phone_utils import find_user_by_phone


class Command(BaseCommand):
    help = "Promote a user phone number to super_admin for the admin portal."

    def add_arguments(self, parser):
        parser.add_argument("phone", help="Phone number, e.g. +919175504996 or 9175504996")

    def handle(self, *args, **options):
        user_model = get_user_model()
        user, _ = find_user_by_phone(user_model, str(options["phone"]).strip())
        if user is None or user.is_deleted:
            raise CommandError(f"No user found for phone {options['phone']}")

        user.role = user_model.Role.SUPER_ADMIN
        user.is_staff = True
        user.is_active = True
        user.save(update_fields=["role", "is_staff", "is_active", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"Promoted {user.phone} to super_admin"))
