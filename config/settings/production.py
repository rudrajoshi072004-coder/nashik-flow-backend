import os

from .base import *  # noqa: F403,F401

DEBUG = False

# Railway healthchecks hit healthcheck.railway.app; app URLs use *.up.railway.app.
_railway_hosts = (
    "healthcheck.railway.app",
    ".railway.app",
    ".up.railway.app",
)
if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
    for host in _railway_hosts:
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

_cors_origins = [
    origin.strip()
    for origin in (os.getenv("CORS_ALLOWED_ORIGINS") or "").split(",")
    if origin.strip()
]
if _cors_origins:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = _cors_origins
else:
    # Allow mobile/web clients until explicit origins are configured on Railway.
    CORS_ALLOW_ALL_ORIGINS = True

_csrf_trusted = [
    origin.strip()
    for origin in (os.getenv("CSRF_TRUSTED_ORIGINS") or "").split(",")
    if origin.strip()
]
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS = _csrf_trusted

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
