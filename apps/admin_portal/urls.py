from django.urls import path

from apps.admin_portal.views import (
    PortalAuditLogsView,
    PortalCustomersView,
    PortalDriverDetailView,
    PortalDriverDocumentFileView,
    PortalDriverDocumentReviewView,
    PortalDriversView,
    PortalOverviewView,
    PortalSettingsView,
)

urlpatterns = [
    path("overview/", PortalOverviewView.as_view(), name="admin-portal-overview"),
    path("drivers/", PortalDriversView.as_view(), name="admin-portal-drivers"),
    path("drivers/<uuid:driver_id>/", PortalDriverDetailView.as_view(), name="admin-portal-driver-detail"),
    path("drivers/<uuid:driver_id>/documents/<uuid:doc_id>/file/", PortalDriverDocumentFileView.as_view(), name="admin-portal-driver-document-file"),
    path("drivers/<uuid:driver_id>/documents/<uuid:doc_id>/", PortalDriverDocumentReviewView.as_view(), name="admin-portal-driver-document-review"),
    path("customers/", PortalCustomersView.as_view(), name="admin-portal-customers"),
    path("settings/", PortalSettingsView.as_view(), name="admin-portal-settings"),
    path("audit-logs/", PortalAuditLogsView.as_view(), name="admin-portal-audit-logs"),
]
