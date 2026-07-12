from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.notifications.fcm import is_firebase_configured

from .responses import success_response


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ok = self._check_db()
        redis_ok = self._check_redis()
        status_text = "healthy" if db_ok and redis_ok else "degraded"
        return success_response(
            data={
                "status": status_text,
                "services": {
                    "database": db_ok,
                    "redis": redis_ok,
                    "firebase": is_firebase_configured(),
                },
                "request_id": getattr(request, "request_id", None),
            }
        )

    def _check_db(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
            return True
        except Exception:
            return False

    def _check_redis(self):
        # Redis is optional on Railway; locmem cache is valid when USE_REDIS is false.
        if not getattr(settings, "USE_REDIS", False):
            return True
        try:
            cache.set("health:ping", "pong", timeout=10)
            return cache.get("health:ping") == "pong"
        except Exception:
            return False
