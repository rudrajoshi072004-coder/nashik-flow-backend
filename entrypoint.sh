#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py seed_nashik || true
python manage.py runserver 0.0.0.0:8000
