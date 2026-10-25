from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.authn.phone_utils import find_user_by_phone
from apps.bookings.models import Booking
from apps.drivers.models import DriverProfile
from apps.tracking.models import DriverLiveLocation
from apps.users.models import User

from .models import FleetDriverMembership, FleetOwnerProfile

ACTIVE_TRIP_STATES = {
    Booking.BookingState.DRIVER_ACCEPTED,
    Booking.BookingState.DRIVER_ARRIVING,
    Booking.BookingState.DRIVER_ARRIVED,
    Booking.BookingState.PICKUP_OTP_PENDING,
    Booking.BookingState.TRIP_STARTED,
    Booking.BookingState.IN_TRANSIT,
    Booking.BookingState.NEARING_DROP,
    Booking.BookingState.PAYMENT_PENDING,
}

BLOCKED_OWNER_ROLES = {
    User.Role.CUSTOMER,
    User.Role.DRIVER,
    User.Role.FLEET_DRIVER,
    User.Role.CITY_MANAGER,
    User.Role.SUPPORT_AGENT,
    User.Role.FINANCE_ADMIN,
    User.Role.SUPER_ADMIN,
}


def ensure_owner_profile(user) -> FleetOwnerProfile:
    profile, _ = FleetOwnerProfile.objects.get_or_create(
        user=user,
        defaults={"city": getattr(user, "city", "") or "Nashik"},
    )
    return profile


def owner_active_memberships(owner: FleetOwnerProfile):
    return FleetDriverMembership.objects.filter(
        owner=owner,
        is_deleted=False,
        status__in=[
            FleetDriverMembership.Status.INVITED,
            FleetDriverMembership.Status.ACTIVE,
            FleetDriverMembership.Status.SUSPENDED,
        ],
    ).select_related("driver", "driver__user", "driver__live_location")


def _money(value) -> str:
    if value is None:
        return "0.00"
    return f"{Decimal(value):.2f}"


@transaction.atomic
def add_driver_to_fleet(
    *,
    owner: FleetOwnerProfile,
    phone: str,
    driver_name: str = "",
    vehicle_number: str = "",
    vehicle_type: str = "",
    notes: str = "",
) -> FleetDriverMembership:
    existing_user, canonical = find_user_by_phone(User, phone)
    created_user = False
    if existing_user is None:
        existing_user = User.objects.create(
            phone=canonical,
            role=User.Role.FLEET_DRIVER,
            is_active=True,
            is_phone_verified=False,
            city=owner.city or "Nashik",
            first_name=(driver_name or "")[:150],
        )
        created_user = True
    elif existing_user.role == User.Role.FLEET_OWNER:
        raise ValueError("This number belongs to a fleet owner. Use a driver phone number.")
    elif existing_user.role in {User.Role.CUSTOMER} and not DriverProfile.objects.filter(user=existing_user).exists():
        raise ValueError("This number is registered as a customer. Ask the driver to use their driver app number.")

    if existing_user.role not in {User.Role.DRIVER, User.Role.FLEET_DRIVER}:
        existing_user.role = User.Role.FLEET_DRIVER
        existing_user.save(update_fields=["role", "updated_at"])

    driver, _ = DriverProfile.objects.get_or_create(user=existing_user)
    dirty = []
    if driver_name and hasattr(driver, "driver_name") and not driver.driver_name:
        driver.driver_name = driver_name[:128]
        dirty.append("driver_name")
    if vehicle_number and hasattr(driver, "vehicle_number"):
        driver.vehicle_number = vehicle_number[:32]
        dirty.append("vehicle_number")
    if vehicle_type and hasattr(driver, "vehicle_type"):
        driver.vehicle_type = vehicle_type[:32]
        dirty.append("vehicle_type")
    if dirty:
        driver.save(update_fields=dirty + ["updated_at"])

    # Edge Case: Check if driver is already an active member of another fleet
    other_active = (
        FleetDriverMembership.objects.filter(
            driver=driver,
            is_deleted=False,
            status=FleetDriverMembership.Status.ACTIVE,
        )
        .exclude(owner=owner)
        .select_related("owner")
        .first()
    )
    if other_active:
        other_name = other_active.owner.business_name or "another fleet owner"
        raise ValueError(
            f"This driver is currently an active member of {other_name}. "
            "They must be removed from their previous fleet before being added."
        )

    # Check for existing membership under this owner (including soft-deleted or removed)
    membership = FleetDriverMembership.objects.filter(owner=owner, driver=driver).order_by("-created_at").first()
    target_status = (
        FleetDriverMembership.Status.INVITED
        if created_user or driver.kyc_status != DriverProfile.KYCStatus.APPROVED
        else FleetDriverMembership.Status.ACTIVE
    )

    if membership:
        # Idempotency: if already in fleet and active/invited, return it without erroring out
        if not membership.is_deleted and membership.status in {
            FleetDriverMembership.Status.ACTIVE,
            FleetDriverMembership.Status.INVITED,
        }:
            return membership

        membership.is_deleted = False
        membership.status = target_status
        membership.driver_display_name = (driver_name or membership.driver_display_name)[:128]
        membership.vehicle_number = (vehicle_number or membership.vehicle_number)[:32]
        membership.vehicle_type = (vehicle_type or membership.vehicle_type)[:32]
        membership.notes = notes[:255]
        membership.save()
        return membership

    return FleetDriverMembership.objects.create(
        owner=owner,
        driver=driver,
        status=target_status,
        driver_display_name=(
            driver_name
            or (driver.public_display_name() if hasattr(driver, "public_display_name") else "")
            or getattr(driver, "driver_name", "")
            or existing_user.first_name
            or "Driver"
        )[:128],
        vehicle_number=(vehicle_number or getattr(driver, "vehicle_number", ""))[:32],
        vehicle_type=(vehicle_type or getattr(driver, "vehicle_type", ""))[:32],
        notes=notes[:255],
    )


def serialize_membership(membership: FleetDriverMembership, *, today_start) -> dict:
    """Serializes a single driver membership with isolated queries."""
    driver = membership.driver
    try:
        live = getattr(driver, "live_location", None)
    except ObjectDoesNotExist:
        live = None

    on_trip = driver.bookings.filter(is_deleted=False, state__in=ACTIVE_TRIP_STATES).exists()
    today_trips = driver.bookings.filter(
        is_deleted=False, state=Booking.BookingState.COMPLETED, updated_at__gte=today_start
    )
    today_earn = today_trips.aggregate(total=Sum("final_fare"))["total"] or 0
    lat = lng = None
    if live and live.location:
        lat = live.location.y
        lng = live.location.x

    return {
        "id": str(membership.id),
        "driver_id": str(driver.id),
        "status": membership.status,
        "name": membership.driver_display_name
        or (
            driver.public_display_name()
            if hasattr(driver, "public_display_name")
            else (getattr(driver, "driver_name", "") or driver.user.first_name or "Driver")
        ),
        "phone": getattr(driver, "driver_phone", "") or driver.user.phone,
        "vehicle_number": membership.vehicle_number or getattr(driver, "vehicle_number", ""),
        "vehicle_type": membership.vehicle_type or getattr(driver, "vehicle_type", ""),
        "city": getattr(driver, "operation_city", "") or driver.user.city,
        "kyc_status": driver.kyc_status,
        "onboarding_completed": driver.onboarding_completed,
        "is_online": driver.is_online,
        "on_trip": on_trip,
        "rating_avg": str(driver.rating_avg),
        "total_trips": driver.total_trips,
        "today_trips": today_trips.count(),
        "today_earnings": _money(today_earn),
        "lat": lat,
        "lng": lng,
        "notes": membership.notes,
        "already_registered": not (
            membership.status == FleetDriverMembership.Status.INVITED and not driver.onboarding_completed
        ),
    }


def serialize_memberships_batch(memberships, *, today_start) -> list[dict]:
    """
    High-traffic O(1) batch serialization for fleet drivers roster.
    Replaces 3N database queries with 2 batch queries total, regardless of fleet size.
    """
    memberships_list = list(memberships)
    if not memberships_list:
        return []

    driver_ids = [m.driver_id for m in memberships_list]

    # 1. Batch query for all drivers currently on active trips
    active_driver_ids = set(
        Booking.objects.filter(
            is_deleted=False,
            driver_id__in=driver_ids,
            state__in=ACTIVE_TRIP_STATES,
        ).values_list("driver_id", flat=True)
    )

    # 2. Batch query for today's completed trip counts and fare revenue
    today_stats = {
        row["driver_id"]: row
        for row in Booking.objects.filter(
            is_deleted=False,
            driver_id__in=driver_ids,
            state=Booking.BookingState.COMPLETED,
            updated_at__gte=today_start,
        )
        .values("driver_id")
        .annotate(total=Sum("final_fare"), trips=Count("id"))
    }

    results = []
    for m in memberships_list:
        driver = m.driver
        try:
            live = getattr(driver, "live_location", None)
        except ObjectDoesNotExist:
            live = None

        lat = lng = None
        if live and live.location:
            lat = live.location.y
            lng = live.location.x

        stat = today_stats.get(driver.id, {})
        today_earn = stat.get("total") or 0
        today_trips_count = stat.get("trips") or 0
        on_trip = driver.id in active_driver_ids

        results.append(
            {
                "id": str(m.id),
                "driver_id": str(driver.id),
                "status": m.status,
                "name": m.driver_display_name
                or (
                    driver.public_display_name()
                    if hasattr(driver, "public_display_name")
                    else (getattr(driver, "driver_name", "") or driver.user.first_name or "Driver")
                ),
                "phone": getattr(driver, "driver_phone", "") or driver.user.phone,
                "vehicle_number": m.vehicle_number or getattr(driver, "vehicle_number", ""),
                "vehicle_type": m.vehicle_type or getattr(driver, "vehicle_type", ""),
                "city": getattr(driver, "operation_city", "") or driver.user.city,
                "kyc_status": driver.kyc_status,
                "onboarding_completed": driver.onboarding_completed,
                "is_online": driver.is_online,
                "on_trip": on_trip,
                "rating_avg": str(driver.rating_avg),
                "total_trips": driver.total_trips,
                "today_trips": today_trips_count,
                "today_earnings": _money(today_earn),
                "lat": lat,
                "lng": lng,
                "notes": m.notes,
                "already_registered": not (
                    m.status == FleetDriverMembership.Status.INVITED and not driver.onboarding_completed
                ),
            }
        )

    return results


def fleet_dashboard(owner: FleetOwnerProfile) -> dict:
    """Consolidated single-query dashboard metrics avoiding N+1 and repeated DB scans."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    memberships = owner_active_memberships(owner)
    driver_ids = list(memberships.values_list("driver_id", flat=True))

    empty_stats = {"earnings": "0.00", "trips": 0}
    if not driver_ids:
        return {
            "business_name": owner.business_name,
            "onboarding_complete": owner.onboarding_complete,
            "drivers_total": 0,
            "drivers_online": 0,
            "drivers_on_trip": 0,
            "drivers_pending_kyc": 0,
            "live_locations": 0,
            "today": empty_stats,
            "week": empty_stats,
            "month": empty_stats,
            "lifetime": empty_stats,
        }

    drivers = DriverProfile.objects.filter(id__in=driver_ids)
    online = drivers.filter(is_online=True).count()
    on_trip = (
        Booking.objects.filter(is_deleted=False, driver_id__in=driver_ids, state__in=ACTIVE_TRIP_STATES)
        .values("driver_id")
        .distinct()
        .count()
    )
    pending_kyc = drivers.exclude(kyc_status=DriverProfile.KYCStatus.APPROVED).count()

    # Single consolidated aggregate query for today, week, month, and lifetime stats
    completed = Booking.objects.filter(
        is_deleted=False, driver_id__in=driver_ids, state=Booking.BookingState.COMPLETED
    )
    agg = completed.aggregate(
        today_total=Sum("final_fare", filter=Q(updated_at__gte=today_start)),
        today_trips=Count("id", filter=Q(updated_at__gte=today_start)),
        week_total=Sum("final_fare", filter=Q(updated_at__gte=week_start)),
        week_trips=Count("id", filter=Q(updated_at__gte=week_start)),
        month_total=Sum("final_fare", filter=Q(updated_at__gte=month_start)),
        month_trips=Count("id", filter=Q(updated_at__gte=month_start)),
        lifetime_total=Sum("final_fare"),
        lifetime_trips=Count("id"),
    )

    live_count = DriverLiveLocation.objects.filter(driver_id__in=driver_ids).count()
    return {
        "business_name": owner.business_name,
        "onboarding_complete": owner.onboarding_complete,
        "drivers_total": len(driver_ids),
        "drivers_online": online,
        "drivers_on_trip": on_trip,
        "drivers_pending_kyc": pending_kyc,
        "live_locations": live_count,
        "today": {"earnings": _money(agg["today_total"]), "trips": agg["today_trips"] or 0},
        "week": {"earnings": _money(agg["week_total"]), "trips": agg["week_trips"] or 0},
        "month": {"earnings": _money(agg["month_total"]), "trips": agg["month_trips"] or 0},
        "lifetime": {"earnings": _money(agg["lifetime_total"]), "trips": agg["lifetime_trips"] or 0},
    }


def fleet_alerts(owner: FleetOwnerProfile) -> list[dict]:
    alerts: list[dict] = []
    for m in owner_active_memberships(owner):
        d = m.driver
        driver_label = (
            m.driver_display_name
            or (d.public_display_name() if hasattr(d, "public_display_name") else "")
            or getattr(d, "driver_name", "")
            or d.user.first_name
            or "Driver"
        )
        if d.kyc_status != DriverProfile.KYCStatus.APPROVED:
            alerts.append(
                {
                    "type": "kyc",
                    "severity": "warning",
                    "title": f"{driver_label} KYC pending",
                    "body": "Ask the driver to finish documents in the Carryoo Driver app.",
                    "driver_id": str(d.id),
                    "membership_id": str(m.id),
                }
            )
        if m.status == FleetDriverMembership.Status.ACTIVE and not d.is_online:
            alerts.append(
                {
                    "type": "offline",
                    "severity": "info",
                    "title": f"{driver_label} is offline",
                    "body": "They will not receive new trip offers until they go online.",
                    "driver_id": str(d.id),
                    "membership_id": str(m.id),
                }
            )
        if m.status == FleetDriverMembership.Status.SUSPENDED:
            alerts.append(
                {
                    "type": "suspended",
                    "severity": "danger",
                    "title": f"{driver_label} is suspended",
                    "body": "This driver is paused from your fleet until you activate them again.",
                    "driver_id": str(d.id),
                    "membership_id": str(m.id),
                }
            )
    return alerts[:40]


def fleet_trips(owner: FleetOwnerProfile, *, limit: int = 50, driver_id: str | None = None) -> list[dict]:
    driver_ids = list(owner_active_memberships(owner).values_list("driver_id", flat=True))
    if not driver_ids:
        return []

    filters = Q(is_deleted=False)
    if driver_id:
        if driver_id not in [str(did) for did in driver_ids]:
            return []
        filters &= Q(driver_id=driver_id)
    else:
        filters &= Q(driver_id__in=driver_ids)

    rows = (
        Booking.objects.filter(filters)
        .exclude(state__in=[Booking.BookingState.DRAFT, Booking.BookingState.PENDING_QUOTE])
        .select_related("driver", "driver__user")
        .order_by("-updated_at")[:limit]
    )
    out = []
    for b in rows:
        fare = b.final_fare or b.estimated_fare
        out.append(
            {
                "id": str(b.id),
                "state": b.state,
                "trip_type": getattr(b, "trip_type", None) or getattr(b, "booking_type", ""),
                "pickup": b.pickup_address_text,
                "drop": b.drop_address_text,
                "fare": _money(fare),
                "distance_km": str(b.estimated_distance_km or 0),
                "driver_id": str(b.driver_id) if b.driver_id else "",
                "driver_name": (
                    b.driver.public_display_name()
                    if b.driver and hasattr(b.driver, "public_display_name")
                    else (
                        (getattr(b.driver, "driver_name", "") if b.driver else "")
                        or (b.driver.user.first_name if b.driver else "")
                        or "Driver"
                    )
                ),
                "driver_phone": ((getattr(b.driver, "driver_phone", "") or b.driver.user.phone) if b.driver else ""),
                "vehicle_number": (getattr(b.driver, "vehicle_number", "") if b.driver else ""),
                "updated_at": b.updated_at.isoformat(),
            }
        )
    return out


def fleet_earnings(owner: FleetOwnerProfile) -> dict:
    dash = fleet_dashboard(owner)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    memberships = list(owner_active_memberships(owner))
    driver_ids = [m.driver_id for m in memberships]

    if not driver_ids:
        return {
            "today": dash["today"],
            "week": dash["week"],
            "month": dash["month"],
            "lifetime": dash["lifetime"],
            "by_driver": [],
        }

    # High-traffic optimization: batch query per-driver aggregates in a single SQL query
    driver_stats = {
        row["driver_id"]: row
        for row in Booking.objects.filter(
            is_deleted=False,
            driver_id__in=driver_ids,
            state=Booking.BookingState.COMPLETED,
        )
        .values("driver_id")
        .annotate(
            today_total=Sum("final_fare", filter=Q(updated_at__gte=today_start)),
            today_trips=Count("id", filter=Q(updated_at__gte=today_start)),
            lifetime_total=Sum("final_fare"),
            lifetime_trips=Count("id"),
        )
    }

    by_driver = []
    for m in memberships:
        stat = driver_stats.get(m.driver_id, {})
        d = m.driver
        by_driver.append(
            {
                "membership_id": str(m.id),
                "driver_id": str(m.driver_id),
                "name": m.driver_display_name
                or (
                    d.public_display_name()
                    if hasattr(d, "public_display_name")
                    else (getattr(d, "driver_name", "") or d.user.first_name or "Driver")
                ),
                "phone": getattr(d, "driver_phone", "") or d.user.phone,
                "today_earnings": _money(stat.get("today_total")),
                "today_trips": stat.get("today_trips") or 0,
                "lifetime_earnings": _money(stat.get("lifetime_total")),
                "lifetime_trips": stat.get("lifetime_trips") or 0,
            }
        )

    by_driver.sort(key=lambda row: Decimal(row["today_earnings"]), reverse=True)
    return {
        "today": dash["today"],
        "week": dash["week"],
        "month": dash["month"],
        "lifetime": dash["lifetime"],
        "by_driver": by_driver,
    }
