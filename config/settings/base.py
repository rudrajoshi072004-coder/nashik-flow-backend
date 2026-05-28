import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from dotenv import load_dotenv

# Project root is nashik-flow-backend/ (config/settings -> config -> backend).
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key-change-this-to-32-plus-bytes")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
# Empty DJANGO_ALLOWED_HOSTS in .env becomes "" — getenv returns "" and ".split" yields [""], which rejects every host.
_allowed = (os.getenv("DJANGO_ALLOWED_HOSTS") or "*").strip()
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "channels",
    "django_celery_beat",
    "django_celery_results",
    "apps.common",
    "apps.rbac",
    "apps.authn",
    "apps.users",
    "apps.profiles",
    "apps.customers",
    "apps.drivers",
    "apps.driver_documents",
    "apps.vehicles",
    "apps.vehicle_categories",
    "apps.service_zones",
    "apps.geo",
    "apps.addresses",
    "apps.bookings",
    "apps.booking_items",
    "apps.pricing",
    "apps.fare_rules",
    "apps.dispatch",
    "apps.ride_socket_demo",
    "apps.tracking",
    "apps.trip_events",
    "apps.wallets",
    "apps.wallet_transactions",
    "apps.payouts",
    "apps.payments",
    "apps.refunds",
    "apps.coupons",
    "apps.incentives",
    "apps.admin_ops",
    "apps.audit_logs",
    "apps.notifications",
    "apps.chat",
    "apps.support",
    "apps.ratings",
    "apps.reviews",
    "apps.cms",
    "apps.app_settings",
    "apps.analytics",
    "apps.reporting",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.request_context.RequestContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    }
]

def _host_resolvable(hostname: str) -> bool:
    host = (hostname or "").strip()
    if not host or _is_local_db_host(host):
        return True
    import socket

    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def _database_url_from_env() -> str:
    import sys

    # Railway, Render, Heroku, and similar PaaS variable names.
    ordered_keys = (
        "DATABASE_PRIVATE_URL",  # Railway internal (same project only)
        "DATABASE_URL",
        "DATABASE_PUBLIC_URL",  # Railway TCP proxy URL
        "POSTGRES_URL",
        "INTERNAL_DATABASE_URL",
        "EXTERNAL_DATABASE_URL",
        "RAILWAY_DATABASE_URL",
    )
    candidates: list[tuple[str, str]] = []
    for key in ordered_keys:
        value = (os.getenv(key) or "").strip()
        if value:
            candidates.append((key, value))

    for key, url in candidates:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if _host_resolvable(host):
            if key != "DATABASE_PRIVATE_URL" and any(k == "DATABASE_PRIVATE_URL" for k, _ in candidates):
                print(
                    f"Database: using {key} because private host {host!r} is not reachable.",
                    file=sys.stderr,
                )
            return url

    if candidates:
        key, url = candidates[0]
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host.endswith(".railway.internal"):
            print(
                f"ERROR: Cannot resolve database host {host!r}.\n"
                "Railway private URLs (*.railway.internal) only work when backend and PostGIS\n"
                "are in the SAME project and environment.\n\n"
                "Fix (choose one):\n"
                "  A) Backend Variables → remove DATABASE_PRIVATE_URL\n"
                "     → add reference to PostGIS service → DATABASE_URL (public, *.proxy.rlwy.net)\n"
                "  B) Ensure PostGIS + backend are in the same Railway project, then redeploy both.\n"
                "  C) Do not paste postgis.railway.internal manually — use Variable Reference.",
                file=sys.stderr,
            )
        return url

    # Railway/Heroku also expose discrete PG* vars when Postgres is linked.
    pg_host = (os.getenv("PGHOST") or os.getenv("POSTGRES_HOST") or "").strip()
    if pg_host and "://" not in pg_host and _host_resolvable(pg_host):
        pg_user = (os.getenv("PGUSER") or os.getenv("POSTGRES_USER") or "postgres").strip()
        pg_password = (os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD") or "").strip()
        pg_db = (os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB") or "railway").strip()
        pg_port = (os.getenv("PGPORT") or os.getenv("POSTGRES_PORT") or "5432").strip()
        auth = f"{pg_user}:{pg_password}@" if pg_password else f"{pg_user}@"
        return f"postgresql://{auth}{pg_host}:{pg_port}/{pg_db}"

    return ""


def _is_local_db_host(host: str) -> bool:
    normalized = (host or "").strip().lower()
    return normalized in {"", "localhost", "127.0.0.1", "::1"}


def _normalize_db_host(value: str) -> str:
    host = (value or "").strip()
    if not host:
        return "localhost"
    # Some deployments accidentally paste a full URL into POSTGRES_HOST.
    if "://" in host:
        parsed = urlparse(host)
        if parsed.hostname:
            return parsed.hostname
    return host


def _database_from_env() -> dict:
    database_url = _database_url_from_env()
    if database_url:
        parsed = urlparse(database_url)
        query = parse_qs(parsed.query)
        db_config = {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": (parsed.path or "/").lstrip("/") or os.getenv("POSTGRES_DB", "nashik_logistics"),
            "USER": unquote(parsed.username or "") or os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": unquote(parsed.password or "") or os.getenv("POSTGRES_PASSWORD", "postgres"),
            "HOST": _normalize_db_host(parsed.hostname or os.getenv("POSTGRES_HOST", "localhost")),
            "PORT": str(parsed.port or os.getenv("POSTGRES_PORT", "5432")),
        }
        sslmode = query.get("sslmode", [None])[0] or (os.getenv("POSTGRES_SSLMODE") or "").strip()
        if not sslmode and not _is_local_db_host(db_config["HOST"]):
            # Managed Postgres (Railway/Render) typically requires TLS.
            sslmode = "require"
        if sslmode:
            db_config["OPTIONS"] = {"sslmode": sslmode}
        return db_config

    discrete_host = _normalize_db_host(os.getenv("POSTGRES_HOST", ""))
    if discrete_host and not _is_local_db_host(discrete_host):
        db_config = {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.getenv("POSTGRES_DB", "nashik_logistics"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
            "HOST": discrete_host,
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "OPTIONS": {"sslmode": os.getenv("POSTGRES_SSLMODE", "require")},
        }
        return db_config

    return {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.getenv("POSTGRES_DB", "nashik_logistics"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": _normalize_db_host(os.getenv("POSTGRES_HOST", "localhost")),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }


DATABASES = {"default": _database_from_env()}

AUTH_USER_MODEL = "users.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "EXCEPTION_HANDLER": "apps.common.api.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": (
        "apps.common.api.renderers.StandardizedJSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": int(os.getenv("API_PAGE_SIZE", "20")),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "14"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Nashik Logistics API",
    "DESCRIPTION": "Production-style logistics API for Nashik launch city.",
    "VERSION": "1.0.0",
}

CORS_ALLOW_ALL_ORIGINS = True

REDIS_URL = (
    os.getenv("REDIS_URL")
    or os.getenv("REDIS_PRIVATE_URL")
    or os.getenv("REDIS_TLS_URL")
    or ""
).strip()
USE_REDIS = bool(REDIS_URL)

if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
else:
    # Deployment-safe fallback: app still runs without external Redis.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "nashik-logistics-local-cache",
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
if not USE_REDIS:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "celery": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "channels": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
