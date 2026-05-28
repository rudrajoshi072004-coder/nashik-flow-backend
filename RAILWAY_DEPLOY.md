# Deploy nashik-flow-backend on Railway

## PostGIS is required (important)

This backend uses **PostGIS** for locations, zones, and dispatch distance queries.

**Railway's default PostgreSQL service does not include PostGIS.**  
If you see:

`extension "postgis" is not available`

you must use a **PostGIS-enabled** database, not standard Postgres.

### Recommended: Railway PostGIS template

1. In your Railway project click **+ New** → **Deploy template**
2. Search **PostGIS** or open: https://railway.com/deploy/postgis-spatial-database
3. Deploy it (image `postgis/postgis:17-3.5`)
4. On your **Django web service** → **Variables** → reference **`DATABASE_PRIVATE_URL`** from the **PostGIS** service (not the old Postgres service)
5. Delete variable references to the old standard Postgres service
6. Redeploy the web service

### Alternative: Supabase Postgres on Railway

https://railway.com/deploy/supabase-postgres-1 — then run `CREATE EXTENSION IF NOT EXISTS postgis;` in the DB if needed.

## Database connection

Link Postgres variables to the web service:

- `DATABASE_PRIVATE_URL` (preferred, same project)
- or `DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`

Do **not** set `POSTGRES_HOST=localhost`.

## App variables

See `.env.railway.example`. Minimum:

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=false`
- `DJANGO_ALLOWED_HOSTS=*.up.railway.app`

## Deploy

- Root directory: `nashik-flow-backend` (monorepo)
- Uses `Dockerfile` / `railway.toml`
- Entrypoint runs `migrate` after PostGIS check

## Verify

```bash
curl https://YOUR-RAILWAY-URL/api/v1/health
```
