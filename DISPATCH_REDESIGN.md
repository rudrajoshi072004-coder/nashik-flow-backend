# Redis GEO dispatch redesign

Production dispatch now uses **Redis GEO** as the primary live-location index.

## What changed

| Area | Change |
|------|--------|
| `apps/tracking/redis_geo.py` | `GEOADD`, metadata TTL (45s), `GEORADIUS` search |
| `apps/tracking/services.py` | Writes Redis on every location update (WS + REST) |
| `apps/dispatch/matching.py` | Redis-first ring matching; PostGIS fallback if Redis unavailable |
| `apps/dispatch/offer_delivery.py` | Assignment locks, offer ack keys, FCM scheduling |
| `apps/dispatch/services.py` | Registers ack + schedules FCM after WebSocket offer |
| `apps/dispatch/tasks.py` | `send_fcm_offer_fallback` Celery task |
| `apps/tracking/consumers.py` | `ping`/`pong`, `driver_offer_ack` |
| `apps/drivers/api.py` | `POST /drivers/me/fcm-token/`, remove GEO on offline |
| `apps/users` | `fcm_token` field on User |
| `apps/notifications/fcm.py` | Firebase Admin push |

## Notification layers

1. **WebSocket** — `driver_assigned` with `offer: true`
2. **FCM** — if no `driver_offer_ack` within `OFFER_ACK_WAIT_SECONDS` (default 4s)
3. **REST poll** — driver app `GET /drivers/me/bookings/` every 5s

## Railway variables

```
DISPATCH_RADIUS_KM=10
DRIVER_LOCATION_TTL_SECONDS=45
OFFER_WINDOW_SECONDS=30
OFFER_ACK_WAIT_SECONDS=4
FIREBASE_SERVICE_ACCOUNT_PATH=/app/firebase-service-account.json
```

Run `python manage.py migrate` after deploy for `users_user.fcm_token`.
