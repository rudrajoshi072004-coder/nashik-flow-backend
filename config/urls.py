from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.admin_ops.api import AdminAuditLogViewSet, AdminOpsViewSet
from apps.bookings.api import BookingViewSet
from apps.common.api.health import HealthCheckView
from apps.common.api.routing import DrivingRouteView
from apps.common.views.public_pages import DeleteAccountView
from apps.customers.api import CustomerViewSet
from apps.dispatch.api import DispatchViewSet
from apps.drivers.api import DriverViewSet
from apps.fare_rules.api import FareRuleViewSet
from apps.payouts.api import PayoutViewSet
from apps.pricing.api import PricingRuleViewSet
from apps.service_zones.api import ServiceZoneViewSet
from apps.support.api import SupportTicketViewSet
from apps.ride_socket_demo.views import DriversListView
from apps.tracking.api import DriverLiveLocationViewSet
from apps.users.api import UserViewSet
from apps.vehicle_categories.api import VehicleCategoryViewSet
from apps.vehicles.api import VehicleViewSet
from apps.wallet_transactions.api import WalletTransactionViewSet
from apps.wallets.api import WalletViewSet

router = DefaultRouter()
router.register(r"customers/me", CustomerViewSet, basename="customer-me")
router.register(r"drivers/me", DriverViewSet, basename="driver-me")
router.register(r"users", UserViewSet, basename="users")
router.register(r"vehicles", VehicleViewSet, basename="vehicles")
router.register(r"vehicle-categories", VehicleCategoryViewSet, basename="vehicle-categories")
router.register(r"service-zones", ServiceZoneViewSet, basename="service-zones")
router.register(r"bookings", BookingViewSet, basename="bookings")
router.register(r"pricing-rules", PricingRuleViewSet, basename="pricing-rules")
router.register(r"fare-rules", FareRuleViewSet, basename="fare-rules")
router.register(r"dispatch", DispatchViewSet, basename="dispatch")
router.register(r"tracking/driver-locations", DriverLiveLocationViewSet, basename="driver-locations")
router.register(r"wallets", WalletViewSet, basename="wallets")
router.register(r"wallet-transactions", WalletTransactionViewSet, basename="wallet-transactions")
router.register(r"payouts", PayoutViewSet, basename="payouts")
router.register(r"support-tickets", SupportTicketViewSet, basename="support-tickets")
router.register(r"admin/ops", AdminOpsViewSet, basename="admin-ops")
router.register(r"admin/audit-logs", AdminAuditLogViewSet, basename="admin-audit-logs")

urlpatterns = [
    path("delete-account/", DeleteAccountView.as_view(), name="delete-account"),
    path("drivers", DriversListView.as_view(), name="ride-demo-drivers"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.authn.urls")),
    path("api/v1/admin/portal/", include("apps.admin_portal.urls")),
    path("api/v1/health", HealthCheckView.as_view(), name="health-check"),
    path("api/v1/routing/driving-route/", DrivingRouteView.as_view(), name="driving-route"),
    path("api/v1/", include(router.urls)),
]
