from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def get_user_from_token(token: str):
    authenticator = JWTAuthentication()
    validated = authenticator.get_validated_token(token)
    return authenticator.get_user(validated)


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope["user"] = None
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = None
        if "token" in params and params["token"]:
            token = params["token"][0]
        else:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]

        if token:
            try:
                scope["user"] = await get_user_from_token(token)
            except Exception:
                scope["user"] = None

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
