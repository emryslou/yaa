import functools
import re
import typing

from yaa.datastructures import Headers, MutableHeaders
from yaa.middlewares.core import Middleware
from yaa.responses import PlainTextResponse, Response
from yaa.types import ASGIApp, Message, Receive, Scope, Send

ALL_METHODS = (
    "DELETE",
    "GET",
    "HEAD",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)

SAFELISTED_HEADERS = {"Accept", "Accept-Language", "Content-Language", "Content-Type"}


class CORSMiddleware(Middleware):
    def __init__(
        self,
        app: ASGIApp,
        debug: bool = False,
        allow_origins: typing.Sequence[str] = (),
        allow_methods: typing.Sequence[str] = ("GET"),
        allow_headers: typing.Sequence[str] = (),
        allow_credentials: bool = False,
        allow_origin_regex: str = None,
        expose_headers: typing.Sequence[str] = (),
        max_age: int = 600,
    ) -> None:
        super().__init__(app)
        self.debug = debug
        if "*" in allow_methods:
            allow_methods = ALL_METHODS

        compiled_allow_origin_regex = None
        if allow_origin_regex is not None:
            compiled_allow_origin_regex = re.compile(allow_origin_regex)

        allow_all_origins = "*" in allow_origins
        allow_all_headers = "*" in allow_headers
        preflight_explicit_allow_origin = not allow_all_origins or allow_credentials

        simple_headers = {}
        if allow_all_origins:
            simple_headers["Access-Control-Allow-Origin"] = "*"

        if allow_credentials:
            simple_headers["Access-Control-Allow-Credentials"] = "true"
        if expose_headers:
            simple_headers["Access-Control-Expose-Headers"] = ",".join(expose_headers)

        preflight_headers = {}
        if preflight_explicit_allow_origin:
            preflight_headers["Vary"] = "Origin"
        else:
            preflight_headers["Access-Control-Allow-Origin"] = "*"

        preflight_headers.update(
            {
                "Access-Control-Allow-Methods": ",".join(allow_methods),
                "Access-Control-Max-Age": str(max_age),
            }
        )
        allow_headers = SAFELISTED_HEADERS | set(allow_headers)
        if allow_headers and not allow_all_headers:
            preflight_headers["Access-Control-Allow-Headers"] = ", ".join(allow_headers)
        if allow_credentials:
            preflight_headers["Access-Control-Allow-Credentials"] = "true"

        self.app = app

        self.allow_origins = allow_origins
        self.allow_all_origins = allow_all_origins
        self.allow_origin_regex = compiled_allow_origin_regex

        self.allow_methods = allow_methods

        self.allow_headers = [h.lower() for h in allow_headers]
        self.allow_all_headers = allow_all_headers

        self.preflight_headers = preflight_headers
        self.preflight_explicit_allow_origin = preflight_explicit_allow_origin

        self.simple_headers = simple_headers

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

        if self.allow_origin_regex is not None and self.allow_origin_regex.fullmatch(
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
            if self.preflight_explicit_allow_origin:
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
        headers.update(self.simple_headers)
        origin = request_headers["Origin"]
        has_cookie = "cookie" in request_headers

        if self.allow_all_origins and has_cookie:
            self.allow_explicit_origin(headers, origin)
        elif not self.allow_all_origins and self.is_allowed_origin(origin):
            self.allow_explicit_origin(headers, origin)

        await send(message)

    @staticmethod
    def allow_explicit_origin(headers: MutableHeaders, origin: str) -> None:
        headers["Access-Control-Allow-Origin"] = origin
        headers.add_vary_header("Origin")
