# Railway database variables — fix localhost error

## Symptom

```
connection to server at "127.0.0.1", port 5432 failed: Connection refused
```

## Cause

- `DATABASE_URL` on **nashik-flow-backend** points to `postgis.railway.internal` (wrong project), or
- `DATABASE_PUBLIC_URL` was **copy-pasted incorrectly** (broken host), or
- Only `POSTGRES_USER` / `POSTGRES_PASSWORD` without a full URL

## Fix (5 minutes)

### 1. Open PostGIS (`adventurous-solace` → PostGIS → Variables)

Click **eye** on **`DATABASE_PUBLIC_URL`**.

Copy the **entire** line. It must contain:

- `postgresql://`
- `@SOMETHING.proxy.rlwy.net:PORT/postgis_db`

### 2. Open backend (`ravishing-energy` → nashik-flow-backend → Variables)

| Action | Variable |
|--------|----------|
| **Delete** | `DATABASE_PUBLIC_URL` (optional) |
| **Delete** | `PGDATA`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` if present |
| **Edit** | `DATABASE_URL` → paste the PostGIS `DATABASE_PUBLIC_URL` value exactly |

### 3. Verify `DATABASE_URL` on backend

| Must have | Must NOT have |
|-----------|----------------|
| `proxy.rlwy.net` | `localhost` |
| `:PORT` before `/postgis_db` | `postgis.railway.internal` |
| | `@://` |

### 4. Push code + redeploy

Commit and push so Railway rebuilds with the updated `entrypoint.sh`, then **Redeploy**.

### 5. Check deploy logs

You should see:

```
Using DATABASE_URL host: 'xxxx.proxy.rlwy.net'
Database target host: xxxx.proxy.rlwy.net
```

You must **not** see `127.0.0.1` or `localhost`.

## Best long-term

Deploy PostGIS inside **ravishing-energy** (same project as backend) and use a variable reference for `DATABASE_URL`.
