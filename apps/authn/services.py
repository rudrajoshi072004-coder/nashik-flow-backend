import random

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken


OTP_TTL_SECONDS = 300
ALLOWED_OTP_ROLES = {"customer", "driver"}


def _otp_cache_key(phone: str) -> str:
    return f"otp:login:{phone}"


def _dev_bypass_otp() -> str:
    return getattr(settings, "OTP_DEV_BYPASS", "") or ""


def request_otp(phone: str) -> str:
    bypass = _dev_bypass_otp()
    otp = bypass if bypass else f"{random.randint(100000, 999999)}"
    cache.set(_otp_cache_key(phone), otp, timeout=OTP_TTL_SECONDS)
    return otp


def verify_otp_and_issue_tokens(phone: str, otp: str, role: str = "customer") -> dict:
    bypass = _dev_bypass_otp()
    if bypass and otp == bypass:
        # Fixed dev OTP — skip cache (safe across Gunicorn workers without shared Redis).
        pass
    else:
        cached = cache.get(_otp_cache_key(phone))
        if not cached or cached != otp:
            raise ValueError("Invalid OTP")
        cache.delete(_otp_cache_key(phone))

    user_model = get_user_model()
    role_value = role if role in ALLOWED_OTP_ROLES else user_model.Role.CUSTOMER

    user, created = user_model.objects.get_or_create(
        phone=phone,
        defaults={"role": role_value, "is_active": True, "is_phone_verified": True},
    )
    user.is_phone_verified = True
    update_fields = ["is_phone_verified"]
    if hasattr(user, "updated_at"):
        update_fields.append("updated_at")
    if not created and role_value == user_model.Role.DRIVER and user.role != user_model.Role.DRIVER:
        user.role = user_model.Role.DRIVER
        update_fields.append("role")
    user.save(update_fields=update_fields)

    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": user,
    }
