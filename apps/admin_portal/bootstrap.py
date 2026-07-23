"""Bootstrap admin phone helpers shared by management commands and login."""

from __future__ import annotations

import os

from apps.authn.phone_utils import normalize_phone_e164


def bootstrap_admin_phones_e164() -> set[str]:
    raw = (os.getenv("ADMIN_BOOTSTRAP_PHONES") or "+919175504996").strip()
    phones: set[str] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            phones.add(normalize_phone_e164(part))
    return phones


def is_bootstrap_admin_phone(phone: str) -> bool:
    return normalize_phone_e164(phone) in bootstrap_admin_phones_e164()


def promote_bootstrap_admin_if_needed(user) -> bool:
    """Promote bootstrap phones to super_admin. Returns True when role changed."""
    if not is_bootstrap_admin_phone(user.phone):
        return False

    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    changed = user.role != user_model.Role.SUPER_ADMIN or not user.is_staff or not user.is_active
    if not changed:
        return False

    user.role = user_model.Role.SUPER_ADMIN
    user.is_staff = True
    user.is_active = True
    user.save(update_fields=["role", "is_staff", "is_active", "updated_at"])
    return True
