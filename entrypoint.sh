#!/bin/sh
set -e
# Phones call http://<PC-LAN-IP>:<port> — narrow .env values cause DisallowedHost before Django starts.
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
        "On Railway: add a PostgreSQL plugin to this service (or reference its variables)\n"
        "so DATABASE_URL / DATABASE_PRIVATE_URL / PGHOST are set.",
        file=sys.stderr,
    )
    sys.exit(1)

host = (os.getenv("PGHOST") or os.getenv("POSTGRES_HOST") or "").strip()
if host in ("", "localhost", "127.0.0.1", "::1") and not (
    os.getenv("DATABASE_URL") or os.getenv("DATABASE_PRIVATE_URL")
):
    print(
        "ERROR: Database host points to localhost inside the container.\n"
        "Link Railway Postgres to this web service — do not use POSTGRES_HOST=localhost.",
        file=sys.stderr,
    )
    sys.exit(1)
PY

# PostGIS is required for django.contrib.gis (safe if extension already exists).
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('CREATE EXTENSION IF NOT EXISTS postgis;')
" || true

for attempt in 1 2 3 4 5; do
  if python manage.py migrate --noinput; then
    break
  fi
  if [ "$attempt" -eq 5 ]; then
    echo "ERROR: migrate failed after 5 attempts."
    exit 1
  fi
  echo "migrate failed (attempt $attempt), retrying in 5s..."
  sleep 5
done

python manage.py seed_nashik || true
python manage.py seed_roles || true
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); u,_=U.objects.update_or_create(phone='9175504999', defaults={'role':U.Role.DRIVER,'is_active':True,'is_phone_verified':True,'city':'Nashik'}); u.set_password('Tran@123'); u.save(update_fields=['password']); print('driver-ready', u.phone)" || true
exec "$@"
