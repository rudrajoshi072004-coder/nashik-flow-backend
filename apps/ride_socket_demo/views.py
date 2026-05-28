from django.http import JsonResponse
from django.views import View

from apps.ride_socket_demo import state


class DriversListView(View):
    """Compatibility with Expo driver app GET /drivers (legacy Node demo)."""

    async def get(self, _request):
        drivers = await state.drivers_snapshot()
        return JsonResponse(drivers, safe=False)
