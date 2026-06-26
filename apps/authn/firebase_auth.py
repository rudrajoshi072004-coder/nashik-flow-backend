"""Firebase Authentication bridge.

The mobile apps sign in with Firebase (phone OTP, email/password, or Google),
obtain a Firebase ID token, and POST it here. We verify the token with
firebase-admin, map it to a local User (by phone or email), and issue our own
SimpleJWT pair so the rest of the API / WebSocket auth keeps working unchanged.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

# Reuse the firebase-admin app already initialised for FCM push.
from apps.notifications.fcm import _get_firebase_app
from .phone_utils import find_user_by_phone, normalize_phone_e164

logger = logging.getLogger(__name__)

ALLOWED_ROLES = {"customer", "driver"}


class FirebaseAuthError(Exception):
    """Raised when a Firebase ID token cannot be verified."""


def verify_firebase_id_token(id_token: str) -> dict:
    """Verify the Firebase ID token and return its decoded claims."""
    if not id_token:
        raise FirebaseAuthError("Missing Firebase ID token.")

    if _get_firebase_app() is None:
        raise FirebaseAuthError(
            "Firebase is not configured on the server (FIREBASE_SERVICE_ACCOUNT_PATH)."
        )

    from firebase_admin import auth as fb_auth

    try:
        return fb_auth.verify_id_token(id_token)
    except Exception as exc:  # noqa: BLE001 - surface a clean 401 to the client
        logger.warning("Firebase token verification failed: %s", exc)
        raise FirebaseAuthError("Invalid or expired Firebase token.") from exc


def _placeholder_phone(uid: str) -> str:
    """Build a unique placeholder phone for email/Google users with no phone.

    The User model uses ``phone`` as USERNAME_FIELD (unique, max_length=20),
    so accounts created via email/Google still need a unique value here.
    """
    return f"fb_{(uid or '')[:16]}"


def find_or_create_user_for_firebase(decoded: dict, role: str = "customer", city: str = "Nashik"):
    """Map verified Firebase claims to a local User, creating one if needed."""
    user_model = get_user_model()

    role = role if role in ALLOWED_ROLES else "customer"
    uid = decoded.get("uid") or decoded.get("user_id") or ""
    phone = normalize_phone_e164((decoded.get("phone_number") or "").strip()) or None
    if phone == "":
        phone = None
    email = (decoded.get("email") or "").strip().lower() or None
    name = (decoded.get("name") or "").strip()

    user = None

    # 1) Prefer matching by phone (our primary identifier).
    if phone:
        user, _ = find_user_by_phone(user_model, phone)

    # 2) Fall back to email (used by email/password + Google sign-in).
    if user is None and email:
        user = user_model.objects.filter(email__iexact=email).first()

    if user is None:
        login_phone = phone or _placeholder_phone(uid)
        user = user_model.objects.create(
            phone=login_phone,
            email=email,
            role=role,
            city=city,
            is_active=True,
            is_phone_verified=bool(phone),
        )
    else:
        changed = []
        if role == user_model.Role.DRIVER and user.role != user_model.Role.DRIVER:
            user.role = user_model.Role.DRIVER
            changed.append("role")
        if email and not user.email:
            user.email = email
            changed.append("email")
        if phone and user.phone != phone and user.phone.startswith("fb_"):
            # Upgrade a placeholder phone to the verified real number.
            user.phone = phone
            user.is_phone_verified = True
            changed.extend(["phone", "is_phone_verified"])
        elif phone and not user.is_phone_verified:
            user.is_phone_verified = True
            changed.append("is_phone_verified")
        if changed:
            user.save(update_fields=list(set(changed)))

    if role == user_model.Role.DRIVER:
        from apps.drivers.models import DriverProfile

        DriverProfile.objects.get_or_create(user=user)

    if name and not (user.first_name or user.last_name):
        first, _, last = name.partition(" ")
        user.first_name = first
        user.last_name = last
        user.save(update_fields=["first_name", "last_name"])

    return user


def issue_tokens_for_firebase(id_token: str, role: str = "customer", city: str = "Nashik") -> dict:
    """Full flow: verify token -> resolve user -> issue our JWT pair."""
    decoded = verify_firebase_id_token(id_token)
    user = find_or_create_user_for_firebase(decoded, role=role, city=city)
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": user,
    }
