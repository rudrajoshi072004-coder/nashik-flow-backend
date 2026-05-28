from django.apps import AppConfig


class RideSocketDemoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ride_socket_demo"

    def ready(self) -> None:
        from apps.ride_socket_demo import state as _state

        _state.seed_drivers_if_empty()
