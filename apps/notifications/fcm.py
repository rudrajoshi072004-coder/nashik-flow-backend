"""FCM push notifications via firebase-admin (offer fallback layer)."""

from __future__ import annotations

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_app = None


def _firebase_credentials():
    """Build firebase-admin credentials from a file path or JSON env var (Railway)."""
    path = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_PATH", "") or ""
    json_blob = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "") or ""
    if json_blob:
        return json.loads(json_blob)
    if path:
        return path
    return None


def is_firebase_configured() -> bool:
    return _firebase_credentials() is not None


def _get_firebase_app():
    global _app
    if _app is not None:
        return _app
    cred_source = _firebase_credentials()
    if not cred_source:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_source)
            _app = firebase_admin.initialize_app(cred)
        else:
            _app = firebase_admin.get_app()
        return _app
    except Exception:
        logger.exception("Firebase init failed")
        return None


def send_fcm_push(token: str, title: str, body: str, data: dict | None = None) -> bool:
    if not token:
        return False
    if _get_firebase_app() is None:
        logger.warning("FCM skipped: set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_JSON")
        return False

    from firebase_admin import messaging

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        token=token,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default", badge=1)),
        ),
    )
    try:
        messaging.send(message)
        return True
    except Exception:
        logger.exception("FCM send failed")
        return False
