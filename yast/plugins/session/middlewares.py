import functools
from base64 import b64decode, b64encode

import itsdangerous
import ujson as json
from itsdangerous.exc import BadTimeSignature, SignatureExpired

from yast.datastructures import MutableHeaders
from yast.requests import Request
from yast.types import ASGIApp, ASGIInstance, Message, Receive, Scope, Send


class SessionMiddleware(object):
    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        session_cookie: str = "session",
        max_age: int = 14 * 24 * 60 * 60,  # 14 days, in seconds
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        self.app = app
        self.signer = itsdangerous.TimestampSigner(secret_key)
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:
            self.security_flags += "; secure"

    def __call__(self, scope: Scope) -> ASGIInstance:
        if scope["type"] in ("http", "websocket"):
            req = Request(scope=scope)
            if self.session_cookie in req.cookie:
                data = req.cookie[self.session_cookie].encode("utf-8")
                try:
                    data = self.signer.unsign(data, max_age=self.max_age)
                    scope["session"] = json.loads(b64decode(data))
                except (BadTimeSignature, SignatureExpired):
                    scope["session"] = {}
            else:
                scope["session"] = {}
            return functools.partial(self.asgi, scope=scope)

        return self.app(scope)

    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        inner = self.app(scope)
        was_empty_session = not scope["session"]

        async def sender(message: Message) -> None:
            if message["type"] == "http.response.start":
                if scope["session"]:
                    data = b64encode(json.dumps(scope["session"]).encode())
                    data = self.signer.sign(data)
                    headers = MutableHeaders(scope=message)
                    header_value = "%s=%s; path=/; Max-Age=%d; %s" % (
                        self.session_cookie,
                        data.decode("utf-8"),
                        self.max_age,
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                elif not was_empty_session:
                    headers = MutableHeaders(scope=message)
                    header_value = "%s=%s; %s" % (
                        self.session_cookie,
                        "null; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT",
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                else:
                    # todo nothing
                    pass
            await send(message)

        await inner(receive, sender)
