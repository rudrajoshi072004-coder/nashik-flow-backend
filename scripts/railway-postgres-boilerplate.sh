#!/usr/bin/env sh
# Interactive boilerplate: enter Railway Postgres values → prints env vars for Railway dashboard.
# Usage: sh scripts/railway-postgres-boilerplate.sh

set -e

echo "=== Nashik Flow — Railway PostgreSQL boilerplate ==="
echo "Get values from: Railway → PostgreSQL service → Variables"
echo ""

printf "PGHOST (e.g. metro.proxy.rlwy.net): "
read -r PGHOST
printf "PGPORT [5432]: "
read -r PGPORT
PGPORT=${PGPORT:-5432}
printf "PGUSER [postgres]: "
read -r PGUSER
PGUSER=${PGUSER:-postgres}
printf "PGPASSWORD: "
read -r PGPASSWORD
printf "PGDATABASE [railway]: "
read -r PGDATABASE
PGDATABASE=${PGDATABASE:-railway}

printf "DJANGO_SECRET_KEY (leave empty to skip): "
read -r DJANGO_SECRET_KEY
printf "DJANGO_ALLOWED_HOSTS [*.up.railway.app]: "
read -r DJANGO_ALLOWED_HOSTS
DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS:-*.up.railway.app}

# URL-encode password for connection string (basic: warn on special chars)
DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT}/${PGDATABASE}"

echo ""
echo "========== Copy below into Railway → Web service → Variables =========="
echo ""
cat <<EOF
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY:-REPLACE_WITH_openssl_rand_hex_32}
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS}
LOG_LEVEL=INFO

DATABASE_URL=${DATABASE_URL}
PGHOST=${PGHOST}
PGPORT=${PGPORT}
PGUSER=${PGUSER}
PGPASSWORD=${PGPASSWORD}
PGDATABASE=${PGDATABASE}
POSTGRES_SSLMODE=require
EOF
echo ""
echo "========== Or use only DATABASE_URL (app supports both) =========="
echo "DATABASE_URL=${DATABASE_URL}"
echo ""
echo "Tip: Prefer referencing DATABASE_PRIVATE_URL from Postgres plugin instead of pasting secrets."
