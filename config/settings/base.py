import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")

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

def _database_url_from_env() -> str:
    # Accept common Render/hosting variable names.
    for key in ("DATABASE_URL", "POSTGRES_URL", "INTERNAL_DATABASE_URL", "EXTERNAL_DATABASE_URL"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


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
        if sslmode:
            db_config["OPTIONS"] = {"sslmode": sslmode}
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

REDIS_URL = (os.getenv("REDIS_URL") or "").strip()
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
