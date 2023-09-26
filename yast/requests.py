import asyncio
import http.cookies
import json
import typing
import warnings
from collections.abc import Mapping
from typing import Iterator
from urllib.parse import unquote

from yast.datastructures import (
    URL,
    Address,
    FormData,
    Headers,
    QueryParams,
    State,
)
from yast.formparsers import FormParser, MultiPartParser
from yast.types import Message, Receive, Scope, Send

try:
    from multipart.multipart import parse_options_header
except ImportError:  # pragma: no cover
    parse_options_header = None  # pragma: no cover


SERVER_PUSH_HEADERS_TO_COPY = {
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "user-agent",
}


async def empty_receive() -> Message:
    raise RuntimeError("Receive channel has not been made avaible")  # pragma: nocover


async def empty_send(message: Message) -> None:
    raise RuntimeError("Send channel has not been made avaible")  # pragma: nocover


class HttpConnection(Mapping):
    def __init__(self, scope: Scope, *args, **kwargs) -> None:
        self._scope = scope
        self._scope.setdefault("state", {})

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
    def scope(self):
        return self._scope

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
        if not hasattr(self, "_state"):
            self._state = State(self._scope["state"])
        return self._state

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
    def __init__(
        self, scope: Scope, receive: Receive = empty_receive, send: Send = empty_send
    ):
        super().__init__(scope=scope)
        self._receive = receive
        self._send = send
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
            chunks = []
            async for chunk in self.stream():
                chunks.append(chunk)
            self._body = b"".join(chunks)
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

    async def send_push_promise(self, path: str) -> None:
        if "http.response.push" in self.scope.get("extensions", {}):
            raw_headers = []
            for name in SERVER_PUSH_HEADERS_TO_COPY:
                for value in self.headers.getlist(name):
                    raw_headers.append(
                        (name.encode("latin-1"), value.encode("latin-1"))
                    )
            print("push file", path)
            await self._send(
                {"type": "http.response.push", "path": path, "headers": raw_headers}
            )
