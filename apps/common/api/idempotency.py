import hashlib
import json
import logging
from typing import Any, Callable

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

IDEMPOTENCY_KEY_HEADER = "HTTP_X_IDEMPOTENCY_KEY"
ALT_IDEMPOTENCY_KEY_HEADER = "HTTP_IDEMPOTENCY_KEY"
DEFAULT_EXPIRY_SECONDS = 60


def get_idempotency_key(request) -> str | None:
    key = request.META.get(IDEMPOTENCY_KEY_HEADER) or request.META.get(ALT_IDEMPOTENCY_KEY_HEADER)
    if key:
        return str(key).strip()
    return None


def generate_dedupe_fingerprint(user_id: Any, path: str, payload: dict) -> str:
    """Generate a deterministic hash for deduplicating identical rapid requests."""
    try:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    except Exception:
        serialized = str(payload)
    raw = f"{user_id}:{path}:{serialized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def check_and_set_idempotency_lock(cache_key: str, expiry: int = DEFAULT_EXPIRY_SECONDS) -> bool:
    """
    Acquires an atomic in-flight lock for the given idempotency key.
    Returns True if lock acquired, False if key is already processing or completed.
    """
    lock_key = f"idempotency:lock:{cache_key}"
    # set nx=True with short TTL (15s) for in-flight processing
    try:
        return bool(cache.add(lock_key, "processing", timeout=15))
    except Exception:
        return True


def release_idempotency_lock(cache_key: str) -> None:
    try:
        cache.delete(f"idempotency:lock:{cache_key}")
    except Exception:
        pass


def get_cached_idempotency_response(cache_key: str) -> dict | None:
    try:
        return cache.get(f"idempotency:resp:{cache_key}")
    except Exception:
        return None


def store_idempotency_response(cache_key: str, response_data: Any, status_code: int, expiry: int = DEFAULT_EXPIRY_SECONDS) -> None:
    try:
        cache.set(
            f"idempotency:resp:{cache_key}",
            {"data": response_data, "status": status_code},
            timeout=expiry,
        )
        release_idempotency_lock(cache_key)
    except Exception:
        pass
