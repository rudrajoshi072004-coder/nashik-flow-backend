from django.urls import path

from .api import (
    OwnerAlertsView,
    OwnerDashboardView,
    OwnerDriverDetailView,
    OwnerDriversView,
    OwnerEarningsView,
    OwnerMeView,
    OwnerTripsView,
)

urlpatterns = [
    path("me", OwnerMeView.as_view(), name="owner-me"),
    path("dashboard", OwnerDashboardView.as_view(), name="owner-dashboard"),
    path("alerts", OwnerAlertsView.as_view(), name="owner-alerts"),
    path("drivers", OwnerDriversView.as_view(), name="owner-drivers"),
    path("drivers/<uuid:membership_id>", OwnerDriverDetailView.as_view(), name="owner-driver-detail"),
    path("trips", OwnerTripsView.as_view(), name="owner-trips"),
    path("earnings", OwnerEarningsView.as_view(), name="owner-earnings"),
]
