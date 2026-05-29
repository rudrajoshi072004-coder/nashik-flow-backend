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


def _normalize_allowed_host_entry(host: str) -> str:
    host = host.strip()
    # Django uses ".example.com" for subdomains, not "*.example.com".
    if host.startswith("*."):
        return host[1:]
    return host


ALLOWED_HOSTS = [_normalize_allowed_host_entry(h) for h in _allowed.split(",") if h.strip()]
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

def _is_local_db_host(host: str) -> bool:
    normalized = (host or "").strip().lower()
    return normalized in {"", "localhost", "127.0.0.1", "::1"}


def _is_railway_internal_host(host: str) -> bool:
    return (host or "").strip().endswith(".railway.internal")


def _host_from_database_url(url: str) -> str:
    return (urlparse(url).hostname or "").strip()


def _host_resolvable(hostname: str) -> bool:
    host = (hostname or "").strip()
    if not host or _is_local_db_host(host):
        return False
    import socket

    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def _is_usable_database_url(url: str) -> bool:
    url = (url or "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        return False
    if "@://" in url or url.count("@") > 1:
        return False
    host = _host_from_database_url(url)
    if not host or _is_local_db_host(host):
        return False
    if _is_railway_internal_host(host) and not _host_resolvable(host):
        return False
    return True


def _print_database_config_help(candidates: list[tuple[str, str]], *, reason: str) -> None:
    import sys

    lines = [f"ERROR: {reason}", ""]
    for key, url in candidates:
        host = _host_from_database_url(url) or "(missing host)"
        lines.append(f"  - {key}: host={host!r}")
    lines.extend(
        [
            "",
            "Railway fix:",
            "  1. On the web service, set DATABASE_URL to PostGIS DATABASE_PUBLIC_URL",
            "     (host must be *.proxy.rlwy.net, not postgis.railway.internal).",
            "  2. Remove PGDATA and POSTGRES_* from the web service (DB service only).",
            "  3. PostGIS and backend must be in the same project for *.railway.internal.",
            "  4. Redeploy the web service.",
        ]
    )
    print("\n".join(lines), file=sys.stderr)


def _database_url_from_env() -> str:
    import sys

    # Prefer public URL first (cross-project / TCP proxy on Railway).
    ordered_keys = (
        "DATABASE_PUBLIC_URL",
        "DATABASE_URL",
        "DATABASE_PRIVATE_URL",
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

    usable = [(key, url) for key, url in candidates if _is_usable_database_url(url)]

    for key, url in usable:
        host = _host_from_database_url(url)
        if _host_resolvable(host):
            skipped_internal = [
                k
                for k, u in candidates
                if k in ("DATABASE_URL", "DATABASE_PRIVATE_URL")
                and _is_railway_internal_host(_host_from_database_url(u))
                and not _is_usable_database_url(u)
            ]
            if skipped_internal and key == "DATABASE_PUBLIC_URL":
                print(
                    "Database: using DATABASE_PUBLIC_URL "
                    f"(skipped unusable: {', '.join(skipped_internal)}).",
                    file=sys.stderr,
                )
            elif key not in ("DATABASE_URL", "DATABASE_PUBLIC_URL") and any(
                k == "DATABASE_PUBLIC_URL" for k, _ in usable
            ):
                print(
                    f"Database: using {key} (DATABASE_PUBLIC_URL also set).",
                    file=sys.stderr,
                )
            return url

    # Public Railway proxy hostnames may not resolve at import time; still use them.
    for key, url in usable:
        host = _host_from_database_url(url)
        if ".proxy.rlwy.net" in host or not _is_railway_internal_host(host):
            return url

    if candidates:
        _print_database_config_help(
            candidates,
            reason="No usable database URL (localhost, missing host, or unreachable *.railway.internal).",
        )
    elif (os.getenv("POSTGRES_USER") or os.getenv("POSTGRES_PASSWORD") or os.getenv("POSTGRES_DB")) and not (
        os.getenv("PGHOST") or os.getenv("POSTGRES_HOST")
    ):
        _print_database_config_help(
            [],
            reason="POSTGRES_USER/PASSWORD/DB are set on the web service without DATABASE_URL or PGHOST.",
        )

    pg_host = (os.getenv("PGHOST") or os.getenv("POSTGRES_HOST") or "").strip()
    if pg_host and "://" not in pg_host and not _is_local_db_host(pg_host) and _host_resolvable(pg_host):
        pg_user = (os.getenv("PGUSER") or os.getenv("POSTGRES_USER") or "postgres").strip()
        pg_password = (os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD") or "").strip()
        pg_db = (os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB") or "railway").strip()
        pg_port = (os.getenv("PGPORT") or os.getenv("POSTGRES_PORT") or "5432").strip()
        auth = f"{pg_user}:{pg_password}@" if pg_password else f"{pg_user}@"
        return f"postgresql://{auth}{pg_host}:{pg_port}/{pg_db}"

    return ""


def _normalize_db_host(value: str) -> str:
    host = (value or "").strip()
    if not host:
        return ""
    if "://" in host:
        parsed = urlparse(host)
        if parsed.hostname:
            return parsed.hostname
    return host


def _database_from_env() -> dict:
    from django.core.exceptions import ImproperlyConfigured

    database_url = _database_url_from_env()
    if database_url:
        parsed = urlparse(database_url)
        query = parse_qs(parsed.query)
        host = _normalize_db_host(parsed.hostname or "")
        if not host or _is_local_db_host(host):
            raise ImproperlyConfigured(
                "DATABASE_URL is set but has no remote host. "
                "Set DATABASE_URL to your Railway DATABASE_PUBLIC_URL (*.proxy.rlwy.net)."
            )
        db_config = {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": (parsed.path or "/").lstrip("/") or os.getenv("POSTGRES_DB", "nashik_logistics"),
            "USER": unquote(parsed.username or "") or os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": unquote(parsed.password or "") or os.getenv("POSTGRES_PASSWORD", "postgres"),
            "HOST": host,
            "PORT": str(parsed.port or os.getenv("POSTGRES_PORT", "5432")),
        }
        sslmode = query.get("sslmode", [None])[0] or (os.getenv("POSTGRES_SSLMODE") or "").strip()
        if not sslmode and not _is_local_db_host(db_config["HOST"]):
            sslmode = "require"
        if sslmode:
            db_config["OPTIONS"] = {"sslmode": sslmode}
        return db_config

    discrete_host = _normalize_db_host(os.getenv("PGHOST") or os.getenv("POSTGRES_HOST") or "")
    if discrete_host and not _is_local_db_host(discrete_host):
        return {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB", "nashik_logistics"),
            "USER": os.getenv("PGUSER") or os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD", "postgres"),
            "HOST": discrete_host,
            "PORT": os.getenv("PGPORT") or os.getenv("POSTGRES_PORT", "5432"),
            "OPTIONS": {"sslmode": os.getenv("POSTGRES_SSLMODE", "require")},
        }

    raise ImproperlyConfigured(
        "PostgreSQL is not configured for production. "
        "On Railway, set DATABASE_URL to the PostGIS service DATABASE_PUBLIC_URL "
        "(postgresql://...@....proxy.rlwy.net:.../...). "
        "Remove POSTGRES_* and PGDATA from the web service."
    )


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
