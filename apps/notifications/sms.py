"""Send login OTP SMS (MSG91 or Fast2SMS)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def _ten_digit_msisdn(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) >= 12:
        return digits[-10:]
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def _send_msg91(mobile10: str, otp: str) -> bool:
    authkey = (getattr(settings, "MSG91_AUTH_KEY", "") or "").strip()
    template_id = (getattr(settings, "MSG91_TEMPLATE_ID", "") or "").strip()
    if not authkey:
        return False
    mobile = f"91{mobile10}"
    query = {"mobile": mobile, "otp": otp, "authkey": authkey}
    if template_id:
        query["template_id"] = template_id
    url = f"https://control.msg91.com/api/v5/otp?{urllib.parse.urlencode(query)}"
    body = json.dumps({"otp": otp, "otp_expiry": 5}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"authkey": authkey, "accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        logger.info("MSG91 OTP response: %s", raw[:300])
        return True
    except urllib.error.HTTPError as exc:
        logger.error("MSG91 OTP failed: %s %s", exc.code, exc.read().decode("utf-8", errors="replace")[:300])
        return False
    except Exception:
        logger.exception("MSG91 OTP send failed")
        return False


def _send_fast2sms(mobile10: str, otp: str) -> bool:
    api_key = (getattr(settings, "FAST2SMS_API_KEY", "") or "").strip()
    if not api_key:
        return False
    params = {
        "authorization": api_key,
        "route": "otp",
        "variables_values": otp,
        "flash": "0",
        "numbers": mobile10,
    }
    url = f"https://www.fast2sms.com/dev/bulkV2?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"cache-control": "no-cache"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        logger.info("Fast2SMS OTP response: %s", raw[:300])
        data = json.loads(raw) if raw.strip().startswith("{") else {}
        return bool(data.get("return", True))
    except Exception:
        logger.exception("Fast2SMS OTP send failed")
        return False


def send_otp_sms(phone: str, otp: str) -> bool:
    mobile10 = _ten_digit_msisdn(phone)
    if len(mobile10) != 10:
        logger.warning("OTP SMS skipped: invalid phone %s", phone)
        return False
    if (getattr(settings, "MSG91_AUTH_KEY", "") or "").strip():
        return _send_msg91(mobile10, otp)
    if (getattr(settings, "FAST2SMS_API_KEY", "") or "").strip():
        return _send_fast2sms(mobile10, otp)
    logger.warning("OTP SMS skipped: set MSG91_AUTH_KEY (+ MSG91_TEMPLATE_ID) or FAST2SMS_API_KEY")
    return False
