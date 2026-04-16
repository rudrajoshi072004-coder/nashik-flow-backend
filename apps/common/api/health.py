from django.db import connection
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

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
                "services": {"database": db_ok, "redis": redis_ok},
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
        try:
            cache.set("health:ping", "pong", timeout=10)
            return cache.get("health:ping") == "pong"
        except Exception:
            return False
