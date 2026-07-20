"""Ensure every driver account has a profile (and wallet) for admin + app flows."""

from __future__ import annotations

from django.contrib.auth import get_user_model


def ensure_driver_profile(user, *, create_wallet: bool = True):
    """Create DriverProfile (+ Wallet) when user has a driver role."""
    user_model = get_user_model()
    if user.role not in (user_model.Role.DRIVER, user_model.Role.FLEET_DRIVER):
        return None

    from apps.drivers.models import DriverProfile

    profile, _ = DriverProfile.objects.get_or_create(user=user)
    if create_wallet:
        from apps.wallets.models import Wallet

        Wallet.objects.get_or_create(driver=profile)
    return profile
