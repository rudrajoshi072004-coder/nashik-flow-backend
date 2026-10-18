from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class GlobalAnonRateThrottle(AnonRateThrottle):
    scope = "anon"


class GlobalUserRateThrottle(UserRateThrottle):
    scope = "user"


class OTPRequestRateThrottle(SimpleRateThrottle):
    """
    Stops SMS bomb attacks and protects SMS gateway balance (MSG91 / Fast2SMS).
    Limits OTP requests per client IP and phone number.
    """
    scope = "otp_request"

    def get_cache_key(self, request, view):
        phone = (request.data.get("phone") or "").strip() if hasattr(request, "data") else ""
        ident = self.get_ident(request)
        if phone:
            return f"throttle:otp_req:{ident}:{phone}"
        return f"throttle:otp_req:{ident}"


class OTPVerifyRateThrottle(SimpleRateThrottle):
    """
    Stops brute-forcing 4-digit or 6-digit OTP codes.
    """
    scope = "otp_verify"

    def get_cache_key(self, request, view):
        phone = (request.data.get("phone") or "").strip() if hasattr(request, "data") else ""
        ident = self.get_ident(request)
        if phone:
            return f"throttle:otp_verify:{ident}:{phone}"
        return f"throttle:otp_verify:{ident}"


class FareEstimateRateThrottle(SimpleRateThrottle):
    """
    Protects routing calculations (OSRM / Google Maps) from bot scraping and spam.
    """
    scope = "fare_estimate"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle:fare:{request.user.id}"
        return f"throttle:fare:{self.get_ident(request)}"


class DriverLocationRateThrottle(SimpleRateThrottle):
    """
    Prevents background battery-draining phone loops from spamming GPS updates.
    Allows up to 60 location pings/minute (1 per second max).
    """
    scope = "driver_location"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle:driver_loc:{request.user.id}"
        return f"throttle:driver_loc:{self.get_ident(request)}"
