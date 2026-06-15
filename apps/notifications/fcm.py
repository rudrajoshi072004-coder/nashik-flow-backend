"""FCM push notifications via firebase-admin (offer fallback layer)."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_app = None


def _get_firebase_app():
    global _app
    if _app is not None:
        return _app
    path = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_PATH", "") or ""
    if not path:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred = credentials.Certificate(path)
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
        logger.warning("FCM skipped: FIREBASE_SERVICE_ACCOUNT_PATH not set")
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
