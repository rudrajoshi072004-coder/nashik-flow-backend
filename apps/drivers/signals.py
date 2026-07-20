from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.drivers.profile_service import ensure_driver_profile


@receiver(post_save, sender=get_user_model())
def ensure_driver_profile_on_user_save(sender, instance, created, **kwargs):
    """New driver sign-ups appear in admin immediately with a profile row."""
    user_model = get_user_model()
    if instance.role in (user_model.Role.DRIVER, user_model.Role.FLEET_DRIVER):
        ensure_driver_profile(instance)
