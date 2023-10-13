from base64 import b64decode, b64encode

import itsdangerous
import ujson as json  # type: ignore[import]
from itsdangerous.exc import BadSignature

from yaa.datastructures import MutableHeaders
from yaa.middlewares.core import Middleware
from yaa.requests import HttpConnection
from yaa.types import ASGI3App, Message, Receive, Scope, Send


class SessionMiddleware(Middleware):
    def __init__(
        self,
        app: ASGI3App,
        secret_key: str,
        session_cookie: str = "session",
        max_age: int = 14 * 24 * 60 * 60,  # 14 days, in seconds
        path: str = "/",
        same_site: str = "lax",
        https_only: bool = False,
        debug: bool = False,
    ) -> None:
        super().__init__(app)
        self.debug = debug
        self.signer = itsdangerous.TimestampSigner(secret_key)
        self.session_cookie = session_cookie
        self.path = path
        self.max_age = max_age
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:
            self.security_flags += "; secure"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            conn = HttpConnection(scope=scope)
            if self.session_cookie in conn.cookies:
                data = conn.cookies[self.session_cookie].encode("utf-8")
                try:
                    data = self.signer.unsign(data, max_age=self.max_age)
                    scope["session"] = json.loads(b64decode(data))  # type: ignore
                except BadSignature:
                    scope["session"] = {}  # type: ignore
            else:
                scope["session"] = {}  # type: ignore
            await self.asgi(scope=scope, receive=receive, send=send)
        else:
            await self.app(scope, receive, send)  # pragma: no cover

    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        was_empty_session = not scope["session"]

        async def sender(message: Message) -> None:
            if message["type"] == "http.response.start":
                if scope["session"]:
                    data = b64encode(json.dumps(scope["session"]).encode())
                    data = self.signer.sign(data)
                    headers = MutableHeaders(scope=message)
                    header_value = "%s=%s; path=%s; Max-Age=%d; %s" % (
                        self.session_cookie,
                        data.decode("utf-8"),
                        self.path,
                        self.max_age,
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                elif not was_empty_session:
                    headers = MutableHeaders(scope=message)
                    header_value = "%s=%s; %s" % (
                        self.session_cookie,
                        f"null; path={self.path}; expires=Thu, 01 Jan 1970 00:00:00 GMT",
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                else:
                    pass

            await send(message)

        await self.app(scope, receive, sender)
