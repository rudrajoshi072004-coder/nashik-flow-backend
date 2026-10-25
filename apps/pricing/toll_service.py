"""
Toll Gate Estimation & Compliant 30-Day Caching Service.

Uses Google Maps Routes API (with FASTag passes) and clusters routes via 5-character
Geohashes (~4.9km boxes) to avoid redundant API billing.
Complies with Google Maps Platform 30-day caching policy while providing high performance.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import json
import logging
from typing import Any
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

from apps.pricing.models import RouteTollCache

logger = logging.getLogger(__name__)

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
GOOGLE_ROUTES_COMPUTE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def encode_geohash(latitude: float, longitude: float, precision: int = 5) -> str:
    """
    Standard base32 geohash encoder without external C-extensions.
    Precision 5 yields a bounding box of ~4.9km x ~4.9km, ideal for city highway exit/entry corridors.
    """
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True

    while len(geohash) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if longitude > mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if latitude > mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(BASE32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)


def fetch_google_routes_toll(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    category_slug: str = "",
) -> dict[str, Any] | None:
    """
    Calls Google Maps Routes API with extraComputations: ["TOLLS"] and IN_FASTAG pass.
    Returns parsed toll info or None if unavailable.
    """
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        logger.warning("GOOGLE_MAPS_API_KEY is not configured. Toll calculation skipped.")
        return None

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": float(origin_lat),
                    "longitude": float(origin_lng),
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": float(dest_lat),
                    "longitude": float(dest_lng),
                }
            }
        },
        "travelMode": "DRIVE",
        "extraComputations": ["TOLLS"],
        "routeModifiers": {
            "vehicleInfo": {"emissionType": "GASOLINE"},
            "tollPasses": ["IN_FASTAG"],
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.travelAdvisory.tollInfo,routes.duration,routes.distanceMeters",
    }

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(GOOGLE_ROUTES_COMPUTE_URL, data=req_data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=6) as response:
            resp_bytes = response.read()
            resp_json = json.loads(resp_bytes.decode("utf-8"))

        routes = resp_json.get("routes", [])
        if not routes:
            return {
                "toll_amount": Decimal("0.00"),
                "currency": "INR",
                "has_tolls": False,
                "toll_details": [],
                "source": RouteTollCache.Source.GOOGLE_ROUTES,
            }

        first_route = routes[0]
        travel_advisory = first_route.get("travelAdvisory", {})
        toll_info = travel_advisory.get("tollInfo", {})
        estimated_prices = toll_info.get("estimatedPrice", [])

        if not estimated_prices:
            # Route found, but has no tolls
            return {
                "toll_amount": Decimal("0.00"),
                "currency": "INR",
                "has_tolls": False,
                "toll_details": [],
                "source": RouteTollCache.Source.GOOGLE_ROUTES,
            }

        total_toll = Decimal("0.00")
        currency_code = "INR"

        for price_entry in estimated_prices:
            curr = price_entry.get("currencyCode") or "INR"
            currency_code = curr
            units = int(price_entry.get("units") or 0)
            nanos = int(price_entry.get("nanos") or 0)
            toll_val = Decimal(str(units)) + (Decimal(str(nanos)) / Decimal("1000000000"))
            total_toll += toll_val

        total_toll = total_toll.quantize(Decimal("0.01"))
        return {
            "toll_amount": total_toll,
            "currency": currency_code,
            "has_tolls": total_toll > Decimal("0.00"),
            "toll_details": estimated_prices,
            "source": RouteTollCache.Source.GOOGLE_ROUTES,
        }

    except urllib.error.HTTPError as http_err:
        try:
            err_body = http_err.read().decode("utf-8")
            logger.error("Google Routes API HTTP error %s: %s", http_err.code, err_body)
        except Exception:
            logger.error("Google Routes API HTTP error %s", http_err.code)
        return None
    except Exception as exc:
        logger.error("Failed to query Google Routes API for tolls: %s", exc)
        return None


def _get_redis_client():
    try:
        from apps.tracking.redis_geo import get_redis_client
        return get_redis_client()
    except Exception:
        return None


def get_or_fetch_route_toll(
    *,
    pickup_lat: float,
    pickup_lng: float,
    drop_lat: float,
    drop_lng: float,
    category: Any = None,
    origin_name: str = "",
    dest_name: str = "",
) -> dict[str, Any]:
    """
    Returns estimated toll fee for a trip.
    Lookup sequence:
      1. Redis cache (sub-millisecond)
      2. Database RouteTollCache (active & unexpired, or manual override)
      3. Google Maps Routes API (if miss/expired) -> writes to DB & Redis with 30-day TTL
      4. Expired DB fallback or Decimal("0.00")
    """
    enabled = getattr(settings, "ENABLE_TOLL_CALCULATION", True)
    if not enabled:
        return {
            "toll_amount": Decimal("0.00"),
            "currency": "INR",
            "has_tolls": False,
            "source": "disabled",
            "cached": False,
        }

    origin_gh = encode_geohash(pickup_lat, pickup_lng, precision=5)
    dest_gh = encode_geohash(drop_lat, drop_lng, precision=5)
    category_slug = (
        (getattr(category, "name", "") or "").strip().lower().replace(" ", "_")
        if category
        else ""
    )

    redis_key = f"toll:{origin_gh}:{dest_gh}:{category_slug or 'default'}"
    ttl_days = getattr(settings, "TOLL_CACHE_TTL_DAYS", 30)

    # 1. Check Redis Cache
    redis_client = _get_redis_client()
    if redis_client:
        try:
            cached_val = redis_client.get(redis_key)
            if cached_val:
                data = json.loads(cached_val.decode("utf-8") if isinstance(cached_val, bytes) else cached_val)
                data["toll_amount"] = Decimal(str(data.get("toll_amount", "0.00")))
                data["cached"] = True
                return data
        except Exception as exc:
            logger.debug("Redis toll read failed: %s", exc)

    # 2. Check Database Cache
    now = timezone.now()
    db_cache = (
        RouteTollCache.objects.filter(
            origin_geohash=origin_gh,
            destination_geohash=dest_gh,
            vehicle_category_slug=category_slug,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )

    # Check generic category fallback if specific not found
    if not db_cache and category_slug:
        db_cache = (
            RouteTollCache.objects.filter(
                origin_geohash=origin_gh,
                destination_geohash=dest_gh,
                vehicle_category_slug="",
                is_active=True,
            )
            .order_by("-updated_at")
            .first()
        )

    # If DB record is valid (not expired or is a manual override)
    if db_cache and (db_cache.expires_at > now or db_cache.source == RouteTollCache.Source.MANUAL_OVERRIDE):
        result = {
            "toll_amount": db_cache.toll_amount,
            "currency": db_cache.currency,
            "has_tolls": db_cache.has_tolls,
            "source": db_cache.source,
            "cached": True,
            "origin_geohash": db_cache.origin_geohash,
            "destination_geohash": db_cache.destination_geohash,
        }
        # Populate Redis
        if redis_client:
            try:
                remaining_seconds = max(60, int((db_cache.expires_at - now).total_seconds()))
                payload = {**result, "toll_amount": str(result["toll_amount"])}
                redis_client.setex(redis_key, remaining_seconds, json.dumps(payload))
            except Exception:
                pass
        return result

    # 3. Cache Miss / Expired: Call Google Routes API
    api_result = fetch_google_routes_toll(
        origin_lat=pickup_lat,
        origin_lng=pickup_lng,
        dest_lat=drop_lat,
        dest_lng=drop_lng,
        category_slug=category_slug,
    )

    if api_result is not None:
        expires_at = now + timedelta(days=ttl_days)
        toll_amt = api_result["toll_amount"]
        has_tolls = api_result["has_tolls"]

        # Persist to PostgreSQL
        try:
            cat_obj = category if hasattr(category, "id") else None
            RouteTollCache.objects.update_or_create(
                origin_geohash=origin_gh,
                destination_geohash=dest_gh,
                vehicle_category_slug=category_slug,
                defaults={
                    "origin_name": origin_name or f"Zone {origin_gh}",
                    "destination_name": dest_name or f"Zone {dest_gh}",
                    "vehicle_category": cat_obj,
                    "toll_amount": toll_amt,
                    "currency": api_result.get("currency", "INR"),
                    "has_tolls": has_tolls,
                    "toll_details": api_result.get("toll_details", []),
                    "source": RouteTollCache.Source.GOOGLE_ROUTES,
                    "is_active": True,
                    "expires_at": expires_at,
                },
            )
        except Exception as exc:
            logger.warning("Failed to save RouteTollCache to DB: %s", exc)

        # Persist to Redis
        if redis_client:
            try:
                redis_payload = {
                    "toll_amount": str(toll_amt),
                    "currency": api_result.get("currency", "INR"),
                    "has_tolls": has_tolls,
                    "source": RouteTollCache.Source.GOOGLE_ROUTES,
                    "cached": False,
                }
                redis_client.setex(redis_key, ttl_days * 86400, json.dumps(redis_payload))
            except Exception:
                pass

        return {
            "toll_amount": toll_amt,
            "currency": api_result.get("currency", "INR"),
            "has_tolls": has_tolls,
            "source": RouteTollCache.Source.GOOGLE_ROUTES,
            "cached": False,
            "origin_geohash": origin_gh,
            "destination_geohash": dest_gh,
        }

    # 4. Fallback if API call failed
    if db_cache:
        logger.info("Using expired DB toll cache as fallback for %s -> %s", origin_gh, dest_gh)
        return {
            "toll_amount": db_cache.toll_amount,
            "currency": db_cache.currency,
            "has_tolls": db_cache.has_tolls,
            "source": "expired_cache_fallback",
            "cached": True,
        }

    return {
        "toll_amount": Decimal("0.00"),
        "currency": "INR",
        "has_tolls": False,
        "source": "none",
        "cached": False,
    }


def clear_route_toll_cache() -> int:
    """Flushes active toll cache in Redis and marks records expired in DB."""
    redis_client = _get_redis_client()
    if redis_client:
        try:
            keys = redis_client.keys("toll:*")
            if keys:
                redis_client.delete(*keys)
        except Exception as exc:
            logger.warning("Failed to clear Redis toll keys: %s", exc)

    count = RouteTollCache.objects.filter(is_active=True).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    return count
