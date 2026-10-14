"""Shared pricing / trip-type constants."""

from __future__ import annotations

# Customer goods flow — trip type (Within City / Outstation) required; must match app + driver categories.
CUSTOMER_TRUCK_CATEGORY_NAMES = frozenset(
    {
        "mini tempo",  # Truck 7 ft (0.75 ton)
        "pickup truck",  # Truck 8 ft (1.25 ton) / Part load
        "3-wheeler",
        "4-wheeler",
    }
)
