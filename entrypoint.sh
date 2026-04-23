#!/bin/sh
set -e
# Phones call http://<PC-LAN-IP>:<port> — narrow .env values cause DisallowedHost before Django starts.
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"
export PORT="${PORT:-8000}"

python manage.py migrate --noinput
python manage.py seed_nashik || true
python manage.py seed_roles || true
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); u,_=U.objects.update_or_create(phone='9175504999', defaults={'role':U.Role.DRIVER,'is_active':True,'is_phone_verified':True,'city':'Nashik'}); u.set_password('Tran@123'); u.save(update_fields=['password']); print('driver-ready', u.phone)" || true
exec "$@"
