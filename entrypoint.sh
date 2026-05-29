#!/bin/sh
set -e
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"
export PORT="${PORT:-8000}"

python - <<'PY'
import os
import re
import sys
from urllib.parse import urlparse

LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def host_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").strip()


def is_valid_railway_db_url(url: str) -> bool:
    url = (url or "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        return False
    host = host_from_url(url)
    if not host or host.lower() in LOCAL_HOSTS:
        return False
    if host.endswith(".railway.internal"):
        return False
    if "@://" in url or url.count("@") > 1:
        return False
    if ".proxy.rlwy.net" in host or ".proxy.rlwy.net" in url:
        return True
    return bool(re.match(r"^[a-zA-Z0-9.-]+$", host))


def pick_database_url() -> str:
    for key in ("DATABASE_PUBLIC_URL", "DATABASE_URL", "DATABASE_PRIVATE_URL", "POSTGRES_URL"):
        candidate = (os.getenv(key) or "").strip()
        if is_valid_railway_db_url(candidate):
            return candidate
    return ""


chosen = pick_database_url()
if not chosen:
    print(
        "ERROR: No valid PostgreSQL URL for Railway.\n"
        "Copy PostGIS → DATABASE_PUBLIC_URL (host *.proxy.rlwy.net) into web service DATABASE_URL.\n"
        "Remove broken URLs containing postgis.railway.internal, @://, or only POSTGRES_* vars.\n",
        file=sys.stderr,
    )
    for key in ("DATABASE_PUBLIC_URL", "DATABASE_URL", "DATABASE_PRIVATE_URL"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            print(f"  {key} host={host_from_url(raw)!r}", file=sys.stderr)
    sys.exit(1)

os.environ["DATABASE_URL"] = chosen
print(f"Using DATABASE_URL host: {host_from_url(chosen)!r}", file=sys.stderr)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
import django

django.setup()
from django.conf import settings

db = settings.DATABASES["default"]
host = (db.get("HOST") or "").strip()
if not host or host.lower() in LOCAL_HOSTS:
    print(
        f"ERROR: Django DATABASE HOST is {host!r}. "
        "Redeploy latest code and set DATABASE_URL to PostGIS DATABASE_PUBLIC_URL.",
        file=sys.stderr,
    )
    sys.exit(1)
print(f"Database target host: {host}", file=sys.stderr)
PY

python - <<'PY'
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from django.db import connection

POSTGIS_TEMPLATE = "https://railway.com/deploy/postgis-spatial-database"
SUPABASE_TEMPLATE = "https://railway.com/deploy/supabase-postgres-1"

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'postgis')"
    )
    available = cursor.fetchone()[0]

if not available:
    print(
        "ERROR: PostGIS is not available on this PostgreSQL server.\n"
        "This app requires PostGIS (maps, pickup/drop locations, service zones).\n\n"
        "Railway's default PostgreSQL plugin does NOT include PostGIS.\n"
        "Fix:\n"
        f"  1. Add a PostGIS database: {POSTGIS_TEMPLATE}\n"
        f"     (or Supabase Postgres on Railway: {SUPABASE_TEMPLATE})\n"
        "  2. Point this web service to the new DB (reference DATABASE_PRIVATE_URL).\n"
        "  3. Remove the old standard Postgres DATABASE_URL references.\n"
        "  4. Redeploy.\n",
        file=sys.stderr,
    )
    sys.exit(1)

with connection.cursor() as cursor:
    cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    print("postgis extension ready")
PY

python manage.py migrate --noinput

python manage.py seed_nashik || true
python manage.py seed_roles || true
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); u,_=U.objects.update_or_create(phone='9175504999', defaults={'role':U.Role.DRIVER,'is_active':True,'is_phone_verified':True,'city':'Nashik'}); u.set_password('Tran@123'); u.save(update_fields=['password']); print('driver-ready', u.phone)" || true
exec "$@"
