import asyncio
import http.cookies
import json
import typing
import warnings
from collections.abc import Mapping
from typing import Iterator
from urllib.parse import unquote

from yast.datastructures import URL, Address, FormData, Headers, QueryParams
from yast.formparsers import FormParser, MultiPartParser
from yast.types import Message, Receive, Scope

try:
    from multipart.multipart import parse_options_header
except ImportError:  # pragma: no cover
    parse_options_header = None  # pragma: no cover


async def empty_receive() -> Message:
    raise RuntimeError("Receive channel has not been made avaible")  # pragma: nocover


class State(object):
    pass


class HttpConnection(Mapping):
    def __init__(self, scope: Scope, *args, **kwargs) -> None:
        self._scope = scope

    def __getitem__(self, __key: typing.Any) -> typing.Any:
        return self._scope[__key]

    def __iter__(self) -> Iterator:
        return iter(self._scope)

    def __len__(self) -> int:
        return len(self._scope)

    @property
    def url(self) -> URL:
        if not hasattr(self, "_url"):
            self._url = URL(scope=self._scope)
        return self._url

    @property
    def app(self) -> typing.Any:
        return self._scope["app"]

    @property
    def headers(self) -> Headers:
        if not hasattr(self, "_headers"):
            self._headers = Headers(scope=self._scope)
        return self._headers

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, "_query_params"):
            self._query_params = QueryParams(self._scope["query_string"])
        return self._query_params

    @property
    def path_params(self) -> dict:
        return self._scope.get("path_params", {})

    @property
    def cookie(self) -> typing.Dict[str, str]:
        if not hasattr(self, "_cookies"):
            cookies = {}
            cookie_headers = self.headers.get("cookie")
            if cookie_headers:
                cookie = http.cookies.SimpleCookie()
                cookie.load(cookie_headers)
                for k, morse in cookie.items():
                    cookies[k] = morse.value
            self._cookies = cookies
        return self._cookies

    @property
    def client(self) -> Address:
        host, port = self._scope.get("client") or (None, None)
        return Address(host=host, port=port)

    @property
    def session(self):
        assert "session" in self._scope, (
            "`SessionMiddleware` must be " "installed to access request.session"
        )
        return self._scope["session"]

    @property
    def database(self):
        warnings.warn("attr `database` will be removed in the future")
        assert "database" in self._scope, (
            "`DatabaseMiddleware` must be " "installed to access request.database"
        )
        return self._scope["database"]

    @property
    def auth(self) -> typing.Any:
        assert (
            "auth" in self._scope
        ), "`AuthenticationMiddleware` must be installed to access request.auth"
        return self._scope["auth"]

    @property
    def state(self) -> State:
        if "state" not in self._scope:
            self._scope["state"] = State()
        return self._scope["state"]

    @property
    def user(self) -> typing.Any:
        assert (
            "user" in self._scope
        ), "`AuthenticationMiddleware` must be installed to access request.user"
        return self._scope["user"]

    def url_for(self, name: str, **path_params: typing.Any) -> URL:
        router = self._scope["router"]

        url = router.url_path_for(name, **path_params)
        return url.make_absolute_url(base_url=self.url)


class ClientDisconnect(Exception):
    pass


class Request(HttpConnection):
    def __init__(self, scope: Scope, receive: Receive = None):
        super().__init__(scope=scope)
        self._receive = empty_receive if receive is None else receive
        self._stream_consumed = False
        self._is_disconnected = False

    def set_receive_channel(self, receive: Receive) -> None:
        self._receive = receive

    @property
    def method(self) -> str:
        return self._scope["method"]

    @property
    def relative_url(self) -> URL:
        if not hasattr(self, "_relative_url"):
            url = self._scope["path"]
            query_str = self._scope["query_string"]

            if query_str:
                url += "?" + unquote(query_str.decode())

            self._relative_url = url

        return self._relative_url

    @property
    def receive(self):
        return self._receive

    async def stream(self):
        if hasattr(self, "_body"):
            yield self._body
            yield b""
            return

        if self._stream_consumed:
            raise RuntimeError("Stream consumed")

        self._stream_consumed = True
        while True:
            message = await self._receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    yield body
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                self._is_disconnected = True
                raise ClientDisconnect()

        yield b""

    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            body = b""
            async for chunk in self.stream():
                body += chunk
            self._body = body
        return self._body

    async def json(self) -> typing.Any:
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = json.loads(body)
        return self._json

    async def form(self) -> FormData:
        if not hasattr(self, "_form"):
            assert (
                parse_options_header is not None
            ), "The `python-multipart` library must be installed to use form parsing"

            content_type_header = self.headers.get("Content-Type")
            content_type, options = parse_options_header(content_type_header)
            if content_type == b"multipart/form-data":
                parser = MultiPartParser(self.headers, self.stream)
                self._form = await parser.parse()
            elif content_type == b"application/x-www-form-urlencoded":
                parser = FormParser(self.headers, self.stream)
                self._form = await parser.parse()
            else:
                self._form = FormData()
        return self._form

    async def close(self):
        if hasattr(self, "_form"):
            await self._form.close()

    async def is_disconnected(self) -> bool:
        if not self._is_disconnected:
            try:
                message = await asyncio.wait_for(self._receive(), timeout=0.00000001)
            except asyncio.TimeoutError:
                message = {}

            # todo: may raise KeyError
            if message.get("type") == "http.disconnect":
                self._is_disconnected = True

        return self._is_disconnected
