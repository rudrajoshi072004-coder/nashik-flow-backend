from .base import *  # noqa: F403,F401

DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True

# Phones call http://<LAN-IP>:8000 — Host must be allowed (DisallowedHost otherwise).
# Override base/.env so Docker or a bad DJANGO_ALLOWED_HOSTS value cannot lock you to localhost only.
ALLOWED_HOSTS = ["*", "localhost", "127.0.0.1", "[::1]"]

# In-memory cache so OTP works with `manage.py runserver` without a local Redis.
# (Docker/production should use settings that keep Redis for cache when needed.)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "nashik-local-dev",
    }
}
