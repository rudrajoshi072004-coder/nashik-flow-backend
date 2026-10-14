from __future__ import annotations

import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

_r2_client = None


def is_r2_configured() -> bool:
    """Return True if Cloudflare R2 credentials and bucket are configured."""
    return bool(
        getattr(settings, "CLOUDFLARE_R2_ACCOUNT_ID", None)
        and getattr(settings, "CLOUDFLARE_R2_ACCESS_KEY_ID", None)
        and getattr(settings, "CLOUDFLARE_R2_SECRET_ACCESS_KEY", None)
        and getattr(settings, "CLOUDFLARE_R2_BUCKET_NAME", None)
    )


def get_r2_client():
    """Return a cached boto3 S3 client configured for Cloudflare R2."""
    global _r2_client
    if _r2_client is not None:
        return _r2_client

    if not is_r2_configured():
        return None

    try:
        import boto3
        from botocore.config import Config

        endpoint_url = getattr(
            settings,
            "CLOUDFLARE_R2_ENDPOINT_URL",
            f"https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        )

        _r2_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        return _r2_client
    except Exception as exc:
        logger.exception("Failed to initialize Cloudflare R2 client: %s", exc)
        return None


def get_public_url(key: str) -> str:
    """Return the public CDN URL for a key if a custom domain is configured."""
    clean_key = (key or "").lstrip("/")
    custom_domain = getattr(settings, "CLOUDFLARE_R2_CUSTOM_DOMAIN", "")
    if custom_domain:
        return f"{custom_domain}/{clean_key}"
    return f"/media/r2/{clean_key}"


def upload_bytes_to_r2(
    key: str,
    data: bytes,
    content_type: str = "image/jpeg",
) -> Optional[str]:
    """Upload raw bytes to Cloudflare R2 at the specified key.

    Returns the object key on success, or None on failure/unconfigured.
    """
    clean_key = (key or "").lstrip("/")
    client = get_r2_client()
    if not client:
        logger.warning("R2 is not configured; skipping upload for key %s", clean_key)
        return None

    bucket = getattr(settings, "CLOUDFLARE_R2_BUCKET_NAME", "carryyo")
    content_type = (content_type or "image/jpeg").split(";")[0].strip()

    try:
        client.put_object(
            Bucket=bucket,
            Key=clean_key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("Successfully uploaded %d bytes to R2: %s", len(data), clean_key)
        return clean_key
    except Exception as exc:
        logger.exception("Failed to upload object to R2 (%s): %s", clean_key, exc)
        return None


def generate_presigned_url(key: str, expires_in: int = 900) -> Optional[str]:
    """Generate a temporary pre-signed GET URL for secure access (default: 15 minutes)."""
    clean_key = (key or "").lstrip("/")
    if not clean_key:
        return None

    # If key is already a full external URL (e.g. legacy http/https), return as is
    if clean_key.startswith("http://") or clean_key.startswith("https://"):
        return clean_key

    client = get_r2_client()
    if not client:
        # Fall back to custom domain public URL if configured
        custom_domain = getattr(settings, "CLOUDFLARE_R2_CUSTOM_DOMAIN", "")
        if custom_domain:
            return f"{custom_domain}/{clean_key}"
        return None

    bucket = getattr(settings, "CLOUDFLARE_R2_BUCKET_NAME", "carryyo")
    try:
        url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": clean_key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        logger.exception("Failed to generate presigned URL for %s: %s", clean_key, exc)
        return None


def delete_r2_object(key: str) -> bool:
    """Delete an object from Cloudflare R2."""
    clean_key = (key or "").lstrip("/")
    if not clean_key:
        return False

    client = get_r2_client()
    if not client:
        return False

    bucket = getattr(settings, "CLOUDFLARE_R2_BUCKET_NAME", "carryyo")
    try:
        client.delete_object(Bucket=bucket, Key=clean_key)
        return True
    except Exception as exc:
        logger.exception("Failed to delete object from R2 (%s): %s", clean_key, exc)
        return False
