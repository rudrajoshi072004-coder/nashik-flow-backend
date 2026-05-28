# Deploy nashik-flow-backend on Railway

## Why deploy was crashing

Django tried to connect to `127.0.0.1:5432` because **no Railway Postgres variables were linked** to the web service. The container has no local Postgres.

## Fill in your Postgres values (boilerplate)

1. Edit **`.env.railway.example`** — replace every `YOUR_*` with values from Railway Postgres → Variables.
2. Or run the generator (prints ready-to-paste env block):
   ```bash
   cd nashik-flow-backend
   python3 scripts/railway-postgres-boilerplate.py
   ```
   ```bash
   sh scripts/railway-postgres-boilerplate.sh
   ```

## One-time Railway setup

1. Create a **PostgreSQL** service in the same Railway project.
2. Open your **web service** → **Variables** → **Add variable reference** (or "Connect"):
   - Reference `DATABASE_PRIVATE_URL` from Postgres (recommended), **or**
   - Reference `DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`.
3. **Remove** any manual vars like `POSTGRES_HOST=localhost` or `127.0.0.1`.
4. Set required app variables (see `.env.railway.example`):
   - `DJANGO_SETTINGS_MODULE=config.settings.production`
   - `DJANGO_SECRET_KEY` (long random string)
   - `DJANGO_DEBUG=false`
   - `DJANGO_ALLOWED_HOSTS=*.up.railway.app,your-domain.com`
5. **Root directory**: set Railway service root to `nashik-flow-backend` (if deploying from monorepo).
6. Deploy using the **Dockerfile** (see `railway.toml`).

## PostGIS

The entrypoint runs `CREATE EXTENSION IF NOT EXISTS postgis` before migrations. Railway Postgres supports this on standard plans.

## Verify after deploy

```bash
curl https://YOUR-RAILWAY-URL/api/v1/health
```

Update customer app `app.json` `apiBaseUrl` / `wsBaseUrl` to your new Railway URL.

## Optional Redis

Add a Redis plugin and reference `REDIS_URL` for Celery/channels. Without Redis, the app still runs (in-memory cache/Celery eager mode).
