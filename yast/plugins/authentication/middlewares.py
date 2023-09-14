import functools

from yast.middlewares.core import Middleware
from yast.requests import Request
from yast.responses import PlainTextResponse
from yast.types import ASGIApp, ASGIInstance, Receive, Scope, Send

from .base import AuthCredentials, AuthenticationBackend, AuthenticationError, UnauthenticatedUser


class AuthenticationMiddleware(Middleware):
    def __init__(self, app: ASGIApp, backend: AuthenticationBackend) -> None:
        super().__init__(app)
        self.backend = backend

    def __call__(self, scope: Scope) -> ASGIInstance:
        return functools.partial(self.asgi, scope=scope)

    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        req = Request(scope=scope, receive=receive)
        try:
            auth_result = await self.backend.authenticate(req)
        except AuthenticationError as exc:
            res = PlainTextResponse(str(exc), status_code=400)
            await res(receive, send)
            return
        if auth_result is None:
            auth_result = AuthCredentials(), UnauthenticatedUser()

        scope["auth"], scope["user"] = auth_result

        await self.app(scope)(receive, send)
