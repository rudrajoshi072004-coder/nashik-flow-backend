from django.urls import path

from apps.admin_portal.views import (
    PortalAuditLogsView,
    PortalCustomersView,
    PortalDriversView,
    PortalOverviewView,
    PortalSettingsView,
)

urlpatterns = [
    path("overview/", PortalOverviewView.as_view(), name="admin-portal-overview"),
    path("drivers/", PortalDriversView.as_view(), name="admin-portal-drivers"),
    path("customers/", PortalCustomersView.as_view(), name="admin-portal-customers"),
    path("settings/", PortalSettingsView.as_view(), name="admin-portal-settings"),
    path("audit-logs/", PortalAuditLogsView.as_view(), name="admin-portal-audit-logs"),
]
