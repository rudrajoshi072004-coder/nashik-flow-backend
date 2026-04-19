#!/bin/sh
set -e
# Phones call http://<PC-LAN-IP>:<port> — narrow .env values cause DisallowedHost before Django starts.
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"

python manage.py migrate --noinput
python manage.py seed_nashik || true
python manage.py runserver 0.0.0.0:8000
