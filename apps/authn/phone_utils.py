"""Normalize Indian phone numbers and match legacy DB formats (+91…, 91…, 10-digit)."""

from __future__ import annotations


def normalize_phone_e164(raw: str) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not digits:
        return str(raw or "").strip()
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    if str(raw or "").strip().startswith("+"):
        return str(raw).strip()
    return f"+{digits}"


def phone_lookup_variants(raw: str) -> list[str]:
    """All plausible stored forms for the same subscriber number."""
    normalized = normalize_phone_e164(raw)
    variants: set[str] = set()
    if normalized:
        variants.add(normalized)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    if not digits:
        stripped = str(raw or "").strip()
        if stripped:
            variants.add(stripped)
        return sorted(variants)
    variants.add(digits)
    if digits.startswith("91") and len(digits) == 12:
        variants.add(digits[2:])
    if len(digits) == 10:
        variants.add(f"91{digits}")
    return sorted(variants)


def find_user_by_phone(user_model, raw_phone: str):
    """Return (user | None, canonical E.164 phone for new sign-ups)."""
    canonical = normalize_phone_e164(raw_phone)
    user = user_model.objects.filter(phone__in=phone_lookup_variants(raw_phone)).first()
    return user, canonical