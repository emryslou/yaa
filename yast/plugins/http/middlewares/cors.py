import functools
import re
import typing

from yast.datastructures import Headers, MutableHeaders
from yast.middlewares.core import Middleware
from yast.responses import PlainTextResponse, Response
from yast.types import ASGIApp, Message, Receive, Scope, Send

ALL_METHODS = (
    "DELETE",
    "GET",
    "PATCH",
    "OPTIONS",
    "POST",
    "PUT",
)


class CORSMiddleware(Middleware):
    def __init__(
        self,
        app: ASGIApp,
        allow_origins: typing.Sequence[str] = (),
        allow_methods: typing.Sequence[str] = ("GET"),
        allow_headers: typing.Sequence[str] = (),
        allow_credentials: bool = False,
        allow_origin_regex: str = None,
        expose_headers: typing.Sequence[str] = (),
        max_age: int = 600,
    ) -> None:
        if "*" in allow_methods:
            allow_methods = ALL_METHODS

        compiled_allow_origin_regex = None
        if allow_origin_regex is not None:
            compiled_allow_origin_regex = re.compile(allow_origin_regex)

        simple_headers = {}
        if "*" in allow_origins:
            simple_headers["Access-Control-Allow-Origin"] = "*"

        if allow_credentials:
            simple_headers["Access-Control-Allow-Credentials"] = "true"
        if expose_headers:
            simple_headers["Access-Control-Expose-Headers"] = ",".join(expose_headers)

        preflight_headers = {}
        if "*" in allow_origins:
            preflight_headers["Access-Control-Allow-Origin"] = "*"
        else:
            preflight_headers["Vary"] = "Origin"

        preflight_headers.update(
            {
                "Access-Control-Allow-Methods": ",".join(allow_methods),
                "Access-Control-Max-Age": str(max_age),
            }
        )

        if allow_headers and "*" not in allow_headers:
            preflight_headers["Access-Control-Allow-Headers"] = ", ".join(allow_headers)
        if allow_credentials:
            preflight_headers["Access-Control-Allow-Credentials"] = "true"

        self.app = app

        self.allow_origins = allow_origins
        self.allow_all_origins = "*" in allow_origins
        self.allow_origin_regex = compiled_allow_origin_regex

        self.allow_methods = allow_methods

        self.allow_headers = [h.lower() for h in allow_headers]
        self.allow_all_headers = "*" in allow_headers

        self.simple_headers = simple_headers
        self.preflight_headers = preflight_headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            method = scope["method"]
            headers = Headers(scope=scope)
            origin = headers.get("origin")

            if origin is not None:
                if method == "OPTIONS" and "access-control-request-method" in headers:
                    await self.preflight_response(headers)(scope, receive, send)
                else:
                    await self.simple_response(
                        scope=scope,
                        receive=receive,
                        send=send,
                        origin=origin,
                        request_headers=headers,
                    )
                return

        await self.app(scope, receive, send)

    def is_allowed_origin(self, origin: str) -> bool:
        if self.allow_all_origins:
            return True

        if self.allow_origin_regex is not None and self.allow_origin_regex.match(
            origin
        ):
            return True
        return origin in self.allow_origins

    def preflight_response(self, request_headers) -> Response:
        req_origin = request_headers["origin"]
        req_method = request_headers["access-control-request-method"]
        req_headers = request_headers.get("access-control-request-headers")
        # req_cookie = "cookie" in request_headers  # todo: how to handle???

        headers = dict(self.preflight_headers)
        failures = []
        if self.is_allowed_origin(origin=req_origin):
            if not self.allow_all_origins:
                headers["Access-Control-Allow-Origin"] = req_origin
        else:
            failures.append("origin")

        if req_method not in self.allow_methods:
            failures.append("method")

        if self.allow_all_headers and req_headers is not None:
            headers["Access-Control-Allow-Headers"] = req_headers
        elif req_headers is not None:
            for header in [h.lower() for h in req_headers.split(",")]:
                if header.strip() not in self.allow_headers:
                    failures.append("headers")

        if failures:
            failure_text = "Disallowed CORS " + ",".join(failures)
            return PlainTextResponse(failure_text, status_code=400, headers=headers)

        return PlainTextResponse("OK", status_code=200, headers=headers)

    async def simple_response(
        self,
        receive: Receive,
        send: Send,
        scope=None,
        origin=None,
        request_headers=None,
    ):
        send = functools.partial(self.send, send=send, request_headers=request_headers)
        await self.app(scope, receive, send)

    async def send(self, message: Message, send: Send, request_headers=None) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return
        message.setdefault("headers", [])
        headers = MutableHeaders(raw=message["headers"])
        origin = request_headers["Origin"]
        has_cookie = "cookie" in request_headers

        if self.allow_all_origins and has_cookie:
            self.simple_headers["Access-Control-Allow-Origin"] = origin
        elif not self.allow_all_origins and self.is_allowed_origin(origin):
            headers["Access-Control-Allow-Origin"] = origin
            headers.add_vary_header("Origin")
        headers.update(self.simple_headers)
        await send(message)
