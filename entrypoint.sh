#!/bin/sh
set -e
# Phones call http://<PC-LAN-IP>:<port> — narrow .env values cause DisallowedHost before Django starts.
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"
export PORT="${PORT:-8000}"

python manage.py migrate --noinput
python manage.py seed_nashik || true
exec "$@"
