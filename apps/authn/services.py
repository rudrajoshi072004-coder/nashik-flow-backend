import random
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken


OTP_TTL_SECONDS = 300


def _otp_cache_key(phone: str) -> str:
    return f"otp:login:{phone}"


def request_otp(phone: str) -> str:
    otp = f"{random.randint(100000, 999999)}"
    cache.set(_otp_cache_key(phone), otp, timeout=OTP_TTL_SECONDS)
    return otp


def verify_otp_and_issue_tokens(phone: str, otp: str) -> dict:
    cached = cache.get(_otp_cache_key(phone))
    if not cached or cached != otp:
        raise ValueError("Invalid OTP")

    user_model = get_user_model()
    user, _ = user_model.objects.get_or_create(
        phone=phone,
        defaults={"role": user_model.Role.CUSTOMER, "is_active": True, "is_phone_verified": True},
    )
    user.is_phone_verified = True
    user.save(update_fields=["is_phone_verified", "updated_at"] if hasattr(user, "updated_at") else ["is_phone_verified"])

    refresh = RefreshToken.for_user(user)
    cache.delete(_otp_cache_key(phone))
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": user,
    }
