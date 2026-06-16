#!/usr/bin/env python3
"""
Build Railway environment variables from your PostgreSQL inputs.

Usage:
  python scripts/railway-postgres-boilerplate.py

Or non-interactive:
  python scripts/railway-postgres-boilerplate.py \\
    --host metro.proxy.rlwy.net --port 5432 --user postgres \\
    --password 'your-secret' --database railway \\
    --allowed-hosts '*.up.railway.app'
"""

from __future__ import annotations

import argparse
import secrets
import sys
from urllib.parse import quote_plus


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def build_database_url(host: str, port: str, user: str, password: str, database: str) -> str:
    safe_user = quote_plus(user)
    safe_password = quote_plus(password)
    return f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{database}"


def render_env(
    *,
    database_url: str,
    pg_host: str,
    pg_port: str,
    pg_user: str,
    pg_password: str,
    pg_database: str,
    django_secret: str,
    allowed_hosts: str,
) -> str:
    lines = [
        "DJANGO_SETTINGS_MODULE=config.settings.production",
        f"DJANGO_SECRET_KEY={django_secret}",
        "DJANGO_DEBUG=false",
        f"DJANGO_ALLOWED_HOSTS={allowed_hosts}",
        "LOG_LEVEL=INFO",
        "JWT_ACCESS_MINUTES=1440",
        "JWT_REFRESH_DAYS=30",
        "",
        f"DATABASE_URL={database_url}",
        f"PGHOST={pg_host}",
        f"PGPORT={pg_port}",
        f"PGUSER={pg_user}",
        f"PGPASSWORD={pg_password}",
        f"PGDATABASE={pg_database}",
        "POSTGRES_SSLMODE=require",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Railway Postgres env boilerplate")
    parser.add_argument("--host", help="PGHOST from Railway")
    parser.add_argument("--port", default="5432", help="PGPORT")
    parser.add_argument("--user", default="postgres", help="PGUSER")
    parser.add_argument("--password", help="PGPASSWORD")
    parser.add_argument("--database", default="railway", help="PGDATABASE")
    parser.add_argument("--django-secret", help="DJANGO_SECRET_KEY (generated if omitted)")
    parser.add_argument("--allowed-hosts", default="*.up.railway.app", help="DJANGO_ALLOWED_HOSTS")
    args = parser.parse_args()

    interactive = not args.host or not args.password
    if interactive:
        print("=== Railway PostgreSQL → env boilerplate ===\n")
        print("Copy values from: Railway → PostgreSQL → Variables\n")

    host = args.host or _prompt("PGHOST")
    port = args.port or _prompt("PGPORT", "5432")
    user = args.user or _prompt("PGUSER", "postgres")
    password = args.password or _prompt("PGPASSWORD")
    database = args.database or _prompt("PGDATABASE", "railway")
    django_secret = args.django_secret or _prompt(
        "DJANGO_SECRET_KEY (empty = auto-generate)", secrets.token_hex(32)
    )
    if not django_secret:
        django_secret = secrets.token_hex(32)
    allowed_hosts = args.allowed_hosts or _prompt("DJANGO_ALLOWED_HOSTS", "*.up.railway.app")

    database_url = build_database_url(host, port, user, password, database)

    print("\n# --- Paste into Railway → Web service → Variables (Raw Editor) ---\n")
    print(
        render_env(
            database_url=database_url,
            pg_host=host,
            pg_port=port,
            pg_user=user,
            pg_password=password,
            pg_database=database,
            django_secret=django_secret,
            allowed_hosts=allowed_hosts,
        )
    )
    print("\n# Optional: use DATABASE_PRIVATE_URL from Postgres plugin instead of DATABASE_URL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
