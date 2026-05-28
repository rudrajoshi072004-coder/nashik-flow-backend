#!/bin/sh
set -e
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"
export PORT="${PORT:-8000}"

python - <<'PY'
import os
import sys

keys = (
    "DATABASE_PRIVATE_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
    "PGHOST",
    "POSTGRES_HOST",
)
if not any((os.getenv(k) or "").strip() for k in keys):
    print(
        "ERROR: No PostgreSQL configuration found.\n"
        "On Railway: link Postgres variables (DATABASE_PRIVATE_URL / DATABASE_URL / PGHOST).",
        file=sys.stderr,
    )
    sys.exit(1)

host = (os.getenv("PGHOST") or os.getenv("POSTGRES_HOST") or "").strip()
if host in ("", "localhost", "127.0.0.1", "::1") and not (
    os.getenv("DATABASE_URL") or os.getenv("DATABASE_PRIVATE_URL")
):
    print(
        "ERROR: Database host is localhost inside the container.\n"
        "Link Railway Postgres to this web service.",
        file=sys.stderr,
    )
    sys.exit(1)
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
