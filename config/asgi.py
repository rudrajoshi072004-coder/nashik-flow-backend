import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from socketio import ASGIApp

os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "config.settings.local"))

django_asgi_app = get_asgi_application()

# Import websocket routing only after Django app registry is initialized.
from apps.ride_socket_demo.socket_server import sio  # noqa: E402
from config.asgi_lifespan import LifespanMiddleware  # noqa: E402
from config.routing import websocket_urlpatterns  # noqa: E402
from config.socket_auth import JWTAuthMiddlewareStack  # noqa: E402

_inner = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)

# Socket.IO at /socket.io/*; everything else (HTTP + Channels WS) uses `_inner`.
# LifespanMiddleware avoids "ASGI lifespan protocol appears unsupported" under Uvicorn/Gunicorn.
application = LifespanMiddleware(ASGIApp(sio, _inner))
